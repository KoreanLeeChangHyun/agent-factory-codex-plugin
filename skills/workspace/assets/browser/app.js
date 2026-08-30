const workspaceShell = document.querySelector("[data-workspace-shell]");
const sidebarResizer = document.querySelector("[data-sidebar-resizer]");
const explorerContent = document.querySelector("[data-explorer-content]");
const explorerSelection = document.querySelector("[data-explorer-selection]");
const skillsContent = document.querySelector("[data-skills-content]");
const skillsSelection = document.querySelector("[data-skills-selection]");
const skillsDocument = document.querySelector("[data-skills-document]");
const activityButtons = document.querySelectorAll("[data-activity]");
const sidebarTitle = document.querySelector("[data-sidebar-title]");
const sidebarViews = document.querySelectorAll("[data-sidebar-view]");
const workspaceViews = document.querySelectorAll("[data-workspace-view]");
const minimumSidebarWidth = 180;
const maximumSidebarWidth = 520;
const activityTitles = {
  explorer: "문서탐색기",
  planning: "명세서",
  skills: "프로젝트 스킬",
};

const folderIcon = () => {
  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  icon.setAttribute("viewBox", "0 0 24 24");
  icon.setAttribute("aria-hidden", "true");
  icon.setAttribute("focusable", "false");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", "M3.5 6.5h6l2 2h9v10h-17v-12Z");
  icon.append(path);
  return icon;
};

const fileIcon = () => {
  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  icon.setAttribute("viewBox", "0 0 24 24");
  icon.setAttribute("aria-hidden", "true");
  icon.setAttribute("focusable", "false");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", "M6 3.5h9l3 3v14H6v-17Zm9 0v3h3");
  icon.append(path);
  return icon;
};

const chevronIcon = () => {
  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  icon.classList.add("explorer-chevron");
  icon.setAttribute("viewBox", "0 0 12 12");
  icon.setAttribute("aria-hidden", "true");
  icon.setAttribute("focusable", "false");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", "m2.5 4 3.5 3.5L9.5 4");
  icon.append(path);
  return icon;
};

const appendTreeNode = (host, node, depth, role) => {
  const hasChildren = node.kind === "directory";
  const item = document.createElement("button");
  item.className = "explorer-row";
  item.type = "button";
  item.style.setProperty("--explorer-indent", `${depth * 16}px`);
  item.dataset.explorerItem = node.name;
  item.dataset.explorerRole = role;
  item.dataset.explorerKind = node.kind;
  item.setAttribute("role", "treeitem");
  if (hasChildren) {
    item.setAttribute("aria-expanded", "true");
    item.append(chevronIcon());
  } else {
    const indent = document.createElement("span");
    indent.className = "explorer-indent";
    item.append(indent);
  }
  item.append(hasChildren ? folderIcon() : fileIcon());
  const label = document.createElement("span");
  label.className = "explorer-row__label";
  label.textContent = node.name;
  item.append(label);
  host.append(item);

  if (hasChildren) {
    const group = document.createElement("div");
    group.setAttribute("role", "group");
    group.dataset.explorerGroup = "";
    (Array.isArray(node.children) ? node.children : []).forEach((child) => {
      appendTreeNode(group, child, depth + 1, role);
    });
    if (node.state === "error") {
      const state = document.createElement("p");
      state.className = "tree-state";
      state.style.setProperty("--explorer-indent", `${(depth + 1) * 16}px`);
      state.textContent = "이 폴더를 안전하게 읽을 수 없습니다.";
      group.append(state);
    } else if (node.state === "empty") {
      const state = document.createElement("p");
      state.className = "tree-state";
      state.style.setProperty("--explorer-indent", `${(depth + 1) * 16}px`);
      state.textContent = "표시할 항목이 없습니다.";
      group.append(state);
    }
    host.append(group);
  }
};

