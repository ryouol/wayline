"use strict";

const assert = require("node:assert/strict");
const events = require("../lingbot_map/workspace/static/session-events.js");

function exercise(event) {
  const calls = [];
  const result = events.dispatch(event, {
    signedOut: () => calls.push("clear-private-state"),
    accountChanged: () => calls.push("clear-private-state-and-reload"),
    sessionChanged: () => calls.push("revalidate-session"),
  });
  return { calls, result };
}

assert.deepEqual(exercise({ type: "signed-out" }), {
  calls: ["clear-private-state"],
  result: "signed-out",
});
assert.deepEqual(exercise({ type: "account-changed" }), {
  calls: ["clear-private-state-and-reload"],
  result: "account-changed",
});
assert.deepEqual(exercise({ type: "session-changed" }), {
  calls: ["revalidate-session"],
  result: "session-changed",
});
assert.deepEqual(exercise({ type: "unknown" }), { calls: [], result: "ignored" });

console.log("session-event behavior passed");
