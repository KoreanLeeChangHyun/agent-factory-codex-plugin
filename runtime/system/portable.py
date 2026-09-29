"""Small operating-system seams shared by the Linux, macOS and Windows runtimes.

POSIX keeps its existing descriptor, ownership and mode checks. Windows (native
Python, including when launched from Git Bash) relies on the per-user profile
ACL instead of POSIX modes, and on msvcrt byte-range locks instead of flock.
"""
from __future__ import annotations

import os
import stat
import sys
import time

WINDOWS = sys.platform == "win32"
SUPPORTED_PLATFORMS = frozenset({"linux", "darwin", "win32"})

O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
O_NONBLOCK = getattr(os, "O_NONBLOCK", 0)
O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
O_BINARY = getattr(os, "O_BINARY", 0)

if WINDOWS:
    import msvcrt
else:
    import fcntl


def lock_descriptor(descriptor: int, *, blocking: bool = True, timeout: float | None = None) -> None:
    """Take an exclusive whole-file lock; raise BlockingIOError when unavailable."""
    if not WINDOWS:
        if timeout is None:
            fcntl.flock(descriptor, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            return
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.01)
    # msvcrt.LK_LOCK gives up after about ten seconds; poll instead so blocking
    # callers keep POSIX semantics. Byte 0 may be locked beyond end of file.
    deadline = None if timeout is None else time.monotonic() + timeout
    while True:
        os.lseek(descriptor, 0, os.SEEK_SET)
        try:
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            return
        except OSError as error:
            if not blocking or (deadline is not None and time.monotonic() >= deadline):
                raise BlockingIOError(str(error)) from error
            time.sleep(0.01)


def unlock_descriptor(descriptor: int) -> None:
    if not WINDOWS:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        return
    os.lseek(descriptor, 0, os.SEEK_SET)
    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)


def private_to_user(info: os.stat_result) -> bool:
    """POSIX: owned by this user with no group/other bits. Windows: profile ACLs apply."""
    if WINDOWS:
        return True
    return info.st_uid == os.getuid() and not info.st_mode & 0o077


def user_tag() -> str:
    """A stable per-user name component for shared temporary directories."""
    if WINDOWS:
        import getpass
        return "".join(character if character.isalnum() else "_" for character in getpass.getuser()) or "user"
    return str(os.getuid())