const renderExplorerTrees = (payload) => {
  if (!explorerContent) return;
  explorerContent.replaceChildren();
  const trees = Array.isArray(payload.trees) ? payload.trees : [];
  trees.forEach((tree) => {
    const section = document.createElement("section");
    section.className = `tree-section tree-section--${tree.role}`;
    const heading = document.createElement("h2");
    heading.className = "tree-section__heading";
    heading.textContent = tree.label;
    section.append(heading);
    if (tree.state === "missing") {
      const state = document.createElement("p");
      state.className = "tree-state";
      state.textContent = "현재 생성된 임시 Explorer 근거 작업공간이 없습니다.";
      section.append(state);
    } else if (tree.state === "error") {
      const state = document.createElement("p");
      state.className = "tree-state";
      state.textContent = "이 트리를 안전하게 불러올 수 없습니다.";
      section.append(state);
    } else if (tree.state === "empty") {
      const state = document.createElement("p");
      state.className = "tree-state";
      state.textContent = "표시할 리소스가 없습니다.";
      section.append(state);
    } else {
      (Array.isArray(tree.children) ? tree.children : []).forEach((node) => {
        appendTreeNode(section, node, 0, tree.role);
      });
    }
    explorerContent.append(section);
  });
  if (payload.truncated) {
    const notice = document.createElement("p");
    notice.className = "tree-limit-state";
    notice.textContent = "안전한 표시 한도에 도달해 나머지 항목은 생략했습니다.";
    explorerContent.append(notice);
  }
};

const loadExplorerTrees = async () => {
  if (!explorerContent) return;
  try {
    const response = await fetch("/api/explorer-tree", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderExplorerTrees(await response.json());
  } catch (_error) {
    explorerContent.replaceChildren();
    const error = document.createElement("p");
    error.className = "empty-state";
    error.textContent = "문서탐색기 트리를 불러올 수 없습니다.";
    explorerContent.append(error);
  }
};

const renderProjectSkills = (skills) => {
  if (!skillsContent) return;

  skillsContent.replaceChildren();
  if (!skills.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "현재 프로젝트에 Project Skill이 없습니다.";
    skillsContent.append(empty);
    return;
  }

  const category = document.createElement("div");
  category.className = "explorer-row";
  category.setAttribute("role", "treeitem");
  category.setAttribute("aria-expanded", "true");
  category.append(folderIcon());
  const categoryLabel = document.createElement("span");
  categoryLabel.className = "explorer-row__label";
  categoryLabel.textContent = "프로젝트 스킬";
  category.append(categoryLabel);
  skillsContent.append(category);

  const group = document.createElement("div");
  group.setAttribute("role", "group");
  skills.forEach((skill) => {
    const item = document.createElement("button");
    item.className = "explorer-row";
    item.type = "button";
    item.style.setProperty("--explorer-indent", "16px");
    item.dataset.projectSkill = skill.name;
    item.dataset.skillHref = skill.href;
    item.setAttribute("role", "treeitem");
    item.append(folderIcon());
    const label = document.createElement("span");
    label.className = "explorer-row__label";
    label.textContent = skill.name;
    item.append(label);
    group.append(item);
  });
  skillsContent.append(group);
};

const loadProjectSkills = async () => {
  if (!skillsContent) return;
  try {
    const response = await fetch("/api/project-skills", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    renderProjectSkills(Array.isArray(payload.skills) ? payload.skills : []);
  } catch (_error) {
    skillsContent.replaceChildren();
    const error = document.createElement("p");
    error.className = "empty-state";
    error.textContent = "Project Skill 목록을 불러올 수 없습니다.";
    skillsContent.append(error);
  }
};

const selectActivity = (activity) => {
  if (!Object.hasOwn(activityTitles, activity)) return;

  activityButtons.forEach((button) => {
    const isActive = button.dataset.activity === activity;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });
  sidebarViews.forEach((view) => {
    view.hidden = view.dataset.sidebarView !== activity;
  });
  workspaceViews.forEach((view) => {
    view.hidden = view.dataset.workspaceView !== activity;
  });
  if (sidebarTitle) sidebarTitle.textContent = activityTitles[activity];
};

const setSidebarWidth = (width) => {
  if (!workspaceShell || !sidebarResizer) return;

  const activityBarWidth = Number.parseFloat(
    getComputedStyle(workspaceShell).getPropertyValue("--activity-bar-width"),
  );
  const availableWidth = Math.max(
    minimumSidebarWidth,
    workspaceShell.clientWidth - activityBarWidth - 96,
  );
  const nextWidth = Math.min(
    Math.max(width, minimumSidebarWidth),
    Math.min(maximumSidebarWidth, availableWidth),
  );

  workspaceShell.style.setProperty("--primary-sidebar-width", `${nextWidth}px`);
  sidebarResizer.setAttribute("aria-valuenow", String(Math.round(nextWidth)));
};

if (workspaceShell) {
  workspaceShell.dataset.ready = "true";
  loadExplorerTrees();
  loadProjectSkills();
}

activityButtons.forEach((button) => {
  button.addEventListener("click", () => selectActivity(button.dataset.activity));
});

if (sidebarResizer) {
  sidebarResizer.addEventListener("pointerdown", (event) => {
    const startX = event.clientX;
    const initialWidth = Number.parseFloat(
      getComputedStyle(workspaceShell).getPropertyValue("--primary-sidebar-width"),
    );

    sidebarResizer.setPointerCapture(event.pointerId);
    sidebarResizer.classList.add("is-dragging");
    document.body.classList.add("is-resizing-sidebar");

    const resize = (moveEvent) => {
      setSidebarWidth(initialWidth + moveEvent.clientX - startX);
    };

    const stopResize = () => {
      sidebarResizer.classList.remove("is-dragging");
      document.body.classList.remove("is-resizing-sidebar");
      sidebarResizer.removeEventListener("pointermove", resize);
      sidebarResizer.removeEventListener("pointerup", stopResize);
      sidebarResizer.removeEventListener("pointercancel", stopResize);
    };

    sidebarResizer.addEventListener("pointermove", resize);
    sidebarResizer.addEventListener("pointerup", stopResize);
    sidebarResizer.addEventListener("pointercancel", stopResize);
  });

  sidebarResizer.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;

    event.preventDefault();
    const currentWidth = Number(sidebarResizer.getAttribute("aria-valuenow"));
    setSidebarWidth(currentWidth + (event.key === "ArrowLeft" ? -16 : 16));
  });
}

