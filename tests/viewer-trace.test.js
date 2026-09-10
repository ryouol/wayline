"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const scope = {window: {}, AbortController, TextDecoder,
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
  let json=JSON.stringify(doc); while(json.length%4) json+=" ";
  const binary=Buffer.alloc(72);
  for(let i=0;i<18;i++) binary.writeFloatLE(i/10,i*4);
  const result=Buffer.alloc(12+8+json.length+8+binary.length);
  result.writeUInt32LE(0x46546c67,0); result.writeUInt32LE(2,4); result.writeUInt32LE(result.length,8);
  result.writeUInt32LE(json.length,12); result.writeUInt32LE(0x4e4f534a,16); result.write(json,20);
  result.writeUInt32LE(binary.length,20+json.length); result.writeUInt32LE(0x004e4942,24+json.length); binary.copy(result,28+json.length);
  return result.buffer.slice(result.byteOffset,result.byteOffset+result.length);
}
async function load(buffer, options) {
  let request;
  scope.fetch=async (url, init) => {request={url,init}; return {ok:true,arrayBuffer:async()=>buffer};};
  const viewer=Object.create(scope.window.PointCloudViewer.prototype);
  Object.assign(viewer,{status:{},loadSequence:0,gl:{bindBuffer(){},bufferData(){}},draw(){},canvas:{dispatchEvent(){}}});
  await viewer.load("/api/public/share/content", options);
  return {viewer,request};
}
(async()=>{
  const {viewer,request}=await load(glb(),{headers:{Authorization:"Bearer private-capability"}});
  assert.equal(request.url.includes("private-capability"),false);
  assert.equal(request.init.headers.Authorization,"Bearer private-capability");
  assert.equal(viewer.count,6);
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
  console.log("viewer trace contract passed");
})().catch(error=>{console.error(error);process.exitCode=1;});
