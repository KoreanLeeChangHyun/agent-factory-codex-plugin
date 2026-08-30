from __future__ import annotations

import importlib.util
import functools
import http.client
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import unittest
from unittest import mock
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "skills" / "workspace" / "scripts" / "serve.py"
LAUNCHER_PATH = ROOT / "skills" / "workspace" / "assets" / "workspace.sh"
ASSET_ROOT = ROOT / "skills" / "workspace" / "assets" / "browser"
COMMON_ROOT = ROOT / ".agent-factory" / "workspace" / "common"
PACKAGED_BROWSER_ASSETS = (
    Path("index.html"),
    Path("styles.css"),
    Path("app.js"),
    Path("THIRD_PARTY_NOTICES.txt"),
    Path("vendor/tabulator/6.5.2/tabulator.min.js"),
    Path("vendor/tabulator/6.5.2/tabulator.min.css"),
    Path("vendor/tabulator/6.5.2/LICENSE"),
)
ORIGINAL_SEARCH_COLUMNS = (
    "문서 분류",
    "출처",
    "태그",
    "문서 이름",
    "확장자",
    "수정 일자",
)

SPEC = importlib.util.spec_from_file_location("workspace_serve", SERVER_PATH)
assert SPEC is not None and SPEC.loader is not None
SERVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SERVER)


