"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const animationFrames = [];
const scope = {window: {}, AbortController, TextDecoder, performance,
  requestAnimationFrame: callback => animationFrames.push(callback),
  CustomEvent: class { constructor(type, options) { this.type=type; this.detail=options.detail; } },
};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../lingbot_map/workspace/static/viewer.js"), "utf8"), scope);
function glb(change = () => {}) {
  const frames = [0, 1].map((time, index) => ({time, pointEnd: (index+1)*3,
    position: [index,0,0], right: [1,0,0], up: [0,1,0], forward: [0,0,-1], fov:1,
    intrinsics: [400,500,300,200], imageSize:[640,480], thumbnail:"data:image/jpeg;base64,AA=="}));
  const doc = {asset:{version:"2.0"}, scene:0, scenes:[{nodes:[0]}],nodes:[{mesh:0}],
    meshes:[{primitives:[{mode:0,attributes:{POSITION:0}}]}],
    buffers:[{byteLength:72}],bufferViews:[{buffer:0,byteLength:72}],
    accessors:[{bufferView:0,componentType:5126,count:6,type:"VEC3"}],
    extras:{wayline:{version:1,kind:"reconstruction",coordinateSystem:"gltf-y-up",pointCount:6,frames}}};
  change(doc);
  const binary=Buffer.alloc(72);
  for(let i=0;i<18;i++) binary.writeFloatLE(i/10,i*4);
  return encodeGlb(doc, binary);
}
function encodeGlb(doc, binary) {
  let json=JSON.stringify(doc); while(json.length%4) json+=" ";
  const result=Buffer.alloc(12+8+json.length+8+binary.length);
  result.writeUInt32LE(0x46546c67,0); result.writeUInt32LE(2,4); result.writeUInt32LE(result.length,8);
  result.writeUInt32LE(json.length,12); result.writeUInt32LE(0x4e4f534a,16); result.write(json,20);
  result.writeUInt32LE(binary.length,20+json.length); result.writeUInt32LE(0x004e4942,24+json.length); binary.copy(result,28+json.length);
  return result.buffer.slice(result.byteOffset,result.byteOffset+result.length);
}
function accessorGlb({ interleaved = false, unaligned = false, floatColors = false, rgb = false,
  change = () => {} } = {}) {
  const width = rgb ? 3 : 4, colorBytes = floatColors ? 4 : 1;
  const positionOffset = unaligned ? 1 : 4, colorOffset = floatColors ? 4 : 3;
  const positionStride = interleaved ? 16 : 12;
  const colorStride = width * colorBytes + (interleaved ? 4 : 0);
  const binary = Buffer.alloc(128);
  [-1, 2, 3, 4, -5, 6].forEach((value, index) =>
    binary.writeFloatLE(value, 4 + positionOffset + Math.floor(index / 3) * positionStride + index % 3 * 4));
  const colors = [[0, 128, 255, 255], [255, 64, 32, 128]];
  colors.forEach((row, index) => row.slice(0, width).forEach((value, column) => {
    const offset = 64 + colorOffset + index * colorStride + column * colorBytes;
    if (floatColors) binary.writeFloatLE(value / 255, offset); else binary[offset] = value;
  }));
  const doc = { asset: { version: "2.0" }, nodes: [{ mesh: 0 }],
    meshes: [{ primitives: [{ mode: 0, attributes: { POSITION: 0, COLOR_0: 1 } }] }],
    buffers: [{ byteLength: binary.length }],
    bufferViews: [
      { buffer: 0, byteOffset: 4, byteLength: positionOffset + positionStride + 12, byteStride: positionStride },
      { buffer: 0, byteOffset: 64, byteLength: colorOffset + colorStride + width * colorBytes, byteStride: colorStride },
    ],
    accessors: [
      { bufferView: 0, byteOffset: positionOffset, componentType: 5126, count: 2, type: "VEC3" },
      { bufferView: 1, byteOffset: colorOffset, componentType: floatColors ? 5126 : 5121,
        count: 2, type: rgb ? "VEC3" : "VEC4", normalized: !floatColors },
    ],
  };
  change(doc, binary);
  return encodeGlb(doc, binary);
}
async function load(buffer, options) {
  let request;
  scope.fetch=async (url, init) => {request={url,init}; return {ok:true,arrayBuffer:async()=>buffer};};
  const viewer=Object.create(scope.window.PointCloudViewer.prototype);
  const uploads = [];
  Object.assign(viewer,{status:{},loadSequence:0,gl:{bindBuffer(){},bufferData(_target, values){uploads.push([...values]);},isContextLost(){return false;}},draw(){},canvas:{dispatchEvent(){}}});
  await viewer.load("/api/public/share/content", options);
  assert.equal(viewer.readiness, null, "Download and draw do not imply browser readiness");
  animationFrames.splice(0).forEach(callback => callback());
  assert.equal(viewer.readiness, null, "Wait for the second animation frame");
  animationFrames.splice(0).forEach(callback => callback());
  assert.ok(viewer.readiness.browserReadySeconds >= viewer.readiness.downloadSeconds);
  return {viewer,request,uploads};
}
(async()=>{
  const expectedPositions = [...new Float32Array([-5/7, 1, -3/7, 5/7, -1, 3/7])];
  const expectedColors = [...new Float32Array([0, 128/255, 1, 1, 64/255, 32/255])];
  for (const layout of [{}, { interleaved: true }, { unaligned: true }, { floatColors: true }, { rgb: true }]) {
    const bytes = accessorGlb(layout), original = Buffer.from(bytes).toString("hex");
    const { uploads } = await load(bytes);
    assert.deepEqual(uploads[0], expectedPositions, "Coordinate normalization is identical for every supported layout");
    assert.deepEqual(uploads[1], expectedColors, "RGB/RGBA byte and float colors retain exact Float32 values");
    assert.equal(Buffer.from(bytes).toString("hex"), original, "Parsing never mutates the downloaded artifact");
  }
  const sampleBytes = accessorGlb({ change(doc) { doc.extras = { sampleVersion: "synthetic-studio-v1" }; } });
  const sampleOriginal = Buffer.from(sampleBytes).toString("hex");
  await load(sampleBytes);
  assert.equal(Buffer.from(sampleBytes).toString("hex"), sampleOriginal, "Sample orientation mutates only owned coordinates");
  await assert.rejects(load(accessorGlb({ change(doc) { doc.bufferViews[0].byteLength--; } })), /exceeds/);
  await assert.rejects(load(accessorGlb({ change(doc) { doc.bufferViews[1].byteLength--; } })), /exceeds/);
  await assert.rejects(load(accessorGlb({ change(doc) { doc.accessors[1].count = 1; } })), /match the scene/);
  await assert.rejects(load(accessorGlb({ change(doc) { doc.accessors[1].normalized = false; } })), /finite normalized/);
  await assert.rejects(load(accessorGlb({ change(doc) { doc.accessors[0].count = 2_000_001; } })), /unsupported accessor/);
  await assert.rejects(load(accessorGlb({ change(_doc, bytes) { bytes.writeFloatLE(NaN, 8); } })), /non-finite coordinate/);
  await assert.rejects(load(accessorGlb({ floatColors: true, change(_doc, bytes) { bytes.writeFloatLE(2, 80); } })), /finite normalized/);
  const {viewer,request}=await load(glb(),{headers:{Authorization:"Bearer private-capability"}});
  assert.equal(request.url.includes("private-capability"),false);
  assert.equal(request.init.headers.Authorization,"Bearer private-capability");
  assert.equal(viewer.count,6);
  const prefetched = await load(new ArrayBuffer(0), { prefetchedResponse: { ok: true, arrayBuffer: async () => glb() } });
  assert.equal(prefetched.viewer.count, 6);
  assert.equal(prefetched.request, undefined, "A capability response can be rendered without another fetch or a blob URL");
  const untraced = await load(glb(d => { delete d.extras; }));
  assert.deepEqual([...untraced.viewer.center], [...viewer.center], "Untraced glTF retains Y-up coordinates");
  const sample = await load(glb(d => { d.extras = {sampleVersion:"synthetic-studio-v1"}; }));
  assert.deepEqual([...sample.viewer.center], [viewer.center[0], viewer.center[2], -viewer.center[1]], "Only the authored sample rotates from Z-up");
  const calibration = scope.window.PointCloudViewer.cameraProjection(viewer.trace.frames[0], 390, 844);
  assert.equal(calibration.viewport[2], 390);
  assert.equal(calibration.viewport[3], 293);
  assert.equal(calibration.projection[0], 1.25);
  assert.equal(calibration.projection[1], 1000/480);
  assert.equal(calibration.projection[2], -0.0625);
  assert.equal(calibration.projection[3], 1-400/480);
  viewer.setFrame(0); assert.equal(viewer.visibleCount,3);
  const sourcePosition = [...viewer.trace.frames[0].position];
  viewer.startWalk();
  viewer.moveWalk(1, 1);
  assert.equal(viewer.walking, true);
  assert.equal(viewer.visibleCount, 6);
  assert.notDeepEqual([...viewer.cameraFrame.position], sourcePosition);
  assert.deepEqual([...viewer.trace.frames[0].position], sourcePosition, "Walking never mutates the captured path");
  viewer.setFrame(0); assert.equal(viewer.walking, false);
  viewer.zoom(0.8); assert.equal(viewer.cameraFrame,null); assert.equal(viewer.visibleCount,6);
  viewer.setFrame(1); viewer.reset(); assert.equal(viewer.visibleCount,6);
  await assert.rejects(load(glb(d=>{d.nodes[0].translation=[10,0,0];})),/baked coordinates/);
  await assert.rejects(load(glb(d=>{d.extras.wayline.frames[1].time=0;})),/source-frame/);
  await assert.rejects(load(glb(d=>{d.extras.wayline.frames[0].right=[0,0,0];})),/orthonormal/);
  await assert.rejects(load(glb(d=>{d.extras.wayline.frames[1].pointEnd=5;})),/does not cover/);
  await assert.rejects(load(glb(d=>{d.extras.wayline.coordinateSystem="z-up";})),/camera trace/);
  await assert.rejects(load(glb(d=>{d.extras.wayline.frames[0].intrinsics[0]=0;})),/source-frame/);
  const landingBuffer = fs.readFileSync(path.join(__dirname, "../lingbot_map/workspace/static/landing-scene.glb"));
  assert.ok(landingBuffer.length <= 1_500_000, "The public presentation stays within its transfer budget");
  const { viewer: landing } = await load(landingBuffer.buffer.slice(landingBuffer.byteOffset, landingBuffer.byteOffset + landingBuffer.byteLength));
  assert.equal(landing.count, 75_000);
  assert.equal(landing.trace.frames.length, 30);
  assert.equal(landing.trace.frames.at(-1).pointEnd, landing.count, "The reduced cloud still has a complete camera trace");
  console.log("viewer trace contract passed");
})().catch(error=>{console.error(error);process.exitCode=1;});
