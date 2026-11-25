"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync(require.resolve("../lingbot_map/workspace/static/app.js"), "utf8");
const state = {
  assets: [], shares: [], assetCursor: null, shareCursor: null,
  selectedAssets: new Set(), selectedShares: new Set(),
};
let response;
const context = vm.createContext({
  state, URLSearchParams, Date,
  api: async () => response,
  byId: () => ({}),
  renderAssets() {}, renderShares() {}, updateSelectionSummary() {},
});
vm.runInContext(source.slice(source.indexOf("function mergeInventoryRows("), source.indexOf("async function loadInventory(")), context);

(async () => {
  state.selectedAssets.add("removed");
  response = { assets: [], nextCursor: null };
  await context.loadAssets();
  assert.equal(state.selectedAssets.size, 0);

  state.assets = [{ id: "keep", deletable: true }, { id: "linked", deletable: true }];
  state.selectedAssets = new Set(["keep", "linked"]);
  response = { assets: [{ id: "linked", deletable: false }, { id: "new", deletable: true }], nextCursor: null };
  await context.loadAssets({ append: true });
  assert.deepEqual([...state.selectedAssets], ["keep"]);
  assert.equal(state.assets.length, 3);
  assert.equal(state.assets.find((row) => row.id === "linked").deletable, false);

  const future = Date.now() / 1000 + 3600;
  state.selectedShares = new Set(["removed", "expired", "revoked", "active"]);
  response = { shares: [
    { id: "expired", expiresAt: 1 },
    { id: "revoked", expiresAt: future, revokedAt: 1 },
    { id: "active", expiresAt: future },
  ], nextCursor: "more" };
  await context.loadShares();
  assert.deepEqual([...state.selectedShares], ["active"]);
  response = { shares: [{ id: "active", expiresAt: future, revokedAt: 1 }], nextCursor: null };
  await context.loadShares({ append: true });
  assert.equal(state.selectedShares.size, 0);
  assert.equal(state.shares.length, 3);
  console.log("Inventory refresh and pagination selection behavior passed");
})().catch((error) => { console.error(error); process.exitCode = 1; });
