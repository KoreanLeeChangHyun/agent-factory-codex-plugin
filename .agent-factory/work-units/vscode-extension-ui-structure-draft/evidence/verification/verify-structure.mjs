import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const designRoot = path.join(root, "docs/design-documents/vscode-extension-ui-structure");
const workUnitRoot = path.join(root, "docs/work-units/vscode-extension-ui-structure-draft");
let checks = 0;

function readJson(relativePath) {
  return JSON.parse(fs.readFileSync(path.join(root, relativePath), "utf8"));
}

function check(name, assertion) {
  assertion();
  checks += 1;
  console.log(`PASS ${String(checks).padStart(2, "0")} ${name}`);
}

const manifest = readJson("docs/design-documents/vscode-extension-ui-structure/data/manifest.json");
const designSchema = readJson("docs/design-documents/vscode-extension-ui-structure/data/schema/design-document.schema.json");
const projectCore = readJson("docs/design-documents/vscode-extension-ui-structure/data/sections/project-core.json");
const requirements = readJson("docs/design-documents/vscode-extension-ui-structure/data/sections/requirements.json");
const ui = readJson("docs/design-documents/vscode-extension-ui-structure/data/sections/ui-structure.json");
const governance = readJson("docs/design-documents/vscode-extension-ui-structure/data/sections/governance-and-verification.json");
const decisions = readJson("docs/design-documents/vscode-extension-ui-structure/data/decisions/design-decisions.json");
const diagramMetadata = readJson("docs/design-documents/vscode-extension-ui-structure/data/diagrams/diagram-metadata.json");
const baseline = readJson("docs/design-documents/vscode-extension-ui-structure/data/snapshots/pre-execution-baseline.json");
const changeHistory = readJson("docs/design-documents/vscode-extension-ui-structure/data/events/change-history.json");
const uiDiagram = readJson("docs/design-documents/vscode-extension-ui-structure/diagram/ui-tab-structure.json");
const stateDiagram = readJson("docs/design-documents/vscode-extension-ui-structure/diagram/work-unit-status.json");
const workUnit = readJson("docs/work-units/vscode-extension-ui-structure-draft/data/work-unit.json");
const workUnitSchema = readJson(".codex/skills/work-unit-planner-af/assets/schema/work-unit.schema.json");
const reportHtml = fs.readFileSync(path.join(designRoot, "report/index.html"), "utf8");
const reportCss = fs.readFileSync(path.join(designRoot, "report/styles.css"), "utf8");
const reportScript = fs.readFileSync(path.join(designRoot, "report/script.js"), "utf8");
const reportDataScript = fs.readFileSync(path.join(designRoot, "report/design-document-data.js"), "utf8");
const generatedMatch = reportDataScript.match(/Object\.freeze\(([\s\S]*)\);\s*$/);
assert.ok(generatedMatch);
const generated = JSON.parse(generatedMatch[1]);

check("Design Document의 13개 JSON source가 strict parse", () => {
  const jsonFiles = fs
    .readdirSync(designRoot, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith(".json"))
    .map((entry) => path.relative(designRoot, path.join(entry.parentPath, entry.name)))
    .sort();
  assert.deepEqual(jsonFiles, [
    "data/decisions/design-decisions.json",
    "data/diagrams/diagram-metadata.json",
    "data/events/change-history.json",
    "data/manifest.json",
    "data/schema/design-document.schema.json",
    "data/sections/governance-and-verification.json",
    "data/sections/project-core.json",
    "data/sections/requirements.json",
    "data/sections/ui-structure.json",
    "data/snapshots/pre-execution-baseline.json",
    "diagram/ui-tab-structure.json",
    "diagram/work-unit-status.json",
    "reference/sources.json"
  ]);
  jsonFiles.forEach((relativePath) => JSON.parse(fs.readFileSync(path.join(designRoot, relativePath), "utf8")));
});

check("manifest가 schema, sections, collections, diagrams와 report 경로를 모두 연결", () => {
  assert.equal(manifest.sourceOfTruth, "Design Document JSON");
  assert.equal(manifest.sections[0].id, "project-core");
  const packagePaths = [
    manifest.schema,
    manifest.projectCore,
    ...manifest.sections.map((section) => section.path),
    ...Object.values(manifest.collections),
    ...diagramMetadata.items.map((diagram) => diagram.source),
    manifest.report.index,
    manifest.report.styles,
    manifest.report.script,
    manifest.report.generatedData,
    manifest.report.generator,
    "reference/sources.json"
  ];
  packagePaths.forEach((relativePath) => assert.ok(fs.existsSync(path.join(designRoot, relativePath)), relativePath));
});

