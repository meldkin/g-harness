#!/bin/sh
# wsl_sandbox.sh - run a command inside a namespace fence, from inside WSL.
#
# Why: the Windows ACL restricted token denies writes but breaks TLS (measured: SEC_E_NO_CREDENTIALS),
# so it cannot wrap a worker that calls an API. WSL2 has no such defect (plain curl answers 200) and
# unprivileged user namespaces are enabled, so the fence is built from namespaces and networking is
# deliberately left working - every worker here has to reach an API.
#
# The fence, every step measured rather than assumed:
#   1. `/tmp` becomes a private tmpfs and the workspace is bind-mounted inside it at /tmp/work, so the
#      command runs in a directory this namespace owns (`mkdir /work` is refused: namespace root is
#      not the owner of `/`).
#   2. Each Windows drive mount (`/mnt/c`, `/mnt/d`, ...) is overlaid with its own tmpfs, which this
#      userns may do. This is what stops writes to C: or F: - a plain `mount -o remount,ro /mnt` is
#      not honoured for drvfs mounts and leaked a write into %TEMP% before.
#      The WSL infrastructure under /mnt is deliberately NOT hidden: `/mnt/wsl`, `/mnt/wslg` and
#      `/mnt/docker-desktop-disk` host the DNS and GUI plumbing, and hiding them kills name
#      resolution (measured: dns FAIL, http=000).
#   3. `/home` and `/root` are self-bound and remounted read-only, so the WSL profile is untouchable.
#   4. `/` is remounted read-only on a best-effort basis.
#
# Usage: wsl_sandbox.sh <workspace-path> <cwd-relative-to-workspace> -- <argv...>
set -u

WS="$1"
REL="$2"
shift 2
[ "${1:-}" = "--" ] && shift
[ -n "$WS" ] || { echo "usage: wsl_sandbox.sh <workspace> <rel-cwd> -- <argv...>" >&2; exit 64; }

mount -t tmpfs tmpfs /tmp 2>/dev/null || echo "warn: no private /tmp" >&2
mkdir -p /tmp/work 2>/dev/null
mount --bind "$WS" /tmp/work 2>/dev/null || echo "warn: workspace bind failed" >&2

for drive in /mnt/*; do
  [ -d "$drive" ] || continue
  case "$drive" in
    /mnt/wsl|/mnt/wslg|/mnt/docker-desktop-disk|/mnt/docker-desktop) continue ;;
  esac
  mount -t tmpfs tmpfs "$drive" 2>/dev/null || echo "warn: could not hide $drive" >&2
done

harden() {
  mount --bind "$1" "$1" 2>/dev/null && mount -o remount,ro,bind "$1" 2>/dev/null && return 0
  echo "warn: $1 stayed writable" >&2
}
harden /home
harden /root
mount -o remount,ro / 2>/dev/null || true

cd "/tmp/work/$REL" 2>/dev/null || cd /tmp/work 2>/dev/null || exit 66
# The WSL-side tooling installed with `pip --user` lives in ~/.local/bin, which a non-interactive
# shell does not have on PATH (measured: ruff reported "not found" while pytest resolved).
PATH="$PATH:$HOME/.local/bin"
export PATH
exec "$@"
