(() => {
  "use strict";
  try {
    if (window.parent !== window && window.parent.location.origin === window.location.origin) {
      document.documentElement.dataset.agentFactoryWorkspaceEmbedded = "true";
    }
  } catch {
    // Standalone and cross-origin hosts retain the normal color scheme.
  }
})();
