#!/usr/bin/env python3
"""Guard Hook Test Suite - validates safety patterns"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / ".claude" / "hooks"))
import guard


def test_normalize_command():
    """Test command normalization strips wrappers."""
    assert guard.normalize_command("sudo ls") == "ls"
    assert guard.normalize_command("env FOO=bar ls") == "ls"


def test_protected_files():
    """Test protected config files list."""
    assert ".ruff.toml" in guard.PROTECTED_FILES
    assert "eslint.config.js" in guard.PROTECTED_FILES
    assert "biome.json" in guard.PROTECTED_FILES


def test_executor_mode():
    """Test executor mode exemptions."""
    assert guard.executor_mode_exempt(".solocode/executor-mode")
    assert guard.executor_mode_exempt(".gemini/antigravity/handoff/inbox/task.md")
    assert not guard.executor_mode_exempt("tools/test.py")


def test_mask_separator_quotes():
    """A quoted span holding a separator is data, not a command boundary."""
    assert guard.mask_separator_quotes("rg 'echo x; diskpart' .") == "rg '' ."
    assert guard.mask_separator_quotes('rg "a|b" .') == "rg '' ."
    # No separator inside the quotes, so the text must survive: `rm -rf '/'`
    # depends on the quoted root still reaching the pattern.
    assert guard.mask_separator_quotes("rm -rf '/'") == "rm -rf '/'"
    # An unbalanced quote passes through rather than swallowing the tail.
    assert guard.mask_separator_quotes("echo 'unclosed; tail") == "echo 'unclosed; tail"


def test_destructive_scan_ignores_data_in_quotes():
    """find_destructive reads the masked text, so naming a command stays allowed."""
    assert guard.find_destructive("rg 'echo x; diskpart' .") is None
    assert guard.find_destructive("rg 'Remove-Item x -Recurse -Force' .") is None
    assert guard.find_destructive("rm -rf /") is not None
    assert guard.find_destructive("Remove-Item C:/ -Recurse") is not None
    assert (
        guard.find_destructive('cmd /c "Remove-Item -Recurse -Force C:\\\\data"')
        is not None
    )
    # A shell wrapper after a separator, which normalize_command only unwraps at
    # the start of the command, must still be caught.
    assert guard.find_destructive("echo hi && bash -c 'rm -rf /'") is not None
    assert guard.find_destructive("true; sh -c 'rm -rf /'") is not None
    # The same wrapper inside quoted search text is data, not command position.
    assert (
        guard.find_destructive("rg 'cmd /c \"Remove-Item -Recurse -Force C:\\data\"' .")
        is None
    )
    assert (
        guard.find_destructive(
            "rg 'powershell -Command \"Remove-Item -Recurse -Force C:\\data\"' ."
        )
        is None
    )
    # A `bash -c` wrapper after a separator is executable command text; masking
    # its quoted payload as search data first erased the destructive command.
    assert guard.find_destructive("echo hi && bash -c 'rm -rf /etc'") is not None
    assert guard.find_destructive("echo hi && bash -c 'cd / && rm -rf /'") is not None
    assert (
        guard.find_destructive("echo hi && bash -c 'rm -rf /; echo done'") is not None
    )
    # The Windows wrappers carry the same payload-before-masking defect.
    assert (
        guard.find_destructive(
            'echo hi && cmd /c "Remove-Item -Recurse -Force C:\\data; echo x"'
        )
        is not None
    )
    assert (
        guard.find_destructive(
            "echo hi && powershell -Command "
            '"Remove-Item -Recurse -Force C:\\data; echo x"'
        )
        is not None
    )
    # The same wrappers inside quoted search text are data, not command position.
    assert guard.find_destructive("rg \"echo hi && bash -c 'rm -rf /etc'\" .") is None
    assert (
        guard.find_destructive("rg \"echo hi && bash -c 'cd / && rm -rf /'\" .") is None
    )
    assert (
        guard.find_destructive("rg \"echo hi && bash -c 'rm -rf /; echo done'\" .")
        is None
    )
    assert guard.find_destructive("rg \"bash -c 'rm -rf /; echo done'\" .") is None
    assert (
        guard.find_destructive(
            "rg 'echo hi && cmd /c \"Remove-Item -Recurse -Force C:\\data; echo x\"' ."
        )
        is None
    )


def test_unwrap_command_wrappers():
    """An executable wrapper unwraps; the same text as search data does not."""
    assert (
        guard.unwrap_command_wrappers("echo hi && bash -c 'cd / && rm -rf /'")
        == "echo hi && cd / && rm -rf /"
    )
    assert (
        guard.unwrap_command_wrappers("rg \"bash -c 'rm -rf /; echo done'\" .")
        == "rg \"bash -c 'rm -rf /; echo done'\" ."
    )
    assert (
        guard.unwrap_command_wrappers('echo hi && cmd /c "Remove-Item C:/ -Recurse"')
        == "echo hi && Remove-Item C:/ -Recurse"
    )
    # A chained payload still unwraps, and `env` leads a wrapper just as `sudo`
    # does -- the prefix list mirrors _RM_CMD's composition prefixes.
    assert (
        guard.unwrap_command_wrappers("echo hi && bash -c 'rm -rf /; echo done'")
        == "echo hi && rm -rf /; echo done"
    )
    assert (
        guard.unwrap_command_wrappers("echo hi && env bash -c 'rm -rf /; echo done'")
        == "echo hi && rm -rf /; echo done"
    )
    # An ambiguous parse returns the text untouched so the masking path decides:
    # a candidate quote behind an odd backslash run, one followed by a backslash
    # (the POSIX `'\''` concatenation), and a doubled quote in a PowerShell
    # payload.
    assert (
        guard.unwrap_command_wrappers('bash -c "echo C:\\"; rm -rf / && echo "done"')
        == 'bash -c "echo C:\\"; rm -rf / && echo "done"'
    )
    assert (
        guard.unwrap_command_wrappers(r"""bash -c 'echo '\''hi'\''; rm -rf /'""")
        == r"""bash -c 'echo '\''hi'\''; rm -rf /'"""
    )
    assert (
        guard.unwrap_command_wrappers(
            'powershell -Command "Write-Host ""hi""; '
            + 'Remove-Item -Recurse -Force C:\\data"'
        )
        == 'powershell -Command "Write-Host ""hi""; '
        + 'Remove-Item -Recurse -Force C:\\data"'
    )