def fsync_directory(path: os.PathLike[str] | str) -> None:
    """Persist a directory entry where the platform exposes directory descriptors."""
    if WINDOWS:
        return
    descriptor = os.open(path, os.O_RDONLY | O_DIRECTORY | O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def is_link(info: os.stat_result) -> bool:
    """Symlinks, and on Windows also junctions and other name-surrogate reparse points."""
    if stat.S_ISLNK(info.st_mode):
        return True
    if WINDOWS and getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        return getattr(info, "st_reparse_tag", 0) & 0x20000000 != 0
    return False


def native_executable(executable: str, command: str = "codex") -> str:
    """Map a Windows npm/pnpm/yarn shim to the native binary its package ships.

    Batch and PowerShell shims run through another interpreter whose argument
    parsing differs from CreateProcess. Codex ships ``codex.exe`` in a per-platform
    package (nested, hoisted, or in older releases inside ``@openai/codex``) under
    ``vendor/<target>/bin`` or ``vendor/<target>/codex``; Claude Code ships
    ``bin/claude.exe``. The Antigravity CLI is already a native binary.
    Unresolvable shims and non-Windows hosts are unchanged.
    """
    if not WINDOWS or command in ("agy", "antigravity"):
        return executable
    import re
    from pathlib import Path
    shim = Path(executable)
    if shim.suffix.lower() not in {".cmd", ".bat", ".ps1", ""}:
        return executable
    scope, name = ("@anthropic-ai", "claude-code") if command == "claude" else ("@openai", "codex")
    roots = [shim.parent / "node_modules" / scope / name]
    try:
        text = shim.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    # pnpm and yarn keep packages outside the shim directory; the shim names them relative to itself.
    for match in re.finditer(r'(?:%~?dp0%?|\$basedir|\$PSScriptRoot)[\\/]+([^"\'\s]+?\.(?:js|cjs|mjs|exe))', text, re.I):
        target = Path(os.path.normpath(shim.parent / match.group(1).replace("\\", "/")))
        if target.suffix.lower() == ".exe" and target.is_file():
            return str(target)
        parts = [part.lower() for part in target.parts]
        for index in range(len(parts) - 2, -1, -1):
            if parts[index:index + 3] == ["node_modules", scope.lower(), name]:
                roots.append(Path(*target.parts[:index + 3]))
                break
    for root in roots:
        chosen = _claude_in_package(root) if command == "claude" else _codex_in_package(root)
        if chosen is not None:
            return str(chosen)
    return executable


def _claude_in_package(root):
    return _find_below([root, *_sibling_packages(root, "claude-code-win32-")], "claude.exe")


def _codex_in_package(root):
    """Search the package and its nested/hoisted per-platform packages; layouts change between releases."""
    return _find_below([root, *_sibling_packages(root, "codex-win32-")], "codex.exe")


def _arm64():
    return "ARM64" in (os.environ.get("PROCESSOR_ARCHITECTURE", "").upper(),
                       os.environ.get("PROCESSOR_ARCHITEW6432", "").upper())


def _sibling_packages(root, prefix):
    try:
        names = sorted(path.name for path in root.parent.iterdir() if path.is_dir() and path.name.startswith(prefix))
    except OSError:
        return []
    preferred = "arm64" if _arm64() else "x64"
    return [root.parent / name for name in sorted(names, key=lambda name: preferred not in name)]


def _find_below(roots, file_name, max_depth=8):
    """Bounded breadth-first search, preferring binaries built for the host architecture."""
    import re
    machine = re.compile(r"aarch64|arm64" if _arm64() else r"x86_64|x64|amd64", re.I)
    level, visited = [(root, 0) for root in roots], set()
    while level:
        found, following = [], []
        for directory, depth in level:
            if directory in visited:
                continue
            visited.add(directory)
            try:
                entries = list(directory.iterdir())
            except OSError:
                continue
            for entry in entries:
                if entry.is_file() and entry.name.lower() == file_name:
                    found.append(entry)
                elif entry.is_dir() and depth < max_depth and entry.name != ".bin":
                    following.append((entry, depth + 1))
        if found:
            return sorted(found, key=lambda path: (not machine.search(str(path)), str(path)))[0]
        level = following
    return None


def find_cli(command):
    """Locate ``codex``/``claude`` like a new terminal would when the process PATH lacks it.

    Searches PATH, the login-shell PATH (POSIX) or registry PATH (Windows), nvm/fnm
    Node versions and common install directories, then maps Windows shims to native binaries.
    """
    import shutil
    from pathlib import Path
    found = shutil.which(command)
    if found:
        return native_executable(found, command)
    home = Path.home()
    env = os.environ.get
    directories = []
    if WINDOWS:
        directories += _registry_path()
        profile = Path(env("USERPROFILE") or home)
        local = Path(env("LOCALAPPDATA") or profile / "AppData/Local")
        roaming = Path(env("APPDATA") or profile / "AppData/Roaming")
        directories += [profile / ".local/bin", roaming / "npm", env("npm_config_prefix"), env("PNPM_HOME"),
                        local / "pnpm", Path(env("VOLTA_HOME") or local / "Volta") / "bin", env("NVM_SYMLINK"),
                        Path(env("ProgramFiles") or "C:/Program Files") / "nodejs", profile / "scoop/shims",
                        local / "Microsoft/WinGet/Links", profile / ".bun/bin", profile / ".cargo/bin"]
        winget = local / "Microsoft/WinGet/Packages"
        if winget.is_dir():
            directories += [inner for package in winget.glob("OpenJS.NodeJS*") for inner in package.iterdir() if inner.is_dir()]
        names = [f"{command}.exe", f"{command}.cmd", f"{command}.bat", f"{command}.ps1"]
    else:
        directories += _login_shell_path()
        prefix = env("npm_config_prefix")
        directories += [home / ".local/bin", home / ".claude/local", prefix and Path(prefix) / "bin", home / ".npm-global/bin",
                        env("PNPM_HOME"), home / ".local/share/pnpm", home / "Library/pnpm",
                        Path(env("VOLTA_HOME") or home / ".volta") / "bin", Path(env("BUN_INSTALL") or home / ".bun") / "bin",
                        home / ".asdf/shims", home / ".local/share/mise/shims", home / ".cargo/bin",
                        "/opt/homebrew/bin", "/usr/local/bin", "/home/linuxbrew/.linuxbrew/bin", "/usr/bin", "/snap/bin"]
        for versions, suffix in ((Path(env("NVM_DIR") or home / ".nvm") / "versions/node", "bin"),
                                 (Path(env("FNM_DIR") or home / ".local/share/fnm") / "node-versions", "installation/bin")):
            if versions.is_dir():
                directories += sorted((path / suffix for path in versions.iterdir()), key=lambda path: _version_key(path), reverse=True)
        names = [command]
    wsl = bool(env("WSL_DISTRO_NAME") or env("WSL_INTEROP"))
    ordered = [Path(d) for d in directories if d]
    if wsl:
        ordered = [d for d in ordered if not str(d).startswith("/mnt/")] + [d for d in ordered if str(d).startswith("/mnt/")]
    for directory in ordered:
        for name in names:
            candidate = directory / name
            if candidate.is_file() and (WINDOWS or os.access(candidate, os.X_OK)):
                return native_executable(str(candidate), command)
    return None


def _version_key(path):
    import re
    match = re.search(r"v?(\d+)\.(\d+)\.(\d+)", str(path))
    return tuple(int(part) for part in match.groups()) if match else (0, 0, 0)


def _login_shell_path():
    import subprocess
    shell = os.environ.get("SHELL") or "/bin/sh"
    try:
        output = subprocess.run([shell, "-ilc", "echo __AF__; printf %s \"$PATH\""], capture_output=True, text=True,
                                timeout=5, stdin=subprocess.DEVNULL).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [entry for entry in output.rpartition("__AF__")[2].strip().split(":") if entry]


def _registry_path():
    try:
        import winreg
    except ImportError:
        return []
    entries = []
    for hive, key in ((winreg.HKEY_CURRENT_USER, "Environment"),
                      (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")):
        try:
            with winreg.OpenKey(hive, key) as handle:
                value = winreg.QueryValueEx(handle, "Path")[0]
            entries += [os.path.expandvars(entry.strip()) for entry in value.split(";") if entry.strip()]
        except OSError:
            continue
    return entries


def replace(source: os.PathLike[str] | str, target: os.PathLike[str] | str) -> None:
    """os.replace, retrying Windows sharing violations while a reader holds the target open."""
    if not WINDOWS:
        os.replace(source, target)
        return
    deadline = time.monotonic() + 5.0
    while True:
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.02)