class WorkspaceBrowserServerTests(unittest.TestCase):
    @staticmethod
    def _tree_names(nodes: list[dict[str, object]]) -> set[str]:
        names: set[str] = set()
        for node in nodes:
            names.add(str(node["name"]))
            names.update(
                WorkspaceBrowserServerTests._tree_names(
                    node.get("children", [])  # type: ignore[arg-type]
                )
            )
        return names

    @staticmethod
    def _create_servable_workspace(project_root: Path) -> Path:
        workspace_root = project_root / SERVER.WORKSPACE_RELATIVE_PATH
        for activity in ("common", *SERVER.ACTIVITY_DIRECTORIES):
            (workspace_root / activity).mkdir(parents=True, exist_ok=True)
        (project_root / SERVER.HUMAN_SPECIFICATION_RELATIVE_PATH).mkdir(
            parents=True
        )
        return workspace_root

    def test_launchers_have_exact_paths_regular_files_identical_and_executable(self) -> None:
        root_launcher = ROOT / "workspace.sh"
        for launcher_path in (LAUNCHER_PATH, root_launcher):
            with self.subTest(launcher=launcher_path):
                self.assertTrue(launcher_path.is_file())
                self.assertFalse(launcher_path.is_symlink())
                self.assertTrue(launcher_path.stat().st_mode & stat.S_IXUSR)
                self.assertTrue(os.access(launcher_path, os.X_OK))
        self.assertEqual(LAUNCHER_PATH.read_bytes(), root_launcher.read_bytes())

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
        self.assertIn('ThreadingHTTPServer(("127.0.0.1", 0), Handler)', launcher)
        self.assertIn("candidate.server_address[1] != forbidden_port", launcher)
        self.assertIn("publish_port_state(server.server_address[1])", launcher)
        self.assertIn('/common/"', launcher)
        self.assertNotIn("allow-non-loopback", launcher)

    def test_launcher_accepts_named_port_and_rejects_invalid_arguments(self) -> None:
        launcher = LAUNCHER_PATH.read_text(encoding="utf-8")
        for contract in (
            "port=",
            "-p|--port)",
            "-h|--help)",
            'if [ "$#" -lt 2 ]',
            "case $2 in",
            "-[0-9]*) ;;",
            "-*)",
            "*)",
            "usage >&2",
            "exit 0",
            "exit 2",
            "port 8000 is reserved and cannot be used",
            'exec python3 - "$project_root" "$port"',
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, launcher)

    def test_launcher_refuses_missing_tree_and_prevents_symlink_escape(self) -> None:
        launcher = LAUNCHER_PATH.read_text(encoding="utf-8")
        self.assertIn("Workspace tree is missing", launcher)
        self.assertIn("workspace_root.relative_to(project_root)", launcher)
        self.assertIn("candidate.relative_to(root)", launcher)

    def test_packaged_assets_faithfully_copy_the_existing_common_shell(self) -> None:
        self.assertEqual(
            set(PACKAGED_BROWSER_ASSETS), SERVER.PACKAGED_BROWSER_ASSET_PATHS
        )
        for relative_path in PACKAGED_BROWSER_ASSETS:
            self.assertEqual(
                (COMMON_ROOT / relative_path).read_bytes(),
                (ASSET_ROOT / relative_path).read_bytes(),
            )
        for root in (ASSET_ROOT, COMMON_ROOT):
            script = (root / "app.js").read_text(encoding="utf-8")
            self.assertNotIn('fetch("/api/explorer-tree"', script)
            self.assertNotIn('fetch("/api/project-skills"', script)

    def test_primary_sidebar_hosts_the_selected_activity_view(self) -> None:
        html = (ASSET_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("data-sidebar-host", html)
        self.assertEqual(SERVER.ACTIVITY_DIRECTORIES, ("explorer", "skills"))
        activities = (
            ("schedule", "일정"),
            ("agents", "에이전트"),
            ("documents", "문서"),
            ("logs", "로그"),
            ("tests", "테스트"),
        )
        positions = []
        for activity, label in activities:
            self.assertIn(f'data-activity="{activity}"', html)
            self.assertIn(f'aria-label="{label}"', html)
            self.assertIn(f'data-sidebar-view="{activity}"', html)
            self.assertIn(f'data-workspace-view="{activity}"', html)
            positions.append(html.index(f'data-activity="{activity}"'))
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(html.count('data-activity="'), 5)
        self.assertGreaterEqual(html.count("정의 대기"), 8)
        self.assertNotIn('data-activity="roadmap"', html)
        self.assertNotIn('data-activity="explorer"', html)
        self.assertNotIn('data-activity="skills"', html)
        self.assertNotIn('data-activity="planning"', html)
        self.assertNotIn('role="tree"', html)
        self.assertNotIn("목차", html)

    def test_document_sidebar_has_decided_groups_and_navigation(self) -> None:
        html = (ASSET_ROOT / "index.html").read_text(encoding="utf-8")
        group_labels = (
            '<span id="original-group-label">원본문서</span>',
            '<span id="processed-group-label">가공문서</span>',
            '<span id="specification-group-label">스펙문서</span>',
        )
        positions = [html.index(label) for label in group_labels]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(3, html.count("data-document-group-toggle"))
        self.assertEqual(3, html.count('aria-expanded="true"'))
        self.assertIn('aria-label="원본문서 보기"', html)
        self.assertIn('data-document-target="original-overview">개요</a>', html)
        self.assertIn('data-document-target="original-search">문서검색</a>', html)
        self.assertIn('aria-label="가공문서 보기"', html)
        self.assertIn('data-document-target="processed-overview">개요</a>', html)
        self.assertIn('aria-label="스펙문서 보기"', html)
        self.assertIn('data-document-target="specification-overview">개요</a>', html)
        self.assertNotIn("스펙 문서 보기", html)

        document_sidebar_start = html.index(
            '<div class="sidebar-view document-sidebar"'
        )
        document_sidebar_end = html.index(
            '</div>\n          <div class="sidebar-view oversight-sidebar" '
            'data-sidebar-view="logs"',
            document_sidebar_start,
        )
        document_sidebar = html[document_sidebar_start:document_sidebar_end]
        self.assertEqual(2, document_sidebar.count('role="region"'))
        self.assertEqual(0, document_sidebar.count('role="treeitem"'))
        self.assertEqual(2, document_sidebar.count("aria-describedby="))
        self.assertIn('id="processed-tree-state"', document_sidebar)
        self.assertIn('id="specification-tree-state"', document_sidebar)
        self.assertEqual(
            2,
            document_sidebar.count("문서 연결 방식은 Human 결정을 기다리고 있습니다"),
        )
        self.assertNotIn("legacy-inquery", document_sidebar)
        self.assertNotIn("notes.md", document_sidebar)

    def test_original_document_views_have_compact_overview_and_search_shapes(self) -> None:
        html = (ASSET_ROOT / "index.html").read_text(encoding="utf-8")
        search_start = html.index('id="document-original-search"')
        search_end = html.index('</article>', search_start)
        search_view = html[search_start:search_end]
        overview_start = html.index('id="document-original-overview"')
        overview_end = html.index('</article>', overview_start)
        overview_view = html[overview_start:overview_end]
        for original_view in (overview_view, search_view):
            self.assertNotIn('class="editor-header"', original_view)
            self.assertNotIn('class="editor-header__tab"', original_view)
        self.assertIn("<table", search_view)
        self.assertIn("<caption>", search_view)
        heading_positions = [
            search_view.index(f'<th scope="col">{heading}</th>')
            for heading in ORIGINAL_SEARCH_COLUMNS
        ]
        self.assertEqual(heading_positions, sorted(heading_positions))
        self.assertEqual(6, search_view.count('<th scope="col">'))
        self.assertIn('type="search"', search_view)
        self.assertIn('data-original-global-search', search_view)
        self.assertIn('disabled data-original-global-search', search_view)
        self.assertIn('data-original-table-fallback', search_view)
        self.assertIn('data-original-table', search_view)
        self.assertNotIn(
            "원본문서 본문을 변경하거나 복제하지 않는 메타데이터·출처 링크 보기입니다.",
            search_view,
        )
        self.assertNotIn("<select", search_view)
        self.assertNotIn("<button", search_view)
        self.assertIn("데이터 연결 대기", search_view)

    def test_document_views_start_visible_with_plain_overview_styling(self) -> None:
        html = (ASSET_ROOT / "index.html").read_text(encoding="utf-8")
        document_view_openings = [
            line.strip()
            for line in html.splitlines()
            if "data-document-view=" in line
        ]
        self.assertEqual(4, len(document_view_openings))
        self.assertTrue(
            all(" hidden" not in opening for opening in document_view_openings)
        )
        self.assertIn(
            'class="activity-button is-active" type="button" '
            'aria-label="문서" aria-pressed="true"',
            html,
        )

        styles = (ASSET_ROOT / "styles.css").read_text(encoding="utf-8")
        self.assertIn("--primary-sidebar-width: 252px", styles)
        self.assertIn(".document-group__toggle", styles)
        self.assertIn("height: 22px", styles)
        self.assertIn(".document-navigation:focus-within", styles)
        self.assertIn(".editor-header__tab", styles)
        self.assertEqual(2, html.count('class="editor-header__tab"'))
        self.assertIn("가공문서 / 개요", html)
        self.assertIn("스펙문서 / 개요", html)
        self.assertIn(".document-view__canvas", styles)
        self.assertNotIn("linear-gradient", styles)
        self.assertNotIn("box-shadow", styles)

    def test_document_separators_preserve_internal_borders_and_omit_terminal_divider(
        self,
    ) -> None:
        styles = (ASSET_ROOT / "styles.css").read_text(encoding="utf-8")
        self.assertIn(
            ".document-group {\n  border-bottom: 1px solid var(--region-border);\n}",
            styles,
        )
        self.assertIn(
            ".document-sidebar > .document-group:last-child {\n"
            "  border-bottom: 0;\n}",
            styles,
        )
        self.assertIn(
            ".primary-sidebar {\n  min-width: 0;\n  overflow: auto;\n"
            "  background: var(--primary-sidebar-background);\n"
            "  border-right: 1px solid var(--region-border);",
            styles,
        )
        self.assertIn(
            ".original-search .tabulator .tabulator-header {\n"
            "  border-bottom: 1px solid #3c3c3c;",
            styles,
        )

    def test_document_group_icons_are_decorative_svg_and_controls_are_named(self) -> None:
        html = (ASSET_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertEqual(3, html.count("data-document-group-toggle"))
        for label_id, label in (
            ("original-group-label", "원본문서"),
            ("processed-group-label", "가공문서"),
            ("specification-group-label", "스펙문서"),
        ):
            label_position = html.index(f'<span id="{label_id}">{label}</span>')
            toggle_start = html.rfind(
                '<button class="document-group__toggle"', 0, label_position
            )
            toggle_end = html.index("</button>", label_position)
            self.assertGreaterEqual(toggle_start, 0)
            toggle = html[toggle_start:toggle_end]
            self.assertIn('type="button"', toggle)
            self.assertIn('aria-expanded="true"', toggle)
            self.assertIn("<svg", toggle)
            self.assertIn('aria-hidden="true"', toggle)
            self.assertIn('focusable="false"', toggle)

    def test_only_original_document_views_use_the_compact_workspace_inset(self) -> None:
        styles = (ASSET_ROOT / "styles.css").read_text(encoding="utf-8")
        compact_rule = """.document-view[data-document-view="original-overview"] .document-view__canvas,
.document-view[data-document-view="original-search"] .document-view__canvas {
  max-width: none;
  padding: var(--compact-workspace-inset);
}"""
        self.assertIn("--compact-workspace-inset: 12px", styles)
        self.assertEqual(1, styles.count(compact_rule))
        self.assertNotIn(
            'data-document-view="processed-overview"] .document-view__canvas',
            styles,
        )
        self.assertNotIn(
            'data-document-view="specification-overview"] .document-view__canvas',
            styles,
        )
        self.assertIn(
            "padding: 24px clamp(24px, 5vw, 56px) 40px",
            styles,
        )

    def test_activity_icons_are_distinct_accessible_inline_svg(self) -> None:
        html = (ASSET_ROOT / "index.html").read_text(encoding="utf-8")
        nav_start = html.index('<nav class="activity-bar"')
        nav_end = html.index("</nav>", nav_start) + len("</nav>")
        activity_bar = ET.fromstring(html[nav_start:nav_end])
        buttons = activity_bar.findall("./button")
        expected = (
            ("schedule", "일정"),
            ("agents", "에이전트"),
            ("documents", "문서"),
            ("logs", "로그"),
            ("tests", "테스트"),
        )

        signatures = []
        icons_by_activity = {}
        for button, (activity, label) in zip(buttons, expected, strict=True):
            self.assertEqual(activity, button.attrib["data-activity"])
            self.assertEqual(label, button.attrib["aria-label"])
            self.assertEqual("", "".join(button.itertext()).strip())

            svg = button.find("svg")
            self.assertIsNotNone(svg)
            assert svg is not None
            self.assertEqual("0 0 24 24", svg.attrib["viewBox"])
            self.assertEqual("true", svg.attrib["aria-hidden"])
            self.assertEqual("false", svg.attrib["focusable"])
            icons_by_activity[activity] = svg

            elements = tuple(svg.iter())[1:]
            self.assertTrue(elements)
            self.assertFalse(
                {"text", "image", "foreignObject"}
                & {element.tag for element in elements}
            )
            signatures.append(
                tuple(
                    (element.tag, tuple(sorted(element.attrib.items())))
                    for element in elements
                )
            )

        self.assertEqual(len(expected), len(buttons))
        self.assertEqual(len(expected), len(set(signatures)))
        self.assertNotIn("<img", html[nav_start:nav_end].lower())

        document_tags = tuple(
            element.tag for element in tuple(icons_by_activity["documents"].iter())[1:]
        )
        log_icon = icons_by_activity["logs"]
        log_tags = tuple(element.tag for element in tuple(log_icon.iter())[1:])
        self.assertNotIn("rect", document_tags)
        self.assertEqual(["path", "path"], [child.tag for child in log_icon])
        document_path_data = {
            child.attrib["d"]
            for child in icons_by_activity["documents"]
            if child.tag == "path"
        }
        log_path_data = {child.attrib["d"] for child in log_icon}
        self.assertNotEqual(document_path_data, log_path_data)
        self.assertEqual(
            {"M12 8l0 4l2 2", "M3.05 11a9 9 0 1 1 .5 4m-.5 5v-5h5"},
            log_path_data,
        )
        self.assertNotIn("g", log_tags)
        self.assertNotIn("rect", log_tags)
        self.assertNotIn("polyline", log_tags)
        self.assertNotIn("circle", log_tags)
        self.assertIn("Tabler History", html)
        self.assertIn("THIRD_PARTY_NOTICES.txt", html)
        self.assertNotIn("Lucide", html)

        notice = (ASSET_ROOT / "THIRD_PARTY_NOTICES.txt").read_text(
            encoding="utf-8"
        )
        normalized_notice = " ".join(notice.split())
        for required_notice_text in (
            "Copyright (c) 2020-2026 Paweł Kuna",
            "Permission is hereby granted, free of charge",
            "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell",
            "this permission notice shall be included in all",
            'THE SOFTWARE IS PROVIDED "AS IS"',
            "WITHOUT WARRANTY OF ANY KIND",
            "IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE",
            "https://tabler.io/icons/icon/history",
            "https://github.com/tabler/tabler-icons/blob/main/LICENSE",
            "Tabulator 6.5.2",
            "https://registry.npmjs.org/tabulator-tables/-/tabulator-tables-6.5.2.tgz",
            "Copyright (c) 2015-2026 Oli Folkerd",
            "vendor/tabulator/6.5.2/tabulator.min.js",
            "vendor/tabulator/6.5.2/tabulator.min.css",
        ):
            self.assertIn(required_notice_text, normalized_notice)
        self.assertNotIn("Lucide", normalized_notice)
        self.assertNotIn("ISC License", normalized_notice)

        styles = (ASSET_ROOT / "styles.css").read_text(encoding="utf-8")
        self.assertIn(".activity-button:focus-visible", styles)
        self.assertIn(".activity-button.is-active", styles)
        self.assertIn("stroke: currentColor", styles)
        self.assertNotIn(".activity-button::before", styles)
        self.assertNotIn(".activity-button::after", styles)
        forbidden_assets = ("icon-font", ".png", ".jpg", ".jpeg", ".gif", ".webp")
        for forbidden in forbidden_assets:
            self.assertNotIn(forbidden, styles.lower())

    def test_activity_behavior_switches_sidebar_and_workspace_context(self) -> None:
        script = (ASSET_ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn("const selectActivity", script)
        self.assertIn('button.setAttribute("aria-pressed", String(isActive))', script)
        self.assertIn("view.dataset.sidebarView !== activity", script)
        self.assertIn("view.dataset.workspaceView !== activity", script)
        self.assertIn("sidebarTitle.textContent = activityTitles[activity]", script)
        self.assertIn('schedule: "일정"', script)
        self.assertIn('agents: "에이전트"', script)
        self.assertIn('tests: "테스트"', script)
        self.assertNotIn("roadmap:", script)
        self.assertNotIn("explorer:", script)
        self.assertNotIn("skills:", script)
        self.assertNotIn("fetch(", script)
        self.assertIn("const selectDocumentView", script)
        self.assertIn('item.setAttribute("aria-current", "page")', script)
        self.assertIn("view.hidden = view !== nextView", script)
        self.assertIn('toggle.setAttribute("aria-expanded", String(!isExpanded))', script)
        self.assertIn("content.hidden = isExpanded", script)
        self.assertIn('selectDocumentView("original-overview")', script)
        self.assertIn("initializeOriginalSearch();", script)

    def test_original_search_uses_pinned_local_tabulator_and_safe_read_only_adapter(self) -> None:
        html = (ASSET_ROOT / "index.html").read_text(encoding="utf-8")
        script = (ASSET_ROOT / "app.js").read_text(encoding="utf-8")
        styles = (ASSET_ROOT / "styles.css").read_text(encoding="utf-8")
        self.assertIn('./vendor/tabulator/6.5.2/tabulator.min.css', html)
        self.assertIn('./vendor/tabulator/6.5.2/tabulator.min.js', html)
        self.assertNotIn("unpkg.com", html)
        self.assertNotIn("cdn", html.lower())
        for title in ORIGINAL_SEARCH_COLUMNS:
            self.assertIn(f'title: "{title}"', script)
        self.assertEqual(3, script.count("...listFilter"))
        self.assertEqual(3, script.count("...textFilter"))
        self.assertIn("movableColumns: true", script)
        self.assertIn('layout: "fitColumns"', script)
        self.assertEqual(6, script.count("widthGrow:"))
        self.assertIn('field: "name", minWidth: 220, widthGrow: 2', script)
        self.assertIn("resizable: true", script)
        self.assertIn(".document-table-wrap {\n  margin-top: 8px;\n  overflow-x: auto;", styles)
        self.assertIn(".original-search .tabulator {\n  min-width: 900px;", styles)
        self.assertIn("document.createElement(\"a\")", script)
        self.assertIn("link.textContent = name", script)
        self.assertIn('resolved.protocol === "http:" || resolved.protocol === "https:"', script)
        self.assertIn('link.rel = "noopener noreferrer"', script)
        self.assertIn('icon.setAttribute("aria-hidden", "true")', script)
        self.assertIn('icon.setAttribute("focusable", "false")', script)
        self.assertIn("window.agentFactoryWorkspace.originalSearch.replaceRows(rows)", script)
        self.assertNotIn("fetch(", script)

    def test_explorer_projection_separates_project_and_classified_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            (project_root / "src").mkdir()
            (project_root / "src" / "main.py").write_text("private contents", encoding="utf-8")
            documents = project_root / SERVER.DOCUMENT_RELATIVE_PATH
            original = documents / "original" / "research-1"
            processed = documents / "processed"
            original.mkdir(parents=True)
            processed.mkdir(parents=True)
            (original / "source.bin").write_bytes(b"source contents")
            (processed / "notes.md").write_text("derived contents", encoding="utf-8")
            agent_runtime = project_root / ".agent-factory" / "agent" / "session"
            agent_runtime.mkdir(parents=True)
            (agent_runtime / "secret.json").write_text("runtime", encoding="utf-8")
            git_root = project_root / ".git"
            git_root.mkdir()
            (git_root / "config").write_text("sensitive", encoding="utf-8")
            codex_root = project_root / ".codex"
            codex_root.mkdir()
            (codex_root / "config.toml").write_text("control", encoding="utf-8")

            payload = SERVER.discover_explorer_trees(project_root)
            project_tree, document_tree = payload["trees"]
            self.assertEqual(("project", "evidence"), (project_tree["role"], document_tree["role"]))
            self.assertIn("main.py", self._tree_names(project_tree["children"]))
            self.assertNotIn("secret.json", self._tree_names(project_tree["children"]))
            self.assertNotIn("config", self._tree_names(project_tree["children"]))
            self.assertNotIn("config.toml", self._tree_names(project_tree["children"]))
            document_names = self._tree_names(document_tree["children"])
            self.assertIn("source.bin", document_names)
            self.assertIn("notes.md", document_names)
            serialized = json.dumps(payload, ensure_ascii=False)
            self.assertNotIn("private contents", serialized)
            self.assertNotIn("source contents", serialized)
            self.assertNotIn("derived contents", serialized)

    def test_explorer_projection_skips_symlinks_and_reports_missing_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            outside = project_root.parent / f"{project_root.name}-outside"
            outside.mkdir()
            try:
                os.symlink(outside, project_root / "escape")
            except OSError as exc:
                outside.rmdir()
                self.skipTest(f"symlinks unavailable: {exc}")
            try:
                payload = SERVER.discover_explorer_trees(project_root)
                project_tree, document_tree = payload["trees"]
                self.assertNotIn("escape", self._tree_names(project_tree["children"]))
                self.assertEqual("missing", document_tree["state"])
            finally:
                (project_root / "escape").unlink()
                outside.rmdir()

    def test_explorer_projection_rejects_document_root_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            outside = project_root.parent / f"{project_root.name}-document-outside"
            outside.mkdir()
            (outside / "secret.md").write_text("not visible", encoding="utf-8")
            document_path = project_root / SERVER.DOCUMENT_RELATIVE_PATH
            document_path.parent.mkdir(parents=True)
            try:
                os.symlink(outside, document_path)
            except OSError as exc:
                (outside / "secret.md").unlink()
                outside.rmdir()
                self.skipTest(f"symlinks unavailable: {exc}")
            try:
                document_tree = SERVER.discover_explorer_trees(project_root)["trees"][1]
                self.assertEqual("error", document_tree["state"])
                self.assertEqual([], document_tree["children"])
            finally:
                document_path.unlink()
                (outside / "secret.md").unlink()
                outside.rmdir()

    def test_explorer_projection_has_deterministic_entry_and_response_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            for index in range(12):
                (project_root / f"file-{index:02d}.txt").write_text("x", encoding="utf-8")
            with mock.patch.object(SERVER, "TREE_MAX_ENTRIES", 4):
                payload = SERVER.discover_explorer_trees(project_root)
            project_tree = payload["trees"][0]
            self.assertLessEqual(len(self._tree_names(project_tree["children"])), 4)
            self.assertTrue(payload["truncated"])
            self.assertLessEqual(len(SERVER._json_response_bytes(payload)), SERVER.TREE_MAX_RESPONSE_BYTES)
            with mock.patch.object(SERVER, "TREE_MAX_RESPONSE_BYTES", 8):
                with self.assertRaises(SERVER.ViewerError):
                    SERVER._json_response_bytes(payload)

    def test_explorer_tree_api_returns_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            common = project_root / "common"
            common.mkdir()
            (project_root / "visible.txt").write_text("not returned", encoding="utf-8")
            handler = functools.partial(
                SERVER.WorkspaceRequestHandler,
                served_roots={"common": common},
                project_root=project_root,
            )
            server = SERVER.ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1])
                connection.request("GET", "/api/explorer-tree")
                response = connection.getresponse()
                body = response.read()
                connection.close()
                self.assertEqual(200, response.status)
                self.assertEqual("nosniff", response.getheader("X-Content-Type-Options"))
                self.assertIn("visible.txt", body.decode("utf-8"))
                self.assertNotIn("not returned", body.decode("utf-8"))
                self.assertLessEqual(len(body), SERVER.TREE_MAX_RESPONSE_BYTES)
            finally:
                server.shutdown()
                thread.join()
                server.server_close()

    def test_project_skill_discovery_uses_only_actual_direct_skill_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            skill_root = project_root / ".codex" / "skills"
            actual = skill_root / "domain-orders"
            actual.mkdir(parents=True)
            (actual / "SKILL.md").write_text("---\nname: domain-orders\n---\n", encoding="utf-8")
            (skill_root / "not-a-skill").mkdir()
            (skill_root / "loose.md").write_text("ignored", encoding="utf-8")

            self.assertEqual(
                SERVER.discover_project_skills(project_root),
                [
                    {
                        "name": "domain-orders",
                        "href": "/project-skills/domain-orders/SKILL.md",
                    }
                ],
            )

    def test_packaged_and_root_launchers_expose_project_skill_projection(self) -> None:
        for launcher_path in (LAUNCHER_PATH, ROOT / "workspace.sh"):
            with self.subTest(launcher=launcher_path):
                launcher = launcher_path.read_text(encoding="utf-8")
                self.assertIn('project_skills_path = project_root / ".codex" / "skills"', launcher)
                self.assertIn('"/api/project-skills"', launcher)
                self.assertIn('"/api/explorer-tree"', launcher)
                self.assertIn('"project-skills"', launcher)

    def test_init_creates_empty_activity_directories_and_preserves_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            asset_root = project_root / "packaged-assets"
            asset_root.mkdir()
            (asset_root / "index.html").write_text("asset", encoding="utf-8")
            workspace_root = project_root / SERVER.WORKSPACE_RELATIVE_PATH
            existing = workspace_root / "planning"
            existing.mkdir(parents=True)
            preserved = existing / "existing.html"
            preserved.write_text("preserve", encoding="utf-8")

            SERVER.install_assets(project_root, asset_root, False)

            for name in SERVER.ACTIVITY_DIRECTORIES:
                self.assertTrue(
                    (project_root / SERVER.WORKSPACE_RELATIVE_PATH / name).is_dir()
                )
            specification_root = (
                project_root / ".agent-factory" / "document" / "specification"
            )
            self.assertTrue(specification_root.is_dir())
            self.assertFalse((specification_root / "human").exists())
            self.assertEqual("preserve", preserved.read_text(encoding="utf-8"))
            self.assertEqual(
                "/port.json\n",
                (workspace_root / ".gitignore").read_text(encoding="utf-8"),
            )

    def test_init_materializes_packaged_browser_files_byte_identically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)

            SERVER.install_assets(project_root, ASSET_ROOT, False)

            installed_root = (
                project_root / SERVER.WORKSPACE_RELATIVE_PATH / "common"
            )
            for relative_path in PACKAGED_BROWSER_ASSETS:
                self.assertTrue((installed_root / relative_path).is_file())
                self.assertEqual(
                    (ASSET_ROOT / relative_path).read_bytes(),
                    (installed_root / relative_path).read_bytes(),
                )

    def test_normal_init_flow_has_no_catalog_side_effect(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            with (
                mock.patch.object(SERVER, "resolve_project_root", return_value=project_root),
                mock.patch.object(
                    SERVER, "install_assets", return_value=(4, 0, True)
                ) as install_assets,
            ):
                self.assertEqual(0, SERVER.main(["--project-root", str(project_root), "init"]))
            install_assets.assert_called_once_with(project_root, ASSET_ROOT, False)
            self.assertFalse((project_root / ".agent-factory" / "db.sqlite").exists())
            self.assertFalse(hasattr(SERVER, "initialize_catalog"))

    def test_init_rejects_activity_file_conflicts_before_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            asset_root = project_root / "packaged-assets"
            asset_root.mkdir()
            (asset_root / "index.html").write_text("asset", encoding="utf-8")
            workspace_root = project_root / SERVER.WORKSPACE_RELATIVE_PATH
            workspace_root.mkdir(parents=True)
            (workspace_root / "skills").write_text("conflict", encoding="utf-8")

            with self.assertRaises(SERVER.ViewerError):
                SERVER.install_assets(project_root, asset_root, False)

            self.assertFalse((workspace_root / "common").exists())

    def test_init_rejects_activity_symlink_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            asset_root = project_root / "packaged-assets"
            asset_root.mkdir()
            (asset_root / "index.html").write_text("asset", encoding="utf-8")
            workspace_root = project_root / SERVER.WORKSPACE_RELATIVE_PATH
            workspace_root.mkdir(parents=True)
            outside = project_root / "outside"
            outside.mkdir()
            try:
                os.symlink(outside, workspace_root / "skills")
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")

            with self.assertRaises(SERVER.ViewerError):
                SERVER.install_assets(project_root, asset_root, False)

    def test_init_requires_force_before_replacing_a_changed_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            asset_root = project_root / "packaged"
            asset_root.mkdir()
            (asset_root / "index.html").write_text("packaged", encoding="utf-8")
            installed = (
                project_root
                / ".agent-factory"
                / "workspace"
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
            launcher_source = project_root / "packaged-workspace.sh"
            launcher_source.write_text("packaged launcher", encoding="utf-8")

            _copied, _unchanged, installed = SERVER.install_assets(
                project_root, asset_root, False, launcher_source
            )
            root_launcher = project_root / "workspace.sh"
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
            launcher_source = project_root / "packaged-workspace.sh"
            launcher_source.write_text("launcher", encoding="utf-8")
            installed_asset = (
                project_root / SERVER.WORKSPACE_RELATIVE_PATH / "common" / "index.html"
            )
            installed_asset.parent.mkdir(parents=True)
            installed_asset.write_text("conflict", encoding="utf-8")

            with self.assertRaises(SERVER.ViewerError):
                SERVER.install_assets(project_root, asset_root, False, launcher_source)
            self.assertFalse((project_root / "workspace.sh").exists())

    def test_request_path_rejects_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            served_root = Path(temporary_directory)
            served_roots = {"common": served_root}
            for target in (
                "/common/../outside",
                "/common/%2e%2e/outside",
                "//outside",
            ):
                with self.subTest(target=target):
                    with self.assertRaises(SERVER.ViewerError):
                        SERVER.resolve_request_path(served_roots, target)

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
                SERVER.resolve_request_path(
                    {"common": served_root}, "/common/escape/file.html"
                )

    def test_non_loopback_hosts_require_the_explicit_override_contract(self) -> None:
        parser = SERVER.build_parser()
        args = parser.parse_args(["serve", "--host", "0.0.0.0"])
        self.assertFalse(args.allow_non_loopback)
        args = parser.parse_args(
            ["serve", "--host", "0.0.0.0", "--allow-non-loopback"]
        )
        self.assertTrue(args.allow_non_loopback)

    def test_automatic_port_is_persisted_and_reused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            self._create_servable_workspace(project_root)
            with mock.patch.object(
                SERVER.ThreadingHTTPServer,
                "serve_forever",
                side_effect=KeyboardInterrupt,
            ):
                SERVER.serve(project_root, "127.0.0.1", None, False, False)
            state_path = project_root / SERVER.PORT_STATE_RELATIVE_PATH
            first = json.loads(state_path.read_text(encoding="utf-8"))["port"]
            self.assertIn(first, range(1, 65536))
            self.assertNotEqual(SERVER.FORBIDDEN_PORT, first)

            with mock.patch.object(
                SERVER.ThreadingHTTPServer,
                "serve_forever",
                side_effect=KeyboardInterrupt,
            ):
                SERVER.serve(project_root, "127.0.0.1", None, False, False)
            self.assertEqual(
                first,
                json.loads(state_path.read_text(encoding="utf-8"))["port"],
            )

    def test_occupied_saved_port_is_reassigned_after_successful_bind(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            self._create_servable_workspace(project_root)
            blocker = SERVER.socket.socket(
                SERVER.socket.AF_INET, SERVER.socket.SOCK_STREAM
            )
            blocker.bind(("127.0.0.1", 0))
            blocker.listen()
            occupied = blocker.getsockname()[1]
            (project_root / SERVER.PORT_STATE_RELATIVE_PATH).write_text(
                json.dumps(
                    {"version": SERVER.PORT_STATE_VERSION, "port": occupied}
                ),
                encoding="utf-8",
            )
            try:
                with mock.patch.object(
                    SERVER.ThreadingHTTPServer,
                    "serve_forever",
                    side_effect=KeyboardInterrupt,
                ):
                    SERVER.serve(project_root, "127.0.0.1", None, False, False)
            finally:
                blocker.close()
            reassigned = json.loads(
                (project_root / SERVER.PORT_STATE_RELATIVE_PATH).read_text(
                    encoding="utf-8"
                )
            )["port"]
            self.assertNotEqual(occupied, reassigned)
            self.assertNotEqual(SERVER.FORBIDDEN_PORT, reassigned)

    def test_explicit_port_persists_and_8000_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            self._create_servable_workspace(project_root)
            probe = SERVER.socket.socket(
                SERVER.socket.AF_INET, SERVER.socket.SOCK_STREAM
            )
            probe.bind(("127.0.0.1", 0))
            explicit = probe.getsockname()[1]
            probe.close()
            if explicit == SERVER.FORBIDDEN_PORT:
                self.skipTest("operating system selected the reserved port for the probe")
            with mock.patch.object(
                SERVER.ThreadingHTTPServer,
                "serve_forever",
                side_effect=KeyboardInterrupt,
            ):
                SERVER.serve(project_root, "127.0.0.1", explicit, False, False)
            self.assertEqual(explicit, SERVER._read_port_state(project_root))
            with self.assertRaisesRegex(SERVER.ViewerError, "reserved"):
                SERVER.serve(project_root, "127.0.0.1", 8000, False, False)

    def test_port_state_rejects_malformed_and_symlinked_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            state_path = project_root / SERVER.PORT_STATE_RELATIVE_PATH
            state_path.parent.mkdir(parents=True)
            state_path.write_text("not-json", encoding="utf-8")
            with self.assertRaisesRegex(SERVER.ViewerError, "malformed"):
                SERVER._read_port_state(project_root)
            state_path.unlink()
            target = project_root / "state-target.json"
            target.write_text(
                json.dumps(
                    {"version": SERVER.PORT_STATE_VERSION, "port": 9000}
                ),
                encoding="utf-8",
            )
            try:
                os.symlink(target, state_path)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            with self.assertRaisesRegex(SERVER.ViewerError, "regular file"):
                SERVER._read_port_state(project_root)


if __name__ == "__main__":
    unittest.main()
