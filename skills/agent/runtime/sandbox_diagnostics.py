"""Read-only host diagnostics; never change or weaken the requested sandbox."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def platform_issue(platform=None):
    """Describe Agent Factory support independently of native Codex support."""
    platform = sys.platform if platform is None else platform
    if platform == "linux":
        return None
    name = {"darwin": "macOS", "win32": "Windows"}.get(platform, platform)
    return {
        "code": "managed_platform_unsupported",
        "message": f"Agent Factory managed execution is not supported on {name}: "
        "process identity and containment require Linux /proc. Use a supported Linux "
        "host (including a separately checked Linux VM/WSL environment). Native Codex "
        "platform support does not imply Agent Factory runtime support.",
    }


def sandbox_failure(text):
    """Match runtime/helper errors, not generic permission failures or agent prose."""
    if "fs sandbox helper failed" in text:
        return (
            "Codex filesystem sandbox initialization failed. Run exec.py doctor --probe. "
            "On Linux, inspect namespace/container restrictions and security audit logs "
            "(including AppArmor where enabled); EPERM alone does not identify the policy. "
            "On other hosts, check native sandbox support and Agent Factory platform support. "
            "Keep the requested permissions; no automatic sandbox fallback is allowed."
        )
    if "sandbox-exec:" in text and any(marker in text for marker in (
        "sandbox_apply: Operation not permitted", "invalid profile", "No such file")):
        return "macOS sandbox initialization failed; check the native sandbox profile and host policy. " + platform_issue("darwin")["message"]
    if "Windows sandbox" in text and any(marker in text for marker in (
        "setup failed", "initialization failed")):
        return "Windows sandbox initialization failed; check native sandbox setup. " + platform_issue("win32")["message"]
    return None


def diagnose(*, codex="codex", probe=False):
    """Inventory without registry writes; optionally exercise system bubblewrap only."""
    issue = platform_issue()
    result = {
        "schemaVersion": 1, "kind": "sandbox-diagnostics", "platform": sys.platform,
        "managedExecution": "unsupported" if issue else "linux-prerequisites-unverified",
        "issue": issue, "codexExecutable": None,
        "sandboxReadiness": "unknown", "probe": {"status": "not-run"},
    }
    if issue:
        return result
    result["codexExecutable"] = shutil.which(codex)
    result["linuxProcessIdentityAvailable"] = Path("/proc/self/stat").is_file() and Path("/proc/sys/kernel/random/boot_id").is_file()
    try:
        result["apparmorRestrictsUserNamespaces"] = Path(
            "/proc/sys/kernel/apparmor_restrict_unprivileged_userns"
        ).read_text(encoding="ascii").strip() == "1"
    except (OSError, UnicodeError):
        result["apparmorRestrictsUserNamespaces"] = None
    executable = shutil.which("bwrap")
    result["systemBubblewrap"] = executable
    result["note"] = (
        "System bubblewrap is diagnostic evidence only: Codex may use a bundled helper. "
        "A successful probe does not prove the complete Codex permission profile works. "
        "AppArmor restriction being enabled does not itself prove a denial."
    )
    if not probe:
        return result
    if executable is None:
        result["probe"] = {"status": "unavailable", "message": "System bwrap is absent; inspect the selected Codex helper."}
        return result
    try:
        completed = subprocess.run(
            [executable, "--unshare-user", "--unshare-net", "--ro-bind", "/", "/",
             "--proc", "/proc", "--dev", "/dev", "--", "/bin/true"],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5,
            check=False,
        )
        result["probe"] = {
            "status": "passed" if completed.returncode == 0 else "failed",
            "exitCode": completed.returncode, "stderr": completed.stderr[:4000],
        }
    except (OSError, subprocess.TimeoutExpired) as error:
        result["probe"] = {"status": "unavailable", "message": str(error)[:4000]}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--probe", action="store_true", help="Run a bounded, network-isolated system bubblewrap probe")
    args = parser.parse_args(argv)
    result = diagnose(codex=args.codex, probe=args.probe)
    print(json.dumps(result))
    if result["issue"]:
        return 2
    return 1 if result["probe"]["status"] in {"failed", "unavailable"} or result["codexExecutable"] is None or not result.get("linuxProcessIdentityAvailable", True) else 0


if __name__ == "__main__":
    raise SystemExit(main())