if (skillsContent) {
  skillsContent.addEventListener("click", async (event) => {
    const item = event.target.closest("[data-project-skill]");
    if (!item) return;

    skillsContent.querySelectorAll("[data-project-skill]").forEach((candidate) => {
      candidate.classList.toggle("is-selected", candidate === item);
    });
    if (skillsSelection) {
      skillsSelection.textContent = `${item.dataset.projectSkill}의 SKILL.md를 불러오는 중입니다.`;
      skillsSelection.hidden = false;
    }
    if (skillsDocument) skillsDocument.hidden = true;

    try {
      const response = await fetch(item.dataset.skillHref);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      if (skillsDocument) {
        skillsDocument.textContent = await response.text();
        skillsDocument.hidden = false;
      }
      if (skillsSelection) skillsSelection.hidden = true;
    } catch (_error) {
      if (skillsSelection) {
        skillsSelection.textContent = "선택한 Project Skill을 불러올 수 없습니다.";
      }
    }
  });
}

if (explorerContent) {
  explorerContent.addEventListener("click", (event) => {
    const item = event.target.closest("[data-explorer-item]");
    if (!item) return;

    explorerContent.querySelectorAll("[data-explorer-item]").forEach((candidate) => {
      candidate.classList.toggle("is-selected", candidate === item);
    });

    if (explorerSelection) {
      const roleLabel = item.dataset.explorerRole === "evidence"
        ? "임시 Explorer 근거"
        : "프로젝트 트리";
      explorerSelection.replaceChildren();
      const heading = document.createElement("h1");
      heading.textContent = item.dataset.explorerItem;
      const description = document.createElement("p");
      description.textContent = `${roleLabel}의 ${item.dataset.explorerKind === "directory" ? "폴더" : "파일"}입니다. 내용은 이 읽기 전용 투영에서 제공하지 않습니다.`;
      explorerSelection.append(heading, description);
    }

    if (item.hasAttribute("aria-expanded")) {
      const expanded = item.getAttribute("aria-expanded") === "true";
      item.setAttribute("aria-expanded", String(!expanded));
      const group = item.nextElementSibling;
      if (group?.matches("[data-explorer-group]")) {
        group.hidden = expanded;
      }
    }
  });
}
