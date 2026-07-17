import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const reportRoot = path.dirname(fileURLToPath(import.meta.url));
const designRoot = path.resolve(reportRoot, "..");
const repositoryRoot = path.resolve(designRoot, "../../..");
const manifestPath = path.join(designRoot, "data/manifest.json");
const outputPath = path.join(reportRoot, "design-document-data.js");

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function buildPayload() {
  const manifest = readJson(manifestPath);
  const sections = Object.fromEntries(
    manifest.sections.map((section) => [section.id, readJson(path.join(designRoot, section.path))])
  );
  const collections = Object.fromEntries(
    Object.entries(manifest.collections).map(([name, collectionPath]) => [name, readJson(path.join(designRoot, collectionPath))])
  );
  const diagrams = collections.diagrams.items.map((diagram) => readJson(path.join(designRoot, diagram.source)));
  const workUnit = readJson(path.join(repositoryRoot, manifest.sourceWorkUnit.path));

  if (!sections["project-core"] || !sections["requirements"] || !sections["ui-structure"] || !sections["governance-and-verification"]) {
    throw new Error("manifest must reference every required Design Document section");
  }

  return {
    generatedFrom: {
      manifest: "data/manifest.json",
      sections: manifest.sections.map((section) => section.path),
      collections: Object.values(manifest.collections),
      diagrams: collections.diagrams.items.map((diagram) => diagram.source),
      workUnit: manifest.sourceWorkUnit.path
    },
    manifest,
    sections,
    collections,
    diagrams,
    workUnitSummary: {
      id: workUnit.id,
      title: workUnit.title
    },
    workUnitReview: {
      acceptanceCriteria: workUnit.acceptanceCriteria,
      definitionOfDone: workUnit.definitionOfDone,
      testCriteria: workUnit.testCriteria,
      aiChecklist: workUnit.aiChecklist,
      humanChecklist: workUnit.humanChecklist,
      humanReviewMethod: workUnit.humanReviewMethod
    },
    projectionCoverage: {
      projectCore: "sections/project-core",
      requirements: "sections/requirements",
      uiStructure: "sections/ui-structure",
      governance: "sections/governance-and-verification",
      decisions: "collections/decisions",
      diagramMetadata: "collections/diagrams",
      baseline: "collections/snapshots",
      changeHistory: "collections/events",
      diagrams: "diagrams",
      workUnitReview: "workUnitReview"
    }
  };
}

function render(payload) {
  return `"use strict";\n\n// Generated from Design Document JSON. Do not edit by hand.\nglobalThis.__VSCODE_EXTENSION_UI_STRUCTURE_REPORT_DATA__ = Object.freeze(${JSON.stringify(payload, null, 2)});\n`;
}

const expected = render(buildPayload());
const mode = process.argv[2] ?? "--verify";

if (mode === "--write") {
  fs.writeFileSync(outputPath, expected, "utf8");
  console.log(`WROTE ${path.relative(process.cwd(), outputPath)}`);
} else if (mode === "--verify") {
  const actual = fs.readFileSync(outputPath, "utf8");
  if (actual !== expected) {
    throw new Error("report/design-document-data.js is stale; run generate-report-data.mjs --write");
  }
  console.log("PASS report data matches manifest and section JSON");
} else {
  throw new Error(`unsupported mode: ${mode}`);
}
