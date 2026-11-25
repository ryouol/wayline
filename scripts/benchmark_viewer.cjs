"use strict";
const fs = require("node:fs"), assert = require("node:assert/strict");
const crypto = require("node:crypto"), { performance } = require("node:perf_hooks");
const [beforePath, afterPath, scenePath, outputPath] = process.argv.slice(2);
const source = fs.readFileSync(scenePath);
const bytes = source.buffer.slice(source.byteOffset, source.byteOffset + source.byteLength);
const hash = value => crypto.createHash("sha256").update(value).digest("hex");
const parser = file => {
  const scope = {};
  const text = fs.readFileSync(file, "utf8").replace("window.PointCloudViewer = PointCloudViewer;",
    "window.PointCloudViewer = PointCloudViewer; window.parse = parseGlb;");
  new Function("window", text)(scope);
  assert.equal(typeof scope.parse, "function");
  return scope.parse;
};
const before = parser(beforePath), after = parser(afterPath);
const baseline = before(bytes), candidate = after(bytes);
const arrayBytes = accessor => Buffer.from(accessor.values.buffer, accessor.values.byteOffset, accessor.values.byteLength);
assert.deepEqual(arrayBytes(candidate.positions), arrayBytes(baseline.positions));
assert.deepEqual(arrayBytes(candidate.colors), arrayBytes(baseline.colors));
assert.deepEqual(candidate.trace, baseline.trace);
assert.equal(candidate.synthetic, baseline.synthetic);
assert.equal(hash(Buffer.from(bytes)), hash(source));
for (let i = 0; i < 3; i++) { before(bytes); after(bytes); }
const timings = { before: [], after: [] };
for (let i = 0; i < 12; i++) {
  for (const [name, parse] of (i % 2 ? [["after", after], ["before", before]] : [["before", before], ["after", after]])) {
    const start = performance.now();
    const scene = parse(bytes);
    timings[name].push(performance.now() - start);
    assert.equal(scene.positions.count, baseline.positions.count);
  }
}
const median = values => { const sorted = [...values].sort((a,b) => a-b); return (sorted[5] + sorted[6]) / 2; };
const result = { checkedAt: new Date().toISOString(), context: "Node V8 parser CPU only; warmup 3, 12 paired iterations with alternating order. Not browser readiness, mobile, or field latency.",
  node: process.version, bytes: source.length, points: baseline.positions.count, sceneSha256: hash(source),
  beforeSourceSha256: hash(fs.readFileSync(beforePath)), afterSourceSha256: hash(fs.readFileSync(afterPath)),
  positionsByteIdentical: true, colorsByteIdentical: true, traceIdentical: true, artifactUnchanged: true,
  milliseconds: timings, beforeMedianMs: median(timings.before), afterMedianMs: median(timings.after) };
result.medianReductionPercent = (1 - result.afterMedianMs / result.beforeMedianMs) * 100;
fs.writeFileSync(outputPath, JSON.stringify(result, null, 2) + "\n");
console.log(JSON.stringify(result, null, 2));
