"""Load the project `.env` into the process environment for the CLI delegates.

Why this exists: the delegates spawn their CLI directly instead of going through
`opencode-env.ps1` / `codex-env.ps1`, so anything the launcher *synthesises* from `.env` is
missing. The concrete failure this fixes (measured 2026-10-16): the generated OpenCode config
declares the `freemodel` provider with `env: ["FREEMODEL_API_KEY"]`, the launcher derives that
from `OPENAI_API_KEY`, and a delegate that bypasses the launcher starts OpenCode without the
variable, so every `freemodel/...` model fails while `commandcode/...` works.

Values are read but never logged, and an already-set process variable wins unless `override`
is passed: the shell's environment stays the operator's decision.
"""

from __future__ import annotations

import os
from pathlib import Path

#: Variables the CLI config reads but `.env` does not define directly: the launcher derives
#: them, and so does this module so a direct spawn behaves like the launcher.
ALIASES: dict[str, str] = {
    "FREEMODEL_API_KEY": "OPENAI_API_KEY",
}

#: Base URLs that must not carry a trailing `/v1` because the config appends it.
NORMALIZE_BASE_URLS = ("OPENAI_BASE_URL", "COMMANDCODE_BASE_URL")

#: Default models per role, so a provider outage is a one-line `.env` change instead of a code
#: edit. The delegate's own constant is the fallback when the variable is unset.
MODEL_OVERRIDES: dict[str, str] = {
    "opencode": "SOLOCODE_MODEL_OPENCODE",
    "kilo": "SOLOCODE_MODEL_KILO",
    "codex": "SOLOCODE_MODEL_CODEX",
    "antigravity": "SOLOCODE_MODEL_ANTIGRAVITY",
}


def parse_env_file(path: Path) -> dict[str, str]:
    """Read a `.env` file into a dict. Quotes are stripped; comments and blanks are skipped."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[name.strip()] = value
    return values


def load_project_env(
    root: Path | None = None, *, override: bool = False
) -> dict[str, str]:
    """Export the project `.env` into `os.environ`, with the launcher's aliases and trimming."""
    root = Path(root) if root is not None else Path(__file__).resolve().parent.parent
    values = parse_env_file(root / ".env")
    for name, value in values.items():
        if value and (override or not os.environ.get(name)):
            os.environ[name] = value
    for alias, source in ALIASES.items():
        if os.environ.get(source) and not os.environ.get(alias):
            os.environ[alias] = os.environ[source]
    for name in NORMALIZE_BASE_URLS:
        current = os.environ.get(name)
        if current:
            trimmed = current.strip().rstrip("/")
            if trimmed.endswith("/v1"):
                trimmed = trimmed[: -len("/v1")]
            os.environ[name] = trimmed
    return values


def model_override(role: str) -> str | None:
    """The `.env` override for a role's default model, or None when unset."""
    variable = MODEL_OVERRIDES.get(role)
    if not variable:
        return None
    return os.environ.get(variable) or None