check("Draft 2020-12 Design Document schema가 실제 package collection을 계약", () => {
  assert.equal(designSchema.$schema, "https://json-schema.org/draft/2020-12/schema");
  assert.deepEqual(designSchema.required, ["manifest", "sections", "collections", "diagrams", "workUnitSummary", "workUnitReview"]);
  assert.deepEqual(Object.keys(designSchema.properties.collections.properties), ["decisions", "diagrams", "snapshots", "events"]);
});

check("Project Core가 지정된 다섯 의미 영역만 소유", () => {
  assert.deepEqual(
    Object.keys(projectCore).sort(),
    ["corePrinciples", "humanApprovalBoundaries", "id", "purpose", "scope", "title", "unresolvedItems"].sort()
  );
});

check("신규 프로젝트 baseline과 실행 전 Design Document·reference 부재를 snapshot으로 기록", () => {
  assert.equal(requirements.baselineRef, manifest.collections.snapshots);
  assert.equal(baseline.adoptionTiming, "new-project");
  assert.deepEqual(baseline.checks.map((item) => item.result), ["not_found", "not_found"]);
});

check("요구사항 section이 scope·non-goals·stakeholder·품질·완료 경계를 모두 정의", () => {
  assert.ok(requirements.outcome && requirements.completionBoundary);
  assert.ok(requirements.stakeholders.length >= 2);
  assert.ok(requirements.functionalRequirements.length >= 11);
  assert.ok(requirements.nonFunctionalRequirements.length >= 3);
  assert.ok(requirements.qualityAttributes.length > 0);
  assert.deepEqual(requirements.assumptions, []);
  assert.ok(requirements.constraints.length > 0);
  assert.ok(requirements.outOfScope.length > 0);
  assert.ok(requirements.nonGoals.length > 0);
  assert.ok(requirements.acceptanceCriteriaRef && requirements.definitionOfDoneRef && requirements.deferredItemsRef);
});

check("네 탭 이름과 TabHeader·Body 쌍을 정확히 정의", () => {
  assert.deepEqual(ui.tabs.map((tab) => tab.label), ["Dashboard", "Intake", "Design", "WorkUnit"]);
  ui.tabs.forEach((tab) => {
    assert.ok(tab.tabHeader);
    assert.ok(tab.body);
  });
  assert.match(ui.activeTabContract.effect, /TabHeader와 Body를 동시에 활성화/);
});

check("단계 selected-only 계약과 Done 숨김 및 미정 선택 세부를 분리", () => {
  assert.equal(ui.stageVisibilityContract.doneCanBeHidden, true);
  assert.equal(ui.stageVisibilityContract.controlType, null);
  assert.equal(ui.stageVisibilityContract.selectionCardinality, null);
  assert.equal(ui.stageVisibilityContract.defaultValue, null);
  assert.equal(ui.stageVisibilityContract.persistence, null);
  assert.match(ui.stageVisibilityContract.effect, /선택한 정상 단계만 표시/);
  assert.equal(ui.reviewHarness.status, "non_normative");
});

check("정상 5단계의 개수·순서·의미가 canonical schema와 일치", () => {
  assert.deepEqual(ui.normalStages.map((stage) => stage.id), ["backlog", "ready", "working", "review", "done"]);
  assert.deepEqual(ui.normalStages.map((stage) => stage.order), [1, 2, 3, 4, 5]);
  const meanings = workUnitSchema.$defs.kanbanStatus["x-statusMeanings"];
  ui.normalStages.forEach((stage) => assert.equal(stage.meaning, meanings[stage.id]));
});

check("Blocked를 정상 5단계 밖의 예외 상태로 정의", () => {
  assert.ok(!ui.normalStages.some((stage) => stage.id === "blocked"));
  assert.equal(ui.exceptionStates.length, 1);
  assert.equal(ui.exceptionStates[0].id, "blocked");
  assert.equal(ui.exceptionStates[0].classification, "exception");
  assert.equal(ui.exceptionStates[0].normalKanbanStage, false);
  assert.equal(ui.exceptionStates[0].visualPlacement, null);
});

