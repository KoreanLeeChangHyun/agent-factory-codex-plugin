const specificationShell = document.querySelector("[data-specification-shell]");
const sidebarResizer = document.querySelector("[data-sidebar-resizer]");
const explorerContent = document.querySelector("[data-explorer-content]");
const activityButtons = document.querySelectorAll("[data-activity]");
const sidebarTitle = document.querySelector("[data-sidebar-title]");
const sidebarViews = document.querySelectorAll("[data-sidebar-view]");
const workspaceViews = document.querySelectorAll("[data-workspace-view]");
const minimumSidebarWidth = 180;
const maximumSidebarWidth = 520;
const activityTitles = {
  explorer: "탐색기",
  planning: "Human 정제 문서",
  skills: "스킬",
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
  if (!specificationShell || !sidebarResizer) return;

  const activityBarWidth = Number.parseFloat(
    getComputedStyle(specificationShell).getPropertyValue("--activity-bar-width"),
  );
  const availableWidth = Math.max(
    minimumSidebarWidth,
    specificationShell.clientWidth - activityBarWidth - 96,
  );
  const nextWidth = Math.min(
    Math.max(width, minimumSidebarWidth),
    Math.min(maximumSidebarWidth, availableWidth),
  );

  specificationShell.style.setProperty("--primary-sidebar-width", `${nextWidth}px`);
  sidebarResizer.setAttribute("aria-valuenow", String(Math.round(nextWidth)));
};

if (specificationShell) {
  specificationShell.dataset.ready = "true";
}

activityButtons.forEach((button) => {
  button.addEventListener("click", () => selectActivity(button.dataset.activity));
});

if (sidebarResizer) {
  sidebarResizer.addEventListener("pointerdown", (event) => {
    const startX = event.clientX;
    const initialWidth = Number.parseFloat(
      getComputedStyle(specificationShell).getPropertyValue("--primary-sidebar-width"),
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

if (explorerContent) {
  explorerContent.addEventListener("click", (event) => {
    const item = event.target.closest("[data-explorer-item]");
    if (!item) return;

    explorerContent.querySelectorAll("[data-explorer-item]").forEach((candidate) => {
      candidate.classList.toggle("is-selected", candidate === item);
    });

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
