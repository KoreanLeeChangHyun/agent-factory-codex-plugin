(() => {
  "use strict";

  const data = globalThis.__VSCODE_EXTENSION_UI_STRUCTURE_REPORT_DATA__;
  if (!data) throw new Error("Generated Design Document report data is missing.");

  const app = document.querySelector("#report-app");
  const projectCore = data.sections["project-core"];
  const requirements = data.sections.requirements;
  const ui = data.sections["ui-structure"];
  const governance = data.sections["governance-and-verification"];
  const decisions = data.collections.decisions;
  const diagramMetadata = data.collections.diagrams;
  const baseline = data.collections.snapshots;
  const changeHistory = data.collections.events;
  const uiDiagram = data.diagrams.find((diagram) => diagram.type === "ui-flow");
  const stateDiagram = data.diagrams.find((diagram) => diagram.type === "state");
  const normalStageIds = new Set(ui.normalStages.map((stage) => stage.id));
  let draggedCard = null;

  function node(tag, options = {}) {
    const element = document.createElement(tag);
    if (options.id) element.id = options.id;
    if (options.className) element.className = options.className;
    if (options.text !== undefined) element.textContent = String(options.text);
    if (options.attrs) {
      Object.entries(options.attrs).forEach(([name, value]) => {
        if (value !== undefined && value !== null) element.setAttribute(name, String(value));
      });
    }
    return element;
  }

  function append(parent, ...children) {
    children.flat(Infinity).forEach((child) => {
      if (child === undefined || child === null) return;
      parent.append(child instanceof Node ? child : document.createTextNode(String(child)));
    });
    return parent;
  }

  function textParagraph(text, className) {
    return node("p", { text, className });
  }

  function renderList(items, ordered = false) {
    if (!items || items.length === 0) return textParagraph("기록된 항목 없음", "empty-value");
    const list = node(ordered ? "ol" : "ul");
    items.forEach((item) => {
      const listItem = node("li");
      append(listItem, item instanceof Node ? item : String(item));
      list.append(listItem);
    });
    return list;
  }

  function renderValue(value) {
    if (value === null || value === undefined) return textParagraph("미정", "empty-value");
    if (Array.isArray(value)) return renderList(value.map((item) => (typeof item === "object" ? renderValue(item) : item)));
    if (typeof value === "object") {
      const definitions = node("dl", { className: "definition-list" });
      Object.entries(value).forEach(([key, nested]) => {
        definitions.append(node("dt", { text: key }));
        const valueNode = node("dd");
        append(valueNode, renderValue(nested));
        definitions.append(valueNode);
      });
      return definitions;
    }
    return node("span", { text: String(value) });
  }

  function sectionHeading(number, title, id) {
    const heading = node("div", { className: "section-heading" });
    append(heading, node("p", { text: number }), node("h2", { id, text: title }));
    return heading;
  }

  function reportSection(number, title, id, projection) {
    const section = node("section", { attrs: { "aria-labelledby": id, "data-projection": projection } });
    section.append(sectionHeading(number, title, id));
    return section;
  }

  function coreArticle(title, content) {
    const article = node("article");
    article.append(node("h3", { text: title }));
    append(article, content);
    return article;
  }

  function detailsBlock(title, content, projection) {
    const details = node("details", { className: "design-detail", attrs: { "data-projection": projection } });
    details.append(node("summary", { text: title }));
    const body = node("div", { className: "detail-body" });
    append(body, content);
    details.append(body);
    return details;
  }

  function metadataRow(term, description) {
    const wrapper = node("div");
    append(wrapper, node("dt", { text: term }), node("dd", { text: description }));
    return wrapper;
  }

  function renderHeader() {
    document.title = `${data.manifest.title} · Design Report 초안`;
    const header = node("header", { className: "document-header" });
    append(
      header,
      node("p", { className: "document-kicker", text: "Design Report · Draft" }),
      node("h1", { text: data.manifest.title }),
      textParagraph(requirements.userRequest.goal)
    );
    const metadata = node("dl", { className: "metadata" });
    append(
      metadata,
      metadataRow("Source of truth", data.manifest.sourceOfTruth),
      metadataRow("Lifecycle", `${data.manifest.sourceWorkUnit.id} · ${data.manifest.lifecyclePhase}`),
      metadataRow("상태", `${data.manifest.status} · Human Review 전`)
    );
    header.append(metadata);
    header.append(
      textParagraph(
        "이 report는 manifest, sections, collections, diagram source와 Work Unit review 기준에서 생성한 Human 검토용 파생 표현입니다. 검토 도구의 control, 초기 선택, 크기와 배치는 제품 설계 결정이 아닙니다.",
        "review-notice"
      )
    );
    return header;
  }

  function renderProjectCore() {
    const section = reportSection("01", projectCore.title, "project-core-title", "projectCore");
    const grid = node("div", { className: "core-grid" });
    append(
      grid,
      coreArticle("목적", textParagraph(projectCore.purpose)),
      coreArticle("핵심 원칙", renderList(projectCore.corePrinciples)),
      coreArticle("범위", renderList(projectCore.scope)),
      coreArticle("Human 승인 경계", renderList(projectCore.humanApprovalBoundaries)),
      coreArticle("미정 항목", renderList(projectCore.unresolvedItems))
    );
    section.append(grid);
    return section;
  }

  function renderUiDiagram(diagram) {
    const figure = node("figure", { className: "relation-view", attrs: { "data-diagram-id": diagram.id } });
    figure.append(node("figcaption", { text: diagram.purpose }));
    const nodes = node("ol", { className: "diagram-node-list" });
    diagram.nodes.forEach((item) => {
      const listItem = node("li");
      append(listItem, node("strong", { text: item.label }), node("span", { text: item.kind }));
      nodes.append(listItem);
    });
    figure.append(nodes);
    const edgeTable = node("table", { className: "diagram-edge-table" });
    const head = node("thead");
    const headRow = node("tr");
    ["From", "Relation", "To"].forEach((label) => headRow.append(node("th", { text: label, attrs: { scope: "col" } })));
    head.append(headRow);
    edgeTable.append(head);
    const body = node("tbody");
    diagram.edges.forEach((edge) => {
      const row = node("tr");
      [edge.from, edge.relation, edge.to].forEach((value) => row.append(node("td", { text: value })));
      body.append(row);
    });
    edgeTable.append(body);
    figure.append(edgeTable);
    return figure;
  }

  function renderReviewControls() {
    const fieldset = node("fieldset", {
      id: "stage-visibility-review",
      className: "review-controls",
      attrs: { "data-review-only": "true" }
    });
    fieldset.append(node("legend", { text: "표시 단계 검토 도구" }));
    fieldset.append(
      textParagraph(
        "아래 checkbox는 selected-only 동작을 검토하기 위한 비규범적 도구입니다. 제품 control 형식, 선택 cardinality와 기본 표시 단계를 정하지 않습니다."
      )
    );
    const options = node("div", { className: "stage-options" });
    ui.normalStages.forEach((stage) => {
      const label = node("label");
      const input = node("input", { attrs: { type: "checkbox", value: stage.id } });
      input.checked = true;
      append(label, input, ` ${stage.label}`);
      options.append(label);
    });
    fieldset.append(options);
    return fieldset;
  }

  function renderKanbanBoard() {
    const body = node("div", {
      id: "body-workunit",
      className: "tab-body-region",
      attrs: { role: "tabpanel", "aria-labelledby": "tab-workunit", "data-tab-body": "workunit" }
    });
    const bodyHeading = node("div", { className: "body-heading" });
    const headingText = node("div");
    append(
      headingText,
      node("p", { className: "region-label", text: "WorkUnit · Body" }),
      textParagraph(ui.tabs.find((tab) => tab.id === "workunit").body.responsibility)
    );
    append(
      bodyHeading,
      headingText,
      node("p", { id: "stage-visibility-status", attrs: { role: "status" }, text: "검토 도구 초기 상태" })
    );
    body.append(bodyHeading);

    const board = node("div", { className: "kanban-board", attrs: { "aria-label": "WorkUnit 정상 5단계 칸반" } });
    ui.normalStages.forEach((stage) => {
      const stageSection = node("section", {
        className: "kanban-stage",
        attrs: { "data-stage": stage.id, "aria-labelledby": `stage-${stage.id}-title` }
      });
      const header = node("header");
      append(
        header,
        node("h3", { id: `stage-${stage.id}-title`, text: stage.label }),
        textParagraph(stage.meaning)
      );
      const cards = node("div", { className: "stage-cards", attrs: { "data-drop-stage": stage.id } });
      if (stage.id === ui.reviewHarness.initialStatus) {
        cards.append(
          node("article", {
            className: "work-unit-card",
            text: data.workUnitSummary.title,
            attrs: {
              draggable: "true",
              "data-work-unit-id": data.workUnitSummary.id,
              "data-status": ui.reviewHarness.initialStatus
            }
          })
        );
      }
      append(stageSection, header, cards);
      board.append(stageSection);
    });
    body.append(board);

    const blocked = ui.exceptionStates.find((state) => state.id === "blocked");
    const notes = node("div", { className: "kanban-notes" });
    [
      ["검토 시나리오", ui.reviewHarness.reason],
      [blocked.label, `${blocked.meaning}. classification: ${blocked.classification} 예외 상태. 정상 칸반 단계 여부: ${blocked.normalKanbanStage}. 표시 위치와 조작은 미정입니다.`],
      ["카드 계약", `보이는 field는 ${ui.workUnitCardContract.visibleFields.join(", ")}뿐이고 height mode는 ${ui.workUnitCardContract.height.mode}입니다. exact value와 long title 처리는 미정입니다.`],
      ["DnD 계약", `${ui.dragAndDropContract.allowedDropResult.join(" ")} ${ui.dragAndDropContract.disallowedDropResult}`],
      ["Human 경계", ui.dragAndDropContract.reviewToDoneGuard]
    ].forEach(([label, value]) => {
      const paragraph = node("p");
      append(paragraph, node("strong", { text: label }), `: ${value}`);
      notes.append(paragraph);
    });
    notes.append(node("p", { id: "dnd-status", attrs: { role: "status" }, text: "검토용 카드를 허용된 정상 단계 사이에서 이동해 보세요." }));
    body.append(notes);
    return body;
  }

  function renderTabReview() {
    const review = node("div", { className: "ui-review", attrs: { "aria-label": "탭 구조 검토 도구" } });
    const tabList = node("div", { className: "tab-list", attrs: { role: "tablist", "aria-label": "검토할 탭" } });
    ui.tabs.forEach((tab, index) => {
      tabList.append(
        node("button", {
          id: `tab-${tab.id}`,
          text: tab.label,
          attrs: {
            type: "button",
            role: "tab",
            "data-tab": tab.id,
            "aria-controls": `body-${tab.id}`,
            "aria-selected": index === 0 ? "true" : "false",
            tabindex: index === 0 ? "0" : "-1"
          }
        })
      );
    });
    review.append(tabList);
    const surface = node("div", { className: "tab-surface" });
    ui.tabs.forEach((tab, index) => {
      const header = node("header", { className: "tab-header-region", attrs: { "data-tab-header": tab.id } });
      if (index !== 0) header.hidden = true;
      header.append(node("p", { className: "region-label", text: `${tab.label} · TabHeader` }));
      if (tab.id === "workunit") header.append(renderReviewControls());
      else header.append(textParagraph(tab.tabHeader.status === "unresolved" ? "상세 내용 미정" : String(tab.tabHeader.content)));
      surface.append(header);
    });
    ui.tabs.forEach((tab, index) => {
      if (tab.id === "workunit") {
        const workUnitBody = renderKanbanBoard();
        workUnitBody.hidden = index !== 0;
        surface.append(workUnitBody);
        return;
      }
      const body = node("div", {
        id: `body-${tab.id}`,
        className: "tab-body-region",
        attrs: { role: "tabpanel", "aria-labelledby": `tab-${tab.id}`, "data-tab-body": tab.id }
      });
      if (index !== 0) body.hidden = true;
      append(
        body,
        node("p", { className: "region-label", text: `${tab.label} · Body` }),
        textParagraph(tab.body.status === "unresolved" ? "상세 내용 미정" : String(tab.body.content))
      );
      surface.append(body);
    });
    review.append(surface);
    return review;
  }

  function renderUiStructure() {
    const section = reportSection("02", "탭과 Body 구조", "structure-title", "uiStructure");
    section.append(textParagraph(ui.activeTabContract.effect));
    section.append(renderUiDiagram(uiDiagram));
    section.append(renderTabReview());
    return section;
  }

  function renderStateView() {
    const section = reportSection("03", "칸반 상태와 전이", "state-title", "diagrams");
    const table = node("table");
    const head = node("thead");
    const headerRow = node("tr");
    ["순서", "단계", "의미"].forEach((label) => headerRow.append(node("th", { text: label, attrs: { scope: "col" } })));
    head.append(headerRow);
    table.append(head);
    const body = node("tbody");
    ui.normalStages.forEach((stage) => {
      const row = node("tr");
      append(
        row,
        node("td", { text: stage.order }),
        node("th", { text: stage.label, attrs: { scope: "row" } }),
        node("td", { text: stage.meaning })
      );
      body.append(row);
    });
    table.append(body);
    const tableWrap = node("div", { className: "table-wrap" });
    tableWrap.append(table);
    section.append(tableWrap);

    const figure = node("figure", { className: "state-view", attrs: { "data-diagram-id": stateDiagram.id } });
    figure.append(node("figcaption", { text: stateDiagram.purpose }));
    const transitionTable = node("table");
    const transitionHead = node("thead");
    const transitionHeaderRow = node("tr");
    ["From", "To", "Guard"].forEach((label) => transitionHeaderRow.append(node("th", { text: label, attrs: { scope: "col" } })));
    transitionHead.append(transitionHeaderRow);
    transitionTable.append(transitionHead);
    const transitionBody = node("tbody");
    stateDiagram.transitions.forEach((transition) => {
      const row = node("tr");
      append(
        row,
        node("td", { text: transition.from }),
        node("td", { text: transition.to }),
        node("td", { text: transition.guard ?? "없음" })
      );
      transitionBody.append(row);
    });
    transitionTable.append(transitionBody);
    figure.append(transitionTable);
    figure.append(textParagraph(`Terminal: ${stateDiagram.terminalStates.join(", ")}. Invalid transition: ${stateDiagram.invalidTransitionResult}`));
    section.append(figure);
    return section;
  }

  function renderRequirementDetails() {
    const wrapper = node("div");
    append(
      wrapper,
      node("h3", { text: "Outcome과 completion boundary" }),
      textParagraph(requirements.outcome),
      textParagraph(requirements.completionBoundary),
      node("h3", { text: "Lifecycle" }),
      renderValue(requirements.lifecycle),
      node("h3", { text: "Stakeholders" }),
      renderValue(requirements.stakeholders),
      node("h3", { text: "Functional requirements" }),
      renderValue(requirements.functionalRequirements),
      node("h3", { text: "Non-functional requirements" }),
      renderValue(requirements.nonFunctionalRequirements),
      node("h3", { text: "Quality attributes" }),
      renderList(requirements.qualityAttributes),
      node("h3", { text: "Assumptions" }),
      renderList(requirements.assumptions),
      node("h3", { text: "Constraints" }),
      renderList(requirements.constraints),
      node("h3", { text: "Out of scope" }),
      renderList(requirements.outOfScope),
      node("h3", { text: "Non-goals" }),
      renderList(requirements.nonGoals)
    );
    return wrapper;
  }

  function renderBaseline() {
    const wrapper = node("div", { attrs: { "data-projection": "baseline" } });
    append(
      wrapper,
      textParagraph(`Adoption timing: ${baseline.adoptionTiming}. Captured: ${baseline.capturedOn}.`),
      renderValue(baseline.checks)
    );
    return wrapper;
  }

  function renderArchitectureDetails() {
    const wrapper = node("div");
    append(
      wrapper,
      node("h3", { text: "Architecture overview" }),
      renderValue(ui.architectureOverview),
      node("h3", { text: "Conceptual interfaces" }),
      renderValue(ui.conceptualInterfaces),
      node("h3", { text: "API model" }),
      renderValue(ui.apiModel),
      node("h3", { text: "Event model" }),
      renderValue(ui.eventModel),
      node("h3", { text: "File formats" }),
      renderList(ui.fileFormats),
      node("h3", { text: "Error behavior" }),
      renderValue(ui.errorBehavior),
      node("h3", { text: "Data, state, ownership, persistence, cache, migration, retention" }),
      renderValue(ui.dataAndState)
    );
    return wrapper;
  }

  function renderDecisions() {
    const wrapper = node("div", { className: "decision-grid", attrs: { "data-projection": "decisions" } });
    decisions.items.forEach((decision) => {
      const article = node("article");
      append(
        article,
        node("h3", { text: `${decision.id} · ${decision.decision}` }),
        textParagraph(`Basis: ${decision.basis}`),
        node("h4", { text: `Rationale · ${decision.rationale.status}` }),
        textParagraph(decision.rationale.text),
        node("h4", { text: `Alternatives · ${decision.alternatives.status}` }),
        renderList(decision.alternatives.items),
        node("h4", { text: `Tradeoffs · ${decision.tradeoffs.status}` }),
        renderList(decision.tradeoffs.items),
        node("h4", { text: "Consequences" }),
        renderList(decision.consequences)
      );
      wrapper.append(article);
    });
    return wrapper;
  }

  function renderDiagramMetadata() {
    const wrapper = node("div", { attrs: { "data-projection": "diagramMetadata" } });
    append(wrapper, renderValue(diagramMetadata));
    return wrapper;
  }

  function renderGovernanceDetails() {
    const wrapper = node("div", { attrs: { "data-projection": "governance" } });
    append(
      wrapper,
      node("h3", { text: "Security, privacy and risk" }),
      renderValue(governance.securityPrivacyAndRisk),
      node("h3", { text: "Observability and operations" }),
      renderValue(governance.observabilityAndOperations),
      node("h3", { text: "Verification strategy" }),
      renderValue(governance.verificationStrategy),
      node("h3", { text: "Traceability" }),
      renderValue(governance.traceability),
      node("h3", { text: "Work Unit decomposition basis" }),
      renderValue(governance.workUnitDecompositionBasis),
      node("h3", { text: "Customer Deliverable impact" }),
      textParagraph(governance.customerDeliverableImpact)
    );
    return wrapper;
  }

  function renderVerificationDetails() {
    const wrapper = node("div");
    [
      ["Acceptance criteria", data.workUnitReview.acceptanceCriteria],
      ["Definition of Done", data.workUnitReview.definitionOfDone],
      ["Test criteria", data.workUnitReview.testCriteria],
      ["AI checklist", data.workUnitReview.aiChecklist]
    ].forEach(([title, items]) => append(wrapper, node("h3", { text: title }), renderList(items, true)));
    return wrapper;
  }

  function renderHistoryAndReferences() {
    const wrapper = node("div", { attrs: { "data-projection": "changeHistory" } });
    append(
      wrapper,
      node("h3", { text: "Change history" }),
      renderValue(changeHistory.events),
      node("h3", { text: "References and evidence" }),
      renderList([...new Set([...data.manifest.references, ...governance.references])]),
      node("h3", { text: "Glossary" }),
      renderValue(governance.glossary)
    );
    return wrapper;
  }

  function renderDetailedDesign() {
    const section = reportSection("04", "상세 설계와 거버넌스", "details-title", "requirements");
    append(
      section,
      detailsBlock("요구사항, 범위와 품질 속성", renderRequirementDetails()),
      detailsBlock("실행 전 baseline", renderBaseline(), "baseline"),
      detailsBlock("Architecture, interface, API, event와 data/state", renderArchitectureDetails()),
      detailsBlock("Design decisions", renderDecisions(), "decisions"),
      detailsBlock("Diagram metadata와 rendering 경계", renderDiagramMetadata(), "diagramMetadata"),
      detailsBlock("Security, privacy, risk, observability, verification과 traceability", renderGovernanceDetails(), "governance"),
      detailsBlock("Acceptance criteria, Definition of Done, test와 AI checklist", renderVerificationDetails()),
      detailsBlock("Change history, references, evidence와 glossary", renderHistoryAndReferences(), "changeHistory")
    );
    return section;
  }

  function renderHumanReview() {
    const section = reportSection("05", "Human Review", "review-title", "workUnitReview");
    section.append(renderList(data.workUnitReview.humanChecklist, true));
    const method = node("article", { className: "review-method" });
    append(method, node("h3", { text: "검토 방법" }), textParagraph(data.workUnitReview.humanReviewMethod));
    section.append(method);
    return section;
  }

  function renderUnresolved() {
    const section = reportSection("06", "미정 항목", "unresolved-title", undefined);
    section.append(renderList(projectCore.unresolvedItems));
    return section;
  }

  function renderFooter() {
    const footer = node("footer");
    footer.append(textParagraph(`기준 파일: ${data.generatedFrom.manifest}`));
    return footer;
  }

  function buildReport() {
    const main = node("main");
    append(
      main,
      renderProjectCore(),
      renderUiStructure(),
      renderStateView(),
      renderDetailedDesign(),
      renderHumanReview(),
      renderUnresolved()
    );
    append(app, renderHeader(), main, renderFooter());
  }

  function verifyRenderedProjection() {
    const renderedProjectionKeys = new Set(
      [...document.querySelectorAll("[data-projection]")]
        .map((element) => element.dataset.projection)
        .filter(Boolean)
    );
    Object.keys(data.projectionCoverage).forEach((key) => {
      if (!renderedProjectionKeys.has(key)) throw new Error(`Missing report projection: ${key}`);
    });

    const renderedTabs = [...document.querySelectorAll("[role='tab'][data-tab]")]
      .map((button) => ({ id: button.dataset.tab, label: button.textContent.trim() }));
    const sourceTabs = ui.tabs.map(({ id, label }) => ({ id, label }));
    const renderedStages = [...document.querySelectorAll(".kanban-stage[data-stage]")]
      .map((stage) => stage.dataset.stage);
    const sourceStages = ui.normalStages.map((stage) => stage.id);
    const renderedDiagramIds = [...document.querySelectorAll("[data-diagram-id]")]
      .map((element) => element.dataset.diagramId);
    const sourceDiagramIds = data.diagrams.map((diagram) => diagram.id);

    if (JSON.stringify(renderedTabs) !== JSON.stringify(sourceTabs)) throw new Error("Rendered tabs do not match source data.");
    if (JSON.stringify(renderedStages) !== JSON.stringify(sourceStages)) throw new Error("Rendered stages do not match source data.");
    if (JSON.stringify(renderedDiagramIds) !== JSON.stringify(sourceDiagramIds)) throw new Error("Rendered diagrams do not match source data.");
  }

  function activateTab(tabId) {
    document.querySelectorAll("[role='tab'][data-tab]").forEach((button) => {
      const active = button.dataset.tab === tabId;
      button.setAttribute("aria-selected", String(active));
      button.tabIndex = active ? 0 : -1;
    });
    document.querySelectorAll("[data-tab-header]").forEach((header) => {
      header.hidden = header.dataset.tabHeader !== tabId;
    });
    document.querySelectorAll("[data-tab-body]").forEach((body) => {
      body.hidden = body.dataset.tabBody !== tabId;
    });
    normalizeReviewCardHeights();
  }

  function updateVisibleStages() {
    const inputs = [...document.querySelectorAll("#stage-visibility-review input[type='checkbox']")];
    const selected = new Set(inputs.filter((input) => input.checked).map((input) => input.value));
    document.querySelectorAll(".kanban-stage[data-stage]").forEach((stage) => {
      stage.hidden = !selected.has(stage.dataset.stage);
    });
    const labels = inputs.filter((input) => input.checked).map((input) => input.parentElement.textContent.trim());
    document.querySelector("#stage-visibility-status").textContent = labels.length
      ? `검토 도구 표시 단계: ${labels.join(", ")}`
      : "검토 도구 표시 단계: 없음";
  }

  function normalizeReviewCardHeights() {
    const cards = [...document.querySelectorAll(".work-unit-card")];
    cards.forEach((card) => card.style.removeProperty("--report-card-block-size"));
    const visibleCards = cards.filter((card) => card.getClientRects().length > 0);
    if (visibleCards.length === 0) return;
    const measured = Math.max(...visibleCards.map((card) => Math.ceil(card.scrollHeight)));
    cards.forEach((card) => card.style.setProperty("--report-card-block-size", `${measured}px`));
  }

  function canDrop(sourceStatus, destinationStatus) {
    if (!normalStageIds.has(destinationStatus)) return false;
    if (sourceStatus === "review" && destinationStatus === "done") return false;
    return ui.dragAndDropContract.statusTransitions[sourceStatus]?.includes(destinationStatus) ?? false;
  }

  function clearDropState() {
    document.querySelectorAll("[data-drop-active='true']").forEach((target) => target.removeAttribute("data-drop-active"));
  }

  function bindInteractions() {
    document.querySelectorAll("[role='tab'][data-tab]").forEach((button) => {
      button.addEventListener("click", () => activateTab(button.dataset.tab));
    });
    document.querySelectorAll("#stage-visibility-review input[type='checkbox']").forEach((input) => {
      input.addEventListener("change", updateVisibleStages);
    });
    document.querySelectorAll(".work-unit-card").forEach((card) => {
      card.addEventListener("dragstart", (event) => {
        draggedCard = card;
        card.setAttribute("aria-grabbed", "true");
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", card.dataset.workUnitId);
      });
      card.addEventListener("dragend", () => {
        card.removeAttribute("aria-grabbed");
        draggedCard = null;
        clearDropState();
      });
    });
    document.querySelectorAll("[data-drop-stage]").forEach((dropTarget) => {
      dropTarget.addEventListener("dragover", (event) => {
        if (!draggedCard) return;
        const destinationStatus = dropTarget.dataset.dropStage;
        const guarded = draggedCard.dataset.status === "review" && destinationStatus === "done";
        if (canDrop(draggedCard.dataset.status, destinationStatus) || guarded) {
          event.preventDefault();
          event.dataTransfer.dropEffect = "move";
          clearDropState();
          dropTarget.dataset.dropActive = "true";
        }
      });
      dropTarget.addEventListener("dragleave", () => dropTarget.removeAttribute("data-drop-active"));
      dropTarget.addEventListener("drop", (event) => {
        event.preventDefault();
        clearDropState();
        if (!draggedCard) return;
        const sourceStatus = draggedCard.dataset.status;
        const destinationStatus = dropTarget.dataset.dropStage;
        const dndStatus = document.querySelector("#dnd-status");
        if (sourceStatus === "review" && destinationStatus === "done") {
          dndStatus.textContent = `변경 없음: ${ui.dragAndDropContract.reviewToDoneGuard}`;
          return;
        }
        if (!canDrop(sourceStatus, destinationStatus)) {
          dndStatus.textContent = `변경 없음: ${ui.dragAndDropContract.disallowedDropResult}`;
          return;
        }
        dropTarget.append(draggedCard);
        draggedCard.dataset.status = destinationStatus;
        dndStatus.textContent = `검토 결과: 카드 위치와 status가 함께 ${destinationStatus}(으)로 변경되었습니다.`;
        normalizeReviewCardHeights();
      });
    });
  }

  buildReport();
  verifyRenderedProjection();
  bindInteractions();
  activateTab(ui.tabs[0].id);
  updateVisibleStages();
  normalizeReviewCardHeights();
  window.addEventListener("resize", normalizeReviewCardHeights);
})();