check("카드는 title-only·fixed이며 정확한 높이와 긴 제목 처리는 미정", () => {
  assert.deepEqual(ui.workUnitCardContract.visibleFields, ["title"]);
  assert.equal(ui.workUnitCardContract.height.mode, "fixed");
  assert.equal(ui.workUnitCardContract.height.exactValue, null);
  assert.equal(ui.workUnitCardContract.longTitleHandling, null);
});

check("DnD transition map이 canonical x-statusTransitions와 일치하고 Human guard를 보존", () => {
  assert.deepEqual(ui.dragAndDropContract.statusTransitions, workUnitSchema["x-statusTransitions"]);
  assert.equal(ui.dragAndDropContract.reviewToDoneRequiresHumanApproval, true);
  assert.match(ui.dragAndDropContract.reviewToDoneGuard, /Human 승인을 생성하거나 대신하지 않는다/);
  assert.match(ui.dragAndDropContract.disallowedDropResult, /변경하지 않는다/);
});

check("세로 scroll과 width 0 hidden scrollbar 계약을 기록", () => {
  assert.equal(ui.scrollContract.direction, "vertical");
  assert.equal(ui.scrollContract.behavior, "enabled");
  assert.equal(ui.scrollContract.scrollbarWidth, 0);
  assert.equal(ui.scrollContract.scrollbarVisible, false);
  assert.equal(ui.scrollContract.viewportHeight, null);
  assert.equal(ui.scrollContract.overflowStartThreshold, null);
});

check("API와 event model을 근거 없이 발명하지 않고 unresolved로 기록", () => {
  assert.equal(ui.apiModel.status, "unresolved");
  assert.equal(ui.eventModel.status, "unresolved");
  assert.ok(ui.apiModel.reason && ui.eventModel.reason);
});

check("Work Unit unresolvedItems를 Project Core에 손실 없이 보존", () => {
  assert.deepEqual(projectCore.unresolvedItems, workUnit.unresolvedItems);
});

check("Design decisions가 rationale·alternatives·tradeoffs 상태를 명시", () => {
  assert.equal(governance.decisionsRef, manifest.collections.decisions);
  assert.equal(decisions.items.length, 4);
  decisions.items.forEach((decision) => {
    assert.ok(decision.rationale.status && decision.rationale.text);
    assert.ok(decision.alternatives.status && Array.isArray(decision.alternatives.items));
    assert.ok(decision.tradeoffs.status && Array.isArray(decision.tradeoffs.items));
    assert.ok(decision.consequences.length > 0);
  });
});

check("두 diagram source와 metadata가 목적·전체 edge·추적성을 보존", () => {
  assert.equal(governance.diagramMetadataRef, manifest.collections.diagrams);
  assert.deepEqual(diagramMetadata.items.map((item) => item.id), [uiDiagram.id, stateDiagram.id]);
  assert.equal(diagramMetadata.rendering.status, "unresolved");
  assert.ok(uiDiagram.nodes.length > 0 && uiDiagram.edges.length > 0);
  assert.deepEqual(stateDiagram.normalStates, ["backlog", "ready", "working", "review", "done"]);
  assert.deepEqual(stateDiagram.exceptionStates, ["blocked"]);
  assert.equal(stateDiagram.transitions.length, 15);
  const reviewToDone = stateDiagram.transitions.find(({ from, to }) => from === "review" && to === "done");
  assert.match(reviewToDone.guard, /Human approval required/);
});

check("Security·privacy 미정과 risk·operations 경계를 명시", () => {
  assert.equal(governance.securityPrivacyAndRisk.securityRequirements.status, "unresolved");
  assert.equal(governance.securityPrivacyAndRisk.privacyRequirements.status, "unresolved");
  assert.ok(governance.securityPrivacyAndRisk.knownRisks.length > 0);
  assert.ok(governance.securityPrivacyAndRisk.mitigations.length > 0);
  assert.ok(governance.observabilityAndOperations.reason);
});

check("Traceability가 requirement→decision→view→Work Unit→test→review를 연결", () => {
  assert.ok(governance.traceability.length >= 4);
  governance.traceability.forEach((entry) => {
    ["requirementIds", "designRefs", "decisionRefs", "workUnitRefs", "testRefs", "reviewRefs"].forEach((key) => {
      assert.ok(Array.isArray(entry[key]) && entry[key].length > 0, key);
    });
    entry.designRefs.forEach((reference) => {
      const relativePath = reference.split("#")[0];
      assert.ok(fs.existsSync(path.join(designRoot, relativePath)), reference);
    });
    entry.reviewRefs.forEach((reference) => {
      const relativePath = reference.split("#")[0];
      assert.ok(fs.existsSync(path.join(root, relativePath)), reference);
    });
  });
});

