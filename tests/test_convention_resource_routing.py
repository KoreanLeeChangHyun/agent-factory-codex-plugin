from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONVENTION = ROOT / "skills" / "convention"
DIAGRAM_INDEX = CONVENTION / "references" / "diagrams.md"
RETIRED_DIAGRAM_RESOURCE = "agent-factory-core-diagrams.md"


class ConventionResourceRoutingTests(unittest.TestCase):
    def test_diagram_index_routes_to_each_focused_resource(self) -> None:
        content = DIAGRAM_INDEX.read_text(encoding="utf-8")
        routes = set(re.findall(r"`(diagrams/(?:erd|behavior|sequence)\.md)`", content))
        self.assertEqual(
            {"diagrams/erd.md", "diagrams/behavior.md", "diagrams/sequence.md"},
            routes,
        )
        for route in routes:
            with self.subTest(route=route):
                self.assertTrue((DIAGRAM_INDEX.parent / route).is_file())

    def test_active_contracts_do_not_route_to_retired_diagram_resource(self) -> None:
        active_contracts = [ROOT / "AGENTS.md"]
        active_contracts.extend(
            path
            for path in (ROOT / "skills").rglob("*.md")
            if path.is_file()
        )
        for contract in active_contracts:
            with self.subTest(contract=contract.relative_to(ROOT)):
                self.assertNotIn(
                    RETIRED_DIAGRAM_RESOURCE,
                    contract.read_text(encoding="utf-8"),
                )

    def test_common_index_remains_the_core_diagram_source_owner(self) -> None:
        content = DIAGRAM_INDEX.read_text(encoding="utf-8")
        self.assertIn("## Agent Factory core sources", content)
        self.assertIn("## Document types", content)
        self.assertIn("## Core capability topology", content)
        self.assertFalse((DIAGRAM_INDEX.parent / RETIRED_DIAGRAM_RESOURCE).exists())


if __name__ == "__main__":
    unittest.main()
