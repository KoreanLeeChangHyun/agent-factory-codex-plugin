from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "skills" / "specification" / "scripts" / "serve.py"
LAUNCHER_PATH = ROOT / "skills" / "specification" / "assets" / "spec.sh"
ASSET_ROOT = ROOT / "skills" / "specification" / "assets" / "browser"
COMMON_ROOT = ROOT / ".agent-factory" / "specification" / "common"

SPEC = importlib.util.spec_from_file_location("specification_serve", SERVER_PATH)
assert SPEC is not None and SPEC.loader is not None
SERVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SERVER)


class SpecificationBrowserServerTests(unittest.TestCase):
    def test_launcher_has_the_exact_path_and_executable_mode(self) -> None:
        self.assertTrue(LAUNCHER_PATH.is_file())
        self.assertEqual(0o755, stat.S_IMODE(LAUNCHER_PATH.stat().st_mode))

    def test_launcher_resolves_its_physical_file_and_is_self_contained(self) -> None:
        launcher = LAUNCHER_PATH.read_text(encoding="utf-8")
        self.assertIn("link_limit=40", launcher)
        self.assertIn('while [ -L "$script_path" ]; do', launcher)
        self.assertIn("too many symbolic links while resolving launcher", launcher)
        self.assertIn('link_target=$(readlink "$script_path")', launcher)
        self.assertIn('/*) script_path=$link_target', launcher)
        self.assertIn('script_path=$(dirname "$script_path")/$link_target', launcher)
        self.assertIn('link_limit=$((link_limit - 1))', launcher)
        self.assertIn(
            'script_dir=$(CDPATH= cd -P "$(dirname "$script_path")" && pwd)',
            launcher,
        )
        self.assertIn("exec python3 - \"$project_root\" \"$port\" <<'PY'", launcher)
        self.assertNotIn("serve.py", launcher)

    def test_launcher_is_loopback_only_and_opens_common_by_default(self) -> None:
        launcher = LAUNCHER_PATH.read_text(encoding="utf-8")
        self.assertIn('port=${1:-8000}', launcher)
        self.assertIn('ThreadingHTTPServer(("127.0.0.1", port), Handler)', launcher)
        self.assertIn('/common/"', launcher)
        self.assertNotIn("allow-non-loopback", launcher)

    def test_launcher_refuses_missing_tree_and_prevents_symlink_escape(self) -> None:
        launcher = LAUNCHER_PATH.read_text(encoding="utf-8")
        self.assertIn("Specification tree is missing", launcher)
        self.assertIn("specification_root.relative_to(project_root)", launcher)
        self.assertIn("candidate.relative_to(specification_root)", launcher)

    def test_packaged_assets_faithfully_copy_the_existing_common_shell(self) -> None:
        for name in ("index.html", "styles.css", "app.js"):
            self.assertEqual(
                (COMMON_ROOT / name).read_bytes(),
                (ASSET_ROOT / name).read_bytes(),
            )

    def test_primary_sidebar_hosts_the_selected_activity_view(self) -> None:
        html = (ASSET_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("data-sidebar-host", html)
        self.assertIn('data-sidebar-view="explorer"', html)
        self.assertIn('role="tree"', html)
        self.assertNotIn("목차", html)

    def test_init_requires_force_before_replacing_a_changed_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            asset_root = project_root / "packaged"
            asset_root.mkdir()
            (asset_root / "index.html").write_text("packaged", encoding="utf-8")
            installed = (
                project_root
                / ".agent-factory"
                / "specification"
                / "common"
                / "index.html"
            )
            installed.parent.mkdir(parents=True)
            installed.write_text("project change", encoding="utf-8")

            with self.assertRaises(SERVER.ViewerError):
                SERVER.install_assets(project_root, asset_root, force=False)
            self.assertEqual("project change", installed.read_text(encoding="utf-8"))

            copied, unchanged, _launcher_installed = SERVER.install_assets(
                project_root, asset_root, force=True
            )
            self.assertEqual((1, 0), (copied, unchanged))
            self.assertEqual("packaged", installed.read_text(encoding="utf-8"))

    def test_init_copies_launcher_once_with_executable_mode_and_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            asset_root = project_root / "packaged-assets"
            asset_root.mkdir()
            (asset_root / "index.html").write_text("asset", encoding="utf-8")
            launcher_source = project_root / "packaged-spec.sh"
            launcher_source.write_text("packaged launcher", encoding="utf-8")

            _copied, _unchanged, installed = SERVER.install_assets(
                project_root, asset_root, False, launcher_source
            )
            root_launcher = project_root / "spec.sh"
            self.assertTrue(installed)
            self.assertEqual("packaged launcher", root_launcher.read_text(encoding="utf-8"))
            self.assertEqual(0o755, stat.S_IMODE(root_launcher.stat().st_mode))

            root_launcher.write_text("project launcher", encoding="utf-8")
            os.chmod(root_launcher, 0o600)
            _copied, _unchanged, installed = SERVER.install_assets(
                project_root, asset_root, True, launcher_source
            )
            self.assertFalse(installed)
            self.assertEqual("project launcher", root_launcher.read_text(encoding="utf-8"))
            self.assertEqual(0o600, stat.S_IMODE(root_launcher.stat().st_mode))

    def test_launcher_and_asset_conflicts_are_preflighted_before_any_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            asset_root = project_root / "packaged-assets"
            asset_root.mkdir()
            (asset_root / "index.html").write_text("packaged", encoding="utf-8")
            launcher_source = project_root / "packaged-spec.sh"
            launcher_source.write_text("launcher", encoding="utf-8")
            installed_asset = (
                project_root / SERVER.SPECIFICATION_RELATIVE_PATH / "common" / "index.html"
            )
            installed_asset.parent.mkdir(parents=True)
            installed_asset.write_text("conflict", encoding="utf-8")

            with self.assertRaises(SERVER.ViewerError):
                SERVER.install_assets(project_root, asset_root, False, launcher_source)
            self.assertFalse((project_root / "spec.sh").exists())

    def test_request_path_rejects_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            served_root = Path(temporary_directory)
            for target in ("/../outside", "/%2e%2e/outside", "//outside"):
                with self.subTest(target=target):
                    with self.assertRaises(SERVER.ViewerError):
                        SERVER.resolve_request_path(served_root, target)

    def test_request_path_rejects_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            served_root = workspace / "served"
            outside = workspace / "outside"
            served_root.mkdir()
            outside.mkdir()
            try:
                os.symlink(outside, served_root / "escape")
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")

            with self.assertRaises(SERVER.ViewerError):
                SERVER.resolve_request_path(served_root, "/escape/file.html")

    def test_non_loopback_hosts_require_the_explicit_override_contract(self) -> None:
        parser = SERVER.build_parser()
        args = parser.parse_args(["serve", "--host", "0.0.0.0"])
        self.assertFalse(args.allow_non_loopback)
        args = parser.parse_args(
            ["serve", "--host", "0.0.0.0", "--allow-non-loopback"]
        )
        self.assertTrue(args.allow_non_loopback)

    def test_serve_validates_and_binds_one_resolved_address_collection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            (project_root / SERVER.SPECIFICATION_RELATIVE_PATH).mkdir(parents=True)
            addresses = [(SERVER.socket.AF_INET, ("127.0.0.1", 8000))]

            with (
                mock.patch.object(
                    SERVER, "_resolved_addresses", return_value=addresses
                ) as resolve,
                mock.patch.object(
                    SERVER.ThreadingHTTPServer, "__init__", return_value=None
                ) as initialize,
                mock.patch.object(
                    SERVER.ThreadingHTTPServer,
                    "server_address",
                    ("127.0.0.1", 8000),
                    create=True,
                ),
                mock.patch.object(
                    SERVER.ThreadingHTTPServer,
                    "serve_forever",
                    side_effect=KeyboardInterrupt,
                ),
                mock.patch.object(SERVER.ThreadingHTTPServer, "server_close"),
            ):
                SERVER.serve(project_root, "localhost", 8000, False, False)

            resolve.assert_called_once_with("localhost", 8000)
            self.assertEqual(addresses[0][1], initialize.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
def test_spec_launcher_named_port_contract() -> None:
    from pathlib import Path

    launcher = (
        Path(__file__).parents[1]
        / "skills"
        / "specification"
        / "assets"
        / "spec.sh"
    ).read_text(encoding="utf-8")

    assert "port=8000" in launcher
    assert "-p|--port)" in launcher
    assert "-h|--help)" in launcher
    assert 'if [ "$#" -lt 2 ]' in launcher
    assert "case $2 in" in launcher
    assert "-[0-9]*) ;;" in launcher
    assert "-*)" in launcher
    assert "*)" in launcher
    assert "usage >&2" in launcher
    assert "exit 0" in launcher
    assert "exit 2" in launcher
    assert "set -- \"$port\"" in launcher