def test_quoted_system_trees_and_chained_payloads():
    """Orchestrator follow-up: pin what mutation testing showed was unpinned."""
    # The quote terminator's job: a quoted system tree is the same wipe.
    assert guard.find_destructive("rm -rf '/etc'") is not None
    assert guard.find_destructive('rm -rf "/usr"') is not None
    # ...and the same tree chained inside an executable wrapper was still a miss.
    assert (
        guard.find_destructive("echo hi && bash -c 'rm -rf /etc; echo x'") is not None
    )
    # A search that names a quoted system tree stays data.
    assert guard.find_destructive("rg \"rm -rf '/etc'\" .") is None


def run_self_test():
    """Run basic validation tests."""
    print("Guard hook self-test...")
    tests = [
        ("Command normalization", test_normalize_command),
        ("Protected files", test_protected_files),
        ("Executor mode", test_executor_mode),
        ("Separator-aware masking", test_mask_separator_quotes),
        ("Destructive scan masking", test_destructive_scan_ignores_data_in_quotes),
        ("Wrapper unwrapping", test_unwrap_command_wrappers),
        ("Quoted system trees", test_quoted_system_trees_and_chained_payloads),
    ]

    passed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  [OK] {name}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")

    print(f"\n{passed}/{len(tests)} passed")
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if run_self_test() else 1)
