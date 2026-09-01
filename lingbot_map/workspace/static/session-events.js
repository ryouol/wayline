"use strict";

(function installWorkspaceSessionEvents(scope) {
  function dispatch(event, handlers) {
    if (!event || typeof event.type !== "string") return "ignored";
    if (event.type === "signed-out") {
      handlers.signedOut();
      return "signed-out";
    }
    if (event.type === "account-changed") {
      handlers.accountChanged();
      return "account-changed";
    }
    if (event.type === "session-changed") {
      handlers.sessionChanged();
      return "session-changed";
    }
    return "ignored";
  }

  const api = Object.freeze({ dispatch });
  if (scope) scope.WorkspaceSessionEvents = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window === "undefined" ? undefined : window);