check("검증·decomposition·deliverable·history·references·glossary를 기록", () => {
  assert.ok(governance.verificationStrategy.requiredEvidence.length > 0);
  assert.ok(governance.workUnitDecompositionBasis.status);
  assert.ok(governance.customerDeliverableImpact);
  assert.ok(changeHistory.events.length > 0);
  assert.ok(governance.references.length > 0);
  assert.ok(governance.glossary.length > 0);
});

check("generated report data가 모든 sections·collections·diagrams·Work Unit review data와 일치", () => {
  assert.deepEqual(generated.manifest, manifest);
  assert.deepEqual(generated.sections, {
    "project-core": projectCore,
    requirements,
    "ui-structure": ui,
    "governance-and-verification": governance
  });
  assert.deepEqual(generated.collections, {
    decisions,
    diagrams: diagramMetadata,
    snapshots: baseline,
    events: changeHistory
  });
  assert.deepEqual(generated.diagrams, [uiDiagram, stateDiagram]);
  assert.deepEqual(generated.workUnitReview, {
    acceptanceCriteria: workUnit.acceptanceCriteria,
    definitionOfDone: workUnit.definitionOfDone,
    testCriteria: workUnit.testCriteria,
    aiChecklist: workUnit.aiChecklist,
    humanChecklist: workUnit.humanChecklist,
    humanReviewMethod: workUnit.humanReviewMethod
  });
});

check("report shell은 generated data와 renderer만 로드하고 factual markup을 복제하지 않음", () => {
  assert.match(reportHtml, /id="report-app"/);
  assert.match(reportHtml, /src="design-document-data\.js"/);
  assert.match(reportHtml, /src="script\.js"/);
  assert.doesNotMatch(reportHtml, /Dashboard|Backlog|Human approval boundary/);
});

check("report renderer가 모든 projection과 diagram source를 생성·검증", () => {
  Object.keys(generated.projectionCoverage).forEach((key) => assert.match(reportScript, new RegExp(`"${key}"|${key}`)));
  assert.match(reportScript, /Missing report projection/);
  assert.match(reportScript, /Rendered diagrams do not match source data/);
  assert.match(reportScript, /stateDiagram\.transitions\.forEach/);
  assert.match(reportScript, /data\.workUnitReview\.acceptanceCriteria/);
  assert.match(reportScript, /data\.workUnitReview\.humanChecklist/);
});

check("report CSS가 단계별 vertical scroll과 width 0 scrollbar를 구현", () => {
  assert.match(reportCss, /\.stage-cards\s*\{[\s\S]*overflow-y:\s*auto/);
  assert.match(reportCss, /scrollbar-width:\s*none/);
  assert.match(reportCss, /\.stage-cards::\-webkit-scrollbar\s*\{[\s\S]*width:\s*0/);
  assert.match(reportCss, /--report-card-block-size/);
});

check("report renderer가 탭 쌍·단계 가시성·DnD 결과를 함께 갱신", () => {
  assert.match(reportScript, /header\.hidden = header\.dataset\.tabHeader !== tabId/);
  assert.match(reportScript, /body\.hidden = body\.dataset\.tabBody !== tabId/);
  assert.match(reportScript, /stage\.hidden = !selected\.has/);
  assert.match(reportScript, /dropTarget\.append\(draggedCard\)/);
  assert.match(reportScript, /draggedCard\.dataset\.status = destinationStatus/);
});

check("실행 가능한 extension 또는 제품 기술·시각 결정을 생성하지 않음", () => {
  const files = fs
    .readdirSync(designRoot, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile())
    .map((entry) => path.relative(designRoot, path.join(entry.parentPath, entry.name)));
  assert.ok(!files.includes("package.json"));
  assert.ok(!files.some((file) => /(^|\/)(src|extension)(\/|$)/.test(file)));
  assert.equal(ui.architectureOverview.runtimeArchitecture, null);
  assert.equal(ui.architectureOverview.hostArea, null);
  assert.equal(ui.architectureOverview.implementationTechnology, null);
  assert.equal(diagramMetadata.rendering.renderer, null);
  assert.equal(diagramMetadata.rendering.exportPath, null);
});

check("검증 파일은 현재 Work Unit evidence 경계 안에 위치", () => {
  assert.ok(import.meta.filename.startsWith(workUnitRoot));
});

console.log(`RESULT PASS ${checks} structure checks`);
