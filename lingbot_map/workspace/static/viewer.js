"use strict";

(function exposeViewer() {
  const componentInfo = {
    5120: { bytes: 1, getter: "getInt8" },
    5121: { bytes: 1, getter: "getUint8" },
    5122: { bytes: 2, getter: "getInt16" },
    5123: { bytes: 2, getter: "getUint16" },
    5125: { bytes: 4, getter: "getUint32" },
    5126: { bytes: 4, getter: "getFloat32" },
  };
  const componentCount = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4 };

  function parseGlb(buffer) {
    const view = new DataView(buffer);
    if (view.byteLength < 20 || view.getUint32(0, true) !== 0x46546c67) {
      throw new Error("Artifact is not a valid binary glTF file.");
    }
    if (view.getUint32(4, true) !== 2 || view.getUint32(8, true) !== view.byteLength) {
      throw new Error("Only complete glTF 2.0 binary artifacts are supported.");
    }
    let offset = 12;
    let document = null;
    let binary = null;
    while (offset + 8 <= view.byteLength) {
      const length = view.getUint32(offset, true);
      const type = view.getUint32(offset + 4, true);
      const start = offset + 8;
      if (start + length > view.byteLength) throw new Error("Artifact contains a truncated chunk.");
      if (type === 0x4e4f534a) {
        const source = new TextDecoder().decode(new Uint8Array(buffer, start, length)).replace(/\0+$/u, "");
        document = JSON.parse(source);
      } else if (type === 0x004e4942) {
        binary = new Uint8Array(buffer, start, length);
      }
      offset = start + length;
    }
    if (!document || !binary) throw new Error("Artifact must include JSON and binary chunks.");
    const node = document.nodes?.[0];
    const primitive = document.meshes?.[0]?.primitives?.[0];
    if (document.meshes?.length !== 1 || document.nodes?.length !== 1
        || document.meshes[0].primitives?.length !== 1 || node.mesh !== 0
        || ["matrix", "translation", "rotation", "scale", "children"].some((key) => key in node)
        || !primitive || primitive.mode !== 0 || primitive.indices != null
        || primitive.material != null || primitive.attributes?.POSITION == null) {
      throw new Error("This viewer requires one point cloud with baked coordinates and vertex colors.");
    }

    function readAccessor(index) {
      if (!Number.isInteger(index) || index < 0 || !Array.isArray(document.accessors)) {
        throw new Error("Artifact references an invalid accessor.");
      }
      const accessor = document.accessors[index];
      if (!accessor || typeof accessor !== "object" || accessor.sparse
          || !Number.isInteger(accessor.bufferView) || accessor.bufferView < 0
          || !Number.isInteger(accessor.count) || accessor.count < 1
          || accessor.count > 2_000_000 || !Array.isArray(document.bufferViews)) {
        throw new Error("Artifact uses an unsupported accessor layout.");
      }
      const bufferView = document.bufferViews[accessor.bufferView];
      const info = componentInfo[accessor.componentType];
      const width = componentCount[accessor.type];
      if (!bufferView || typeof bufferView !== "object" || bufferView.buffer !== 0
          || !info || !width) {
        throw new Error("Artifact uses an unsupported accessor layout.");
      }
      const elementBytes = info.bytes * width;
      const viewOffset = bufferView.byteOffset || 0;
      const accessorOffset = accessor.byteOffset || 0;
      const viewLength = bufferView.byteLength;
      const stride = bufferView.byteStride || elementBytes;
      if (![viewOffset, accessorOffset, viewLength, stride].every(Number.isSafeInteger)
          || viewOffset < 0 || accessorOffset < 0 || viewLength < 0
          || stride < elementBytes || stride > 252 || stride % info.bytes !== 0) {
        throw new Error("Artifact contains invalid buffer offsets.");
      }
      const base = viewOffset + accessorOffset;
      const end = base + (accessor.count - 1) * stride + elementBytes;
      if (!Number.isSafeInteger(end) || base < viewOffset
          || end > viewOffset + viewLength || end > binary.byteLength) {
        throw new Error("Artifact accessor exceeds its binary buffer.");
      }
      const result = new Float32Array(accessor.count * width);
      const data = new DataView(binary.buffer, binary.byteOffset, binary.byteLength);
      for (let row = 0; row < accessor.count; row += 1) {
        for (let column = 0; column < width; column += 1) {
          const value = data[info.getter](base + row * stride + column * info.bytes, true);
          let normalized = value;
          if (accessor.normalized) {
            if (accessor.componentType === 5121) normalized = value / 255;
            else if (accessor.componentType === 5123) normalized = value / 65535;
            else if (accessor.componentType === 5120) normalized = Math.max(-1, value / 127);
            else if (accessor.componentType === 5122) normalized = Math.max(-1, value / 32767);
          }
          result[row * width + column] = normalized;
        }
      }
      return { values: result, width, count: accessor.count };
    }

    const positions = readAccessor(primitive.attributes.POSITION);
    if (positions.width !== 3) {
      throw new Error("Point cloud must contain at most two million 3D points.");
    }
    let colors = null;
    if (primitive.attributes.COLOR_0 != null) colors = readAccessor(primitive.attributes.COLOR_0);
    if (colors && ![3, 4].includes(colors.width)) {
      throw new Error("Point colors must use RGB or RGBA values.");
    }
    if (colors && (colors.count !== positions.count || colors.values.some((value) => !Number.isFinite(value) || value < 0 || value > 1))) {
      throw new Error("Point colors must match the scene and use finite normalized values.");
    }
    const trace = document.extras?.wayline;
    if (trace != null) {
      if (trace.version !== 1 || trace.kind !== "reconstruction" || trace.coordinateSystem !== "gltf-y-up"
          || trace.pointCount !== positions.count || !Array.isArray(trace.frames)
          || trace.frames.length < 2 || trace.frames.length > 120) throw new Error("Invalid camera trace.");
      let lastTime = -1, lastPoint = 0;
      for (const frame of trace.frames) {
        if (!Number.isFinite(frame.time) || frame.time <= lastTime || !Number.isInteger(frame.pointEnd)
            || frame.pointEnd < lastPoint || frame.pointEnd > positions.count
            || !Number.isFinite(frame.fov) || frame.fov <= 0 || frame.fov >= Math.PI
            || !Array.isArray(frame.imageSize) || frame.imageSize.length !== 2
            || !frame.imageSize.every((value) => Number.isInteger(value) && value > 0 && value <= 4096)
            || !Array.isArray(frame.intrinsics) || frame.intrinsics.length !== 4
            || !frame.intrinsics.every(Number.isFinite) || frame.intrinsics[0] <= 0 || frame.intrinsics[1] <= 0
            || ![frame.position, frame.right, frame.up, frame.forward].every(
              (v) => Array.isArray(v) && v.length === 3 && v.every(Number.isFinite))
            || typeof frame.thumbnail !== "string" || frame.thumbnail.length > 100000
            || !/^data:image\/jpeg;base64,[A-Za-z0-9+/=]+$/.test(frame.thumbnail)) {
          throw new Error("Invalid source-frame data.");
        }
        const axes = [frame.right, frame.up, frame.forward];
        const dot = (a, b) => a.reduce((sum, value, index) => sum + value * b[index], 0);
        if (axes.some((axis) => Math.abs(dot(axis, axis) - 1) > 0.01)
            || Math.abs(dot(axes[0], axes[1])) > 0.01 || Math.abs(dot(axes[0], axes[2])) > 0.01
            || Math.abs(dot(axes[1], axes[2])) > 0.01) throw new Error("Camera orientation must be orthonormal.");
        lastTime = frame.time; lastPoint = frame.pointEnd;
      }
      if (lastPoint !== positions.count) throw new Error("Camera trace does not cover this scene.");
    }
    return { positions, colors, trace };
  }

  function shader(gl, type, source) {
    const value = gl.createShader(type);
    gl.shaderSource(value, source);
    gl.compileShader(value);
    if (!gl.getShaderParameter(value, gl.COMPILE_STATUS)) {
      throw new Error(gl.getShaderInfoLog(value) || "WebGL shader failed to compile.");
    }
    return value;
  }

  class PointCloudViewer {
    constructor(canvas, status) {
      this.canvas = canvas;
      this.status = status;
      this.gl = canvas.getContext("webgl", { antialias: true, alpha: false });
      if (!this.gl) throw new Error("WebGL is unavailable in this browser.");
      this.yaw = -0.65;
      this.pitch = -0.38;
      this.distance = 3.2;
      this.count = 0;
      this.drag = null;
      this.loadSequence = 0;
      this.destroyed = false;
      this.events = new AbortController();
      this.loadController = null;
      this.initializeGraphics();
      this.bindControls();
      this.resizeObserver = new ResizeObserver(() => this.draw());
      this.resizeObserver.observe(canvas);
    }

    initializeGraphics() {
      const gl = this.gl;
      const vertex = shader(gl, gl.VERTEX_SHADER, `
        attribute vec3 aPosition;
        attribute vec3 aColor;
        uniform float uYaw;
        uniform float uPitch;
        uniform float uDistance;
        uniform float uAspect;
        uniform float uPointSize;
        uniform bool uCamera;
        uniform vec3 uEye;
        uniform vec3 uRight;
        uniform vec3 uUp;
        uniform vec3 uForward;
        uniform vec4 uProjection;
        varying vec3 vColor;
        void main() {
          float cy = cos(uYaw); float sy = sin(uYaw);
          float cp = cos(uPitch); float sp = sin(uPitch);
          vec3 first = vec3(cy * aPosition.x - sy * aPosition.z, aPosition.y, sy * aPosition.x + cy * aPosition.z);
          vec3 point = vec3(first.x, cp * first.y - sp * first.z, sp * first.y + cp * first.z - uDistance);
          float near = 0.001; float far = 100.0; float focal = 2.41421356;
          if (uCamera) {
            vec3 delta = aPosition - uEye;
            point = vec3(dot(delta, uRight), dot(delta, uUp), -dot(delta, uForward));
          }
          vec2 projected = uCamera ? point.xy * uProjection.xy - point.z * uProjection.zw
            : vec2(point.x * focal / uAspect, point.y * focal);
          gl_Position = vec4(projected,
            ((far + near) / (near - far)) * point.z + (2.0 * far * near / (near - far)), -point.z);
          gl_PointSize = uPointSize;
          vColor = aColor;
        }
      `);
      const fragment = shader(gl, gl.FRAGMENT_SHADER, `
        precision mediump float;
        varying vec3 vColor;
        uniform bool uLines;
        void main() {
          vec2 offset = gl_PointCoord - vec2(0.5);
          if (!uLines && dot(offset, offset) > 0.25) discard;
          gl_FragColor = vec4(vColor, 1.0);
        }
      `);
      const program = gl.createProgram();
      gl.attachShader(program, vertex);
      gl.attachShader(program, fragment);
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
        throw new Error(gl.getProgramInfoLog(program) || "WebGL program failed to link.");
      }
      this.program = program;
      this.vertexShader = vertex;
      this.fragmentShader = fragment;
      this.locations = {
        position: gl.getAttribLocation(program, "aPosition"),
        color: gl.getAttribLocation(program, "aColor"),
        yaw: gl.getUniformLocation(program, "uYaw"),
        pitch: gl.getUniformLocation(program, "uPitch"),
        distance: gl.getUniformLocation(program, "uDistance"),
        aspect: gl.getUniformLocation(program, "uAspect"),
        pointSize: gl.getUniformLocation(program, "uPointSize"),
        camera: gl.getUniformLocation(program, "uCamera"),
        eye: gl.getUniformLocation(program, "uEye"),
        right: gl.getUniformLocation(program, "uRight"),
        up: gl.getUniformLocation(program, "uUp"),
        forward: gl.getUniformLocation(program, "uForward"),
        projection: gl.getUniformLocation(program, "uProjection"),
        lines: gl.getUniformLocation(program, "uLines"),
      };
      this.positionBuffer = gl.createBuffer();
      this.colorBuffer = gl.createBuffer();
      this.pathBuffer = gl.createBuffer();
    }

    bindControls() {
      const signal = this.events.signal;
      this.canvas.addEventListener("pointerdown", (event) => {
        if (!this.walking) this.orbit();
        this.canvas.setPointerCapture(event.pointerId);
        this.drag = { id: event.pointerId, x: event.clientX, y: event.clientY };
      }, { signal });
      this.canvas.addEventListener("pointermove", (event) => {
        if (!this.drag || event.pointerId !== this.drag.id) return;
        if (this.walking) {
          this.lookWalk((event.clientX - this.drag.x) * 0.008, -(event.clientY - this.drag.y) * 0.008);
        } else {
          this.yaw += (event.clientX - this.drag.x) * 0.008;
          this.pitch = Math.max(-1.45, Math.min(1.45, this.pitch + (event.clientY - this.drag.y) * 0.008));
        }
        this.drag.x = event.clientX;
        this.drag.y = event.clientY;
        this.draw();
      }, { signal });
      const stopDrag = (event) => {
        if (this.drag?.id === event.pointerId) this.drag = null;
      };
      this.canvas.addEventListener("pointerup", stopDrag, { signal });
      this.canvas.addEventListener("pointercancel", stopDrag, { signal });
      this.canvas.addEventListener("wheel", (event) => {
        event.preventDefault();
        this.zoom(Math.exp(event.deltaY * 0.001));
      }, { passive: false, signal });
      this.canvas.addEventListener("keydown", (event) => {
        const key = event.key;
        if (this.walking) {
          const movement = {w:[1,0], s:[-1,0], a:[0,-1], d:[0,1]};
          const looking = {ArrowLeft:[-0.12,0], ArrowRight:[0.12,0], ArrowUp:[0,0.1], ArrowDown:[0,-0.1]};
          if (movement[key.toLowerCase()]) {
            event.preventDefault(); this.moveWalk(...movement[key.toLowerCase()]); return;
          }
          if (looking[key]) {
            event.preventDefault(); this.lookWalk(...looking[key]); this.draw(); return;
          }
        }
        if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "+", "=", "-", "0"].includes(key)) {
          event.preventDefault();
        } else return;
        this.orbit();
        if (key === "ArrowLeft") this.yaw -= 0.12;
        else if (key === "ArrowRight") this.yaw += 0.12;
        else if (key === "ArrowUp") this.pitch = Math.max(-1.45, this.pitch - 0.1);
        else if (key === "ArrowDown") this.pitch = Math.min(1.45, this.pitch + 0.1);
        else if (key === "+" || key === "=") this.distance = Math.max(0.05, this.distance * 0.9);
        else if (key === "-") this.distance = Math.min(8, this.distance * 1.1);
        else if (key === "0") { this.yaw = -0.65; this.pitch = -0.38; this.distance = 3.2; }
        else return;
        this.draw();
      }, { signal });
    }

    async load(url, { headers = {} } = {}) {
      if (this.destroyed) throw new Error("The viewer has been closed.");
      const sequence = ++this.loadSequence;
      if (this.loadController) this.loadController.abort();
      this.loadController = new AbortController();
      this.status.textContent = "Loading stored point cloud.";
      const response = await fetch(url, {
        credentials: "same-origin",
        headers,
        signal: this.loadController.signal,
      });
      if (!response.ok) throw new Error("The stored scene could not be loaded.");
      const parsed = parseGlb(await response.arrayBuffer());
      if (this.destroyed || sequence !== this.loadSequence) return;
      const raw = parsed.positions.values;
      if (!parsed.trace) {
        // The authored sample is Z-up; reconstruction exports are glTF Y-up.
        for (let index = 0; index < raw.length; index += 3) {
          const y = raw[index + 1]; raw[index + 1] = raw[index + 2]; raw[index + 2] = -y;
        }
      }
      const minimum = [Infinity, Infinity, Infinity];
      const maximum = [-Infinity, -Infinity, -Infinity];
      for (let index = 0; index < raw.length; index += 3) {
        for (let axis = 0; axis < 3; axis += 1) {
          if (!Number.isFinite(raw[index + axis])) {
            throw new Error("Point cloud contains a non-finite coordinate.");
          }
          minimum[axis] = Math.min(minimum[axis], raw[index + axis]);
          maximum[axis] = Math.max(maximum[axis], raw[index + axis]);
        }
      }
      const center = minimum.map((value, axis) => (value + maximum[axis]) / 2);
      const extent = Math.max(...maximum.map((value, axis) => value - minimum[axis])) || 1;
      this.trace = parsed.trace || null;
      this.center = center;
      this.extent = extent;
      this.cameraFrame = null;
      this.walking = false;
      const positions = new Float32Array(raw.length);
      for (let index = 0; index < raw.length; index += 3) {
        positions[index] = (raw[index] - center[0]) / extent * 2;
        positions[index + 1] = (raw[index + 1] - center[1]) / extent * 2;
        positions[index + 2] = (raw[index + 2] - center[2]) / extent * 2;
      }
      const colors = new Float32Array(parsed.positions.count * 3);
      if (parsed.colors && parsed.colors.count === parsed.positions.count) {
        const width = parsed.colors.width;
        for (let row = 0; row < parsed.colors.count; row += 1) {
          colors[row * 3] = parsed.colors.values[row * width];
          colors[row * 3 + 1] = parsed.colors.values[row * width + 1];
          colors[row * 3 + 2] = parsed.colors.values[row * width + 2];
        }
      } else {
        colors.fill(0.78);
      }
      const gl = this.gl;
      gl.bindBuffer(gl.ARRAY_BUFFER, this.positionBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, positions, gl.STATIC_DRAW);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.colorBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, colors, gl.STATIC_DRAW);
      this.count = parsed.positions.count;
      this.visibleCount = this.count;
      if (this.trace) {
        const path = this.trace.frames.flatMap((frame) => this.normalizePoint(frame.position));
        gl.bindBuffer(gl.ARRAY_BUFFER, this.pathBuffer);
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(path), gl.STATIC_DRAW);
      }
      this.status.textContent = `${this.count.toLocaleString()} points loaded. Drag or use arrow keys to orbit.`;
      this.draw();
    }

    normalizePoint(point) { return point.map((value, axis) => (value-this.center[axis])/this.extent*2); }

    setFrame(index) {
      if (!this.trace || !Number.isInteger(index) || index < 0 || index >= this.trace.frames.length) return;
      this.cameraFrame = this.trace.frames[index];
      this.walking = false;
      this.visibleCount = this.cameraFrame.pointEnd;
      this.draw();
    }

    reset() {
      this.walking = false;
      this.cameraFrame = null; this.visibleCount = this.count;
      this.yaw = -0.65; this.pitch = -0.38; this.distance = 3.2;
      this.draw();
    }

    zoom(factor) {
      if (this.walking) { this.moveWalk(factor < 1 ? 1 : -1, 0); return; }
      this.orbit();
      this.distance = Math.max(0.05, Math.min(8, this.distance*factor));
      this.draw();
    }

    orbit() {
      this.walking = false;
      this.cameraFrame = null;
      this.visibleCount = this.count;
      this.canvas.dispatchEvent(new CustomEvent("viewmode", { detail: "FREE ORBIT" }));
    }

    startWalk() {
      const frame = this.cameraFrame || this.trace?.frames[0];
      if (!frame) return;
      this.cameraFrame = {...frame, position: [...frame.position]};
      this.walkYaw = Math.atan2(frame.forward[0], -frame.forward[2]);
      this.walkPitch = Math.asin(Math.max(-1, Math.min(1, frame.forward[1])));
      this.walking = true;
      this.visibleCount = this.count;
      this.lookWalk(0, 0);
      this.canvas.dispatchEvent(new CustomEvent("viewmode", { detail: "WALK VIEW" }));
      this.draw();
    }

    lookWalk(yaw, pitch) {
      if (!this.walking) return;
      this.walkYaw += yaw;
      this.walkPitch = Math.max(-1.45, Math.min(1.45, this.walkPitch + pitch));
      const sy = Math.sin(this.walkYaw), cy = Math.cos(this.walkYaw);
      const sp = Math.sin(this.walkPitch), cp = Math.cos(this.walkPitch);
      Object.assign(this.cameraFrame, {
        forward: [sy*cp, sp, -cy*cp], right: [cy, 0, sy], up: [-sy*sp, cp, cy*sp],
      });
    }

    moveWalk(forward, sideways) {
      if (!this.walking) return;
      const step = this.extent * 0.025;
      this.cameraFrame.position[0] += (Math.sin(this.walkYaw)*forward + Math.cos(this.walkYaw)*sideways)*step;
      this.cameraFrame.position[2] += (-Math.cos(this.walkYaw)*forward + Math.sin(this.walkYaw)*sideways)*step;
      this.draw();
    }

    static cameraProjection(frame, width, height) {
      const [sourceWidth, sourceHeight] = frame.imageSize;
      const [fx, fy, cx, cy] = frame.intrinsics;
      const scale = Math.min(width / sourceWidth, height / sourceHeight);
      const viewWidth = Math.max(1, Math.round(sourceWidth * scale));
      const viewHeight = Math.max(1, Math.round(sourceHeight * scale));
      return {
        viewport: [Math.round((width-viewWidth)/2), Math.round((height-viewHeight)/2), viewWidth, viewHeight],
        projection: [2*fx/sourceWidth, 2*fy/sourceHeight, 2*cx/sourceWidth-1, 1-2*cy/sourceHeight],
      };
    }

    draw() {
      if (this.destroyed) return;
      const gl = this.gl;
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      const width = Math.max(1, Math.round(this.canvas.clientWidth * ratio));
      const height = Math.max(1, Math.round(this.canvas.clientHeight * ratio));
      if (this.canvas.width !== width || this.canvas.height !== height) {
        this.canvas.width = width;
        this.canvas.height = height;
      }
      gl.viewport(0, 0, width, height);
      gl.clearColor(0.055, 0.067, 0.047, 1);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      if (!this.count) return;
      gl.enable(gl.DEPTH_TEST);
      gl.useProgram(this.program);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.positionBuffer);
      gl.enableVertexAttribArray(this.locations.position);
      gl.vertexAttribPointer(this.locations.position, 3, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.colorBuffer);
      gl.enableVertexAttribArray(this.locations.color);
      gl.vertexAttribPointer(this.locations.color, 3, gl.FLOAT, false, 0, 0);
      gl.uniform1f(this.locations.yaw, this.yaw);
      gl.uniform1f(this.locations.pitch, this.pitch);
      gl.uniform1f(this.locations.distance, this.distance);
      gl.uniform1f(this.locations.aspect, width / height);
      gl.uniform1f(this.locations.pointSize, Math.max(2, 2.4 * ratio));
      const frame = this.cameraFrame;
      gl.uniform1i(this.locations.camera, Boolean(frame));
      gl.uniform1i(this.locations.lines, false);
      if (frame) {
        const calibration = PointCloudViewer.cameraProjection(frame, width, height);
        gl.viewport(...calibration.viewport);
        gl.uniform3fv(this.locations.eye, this.normalizePoint(frame.position));
        gl.uniform3fv(this.locations.right, frame.right);
        gl.uniform3fv(this.locations.up, frame.up);
        gl.uniform3fv(this.locations.forward, frame.forward);
        gl.uniform4fv(this.locations.projection, calibration.projection);
      }
      gl.drawArrays(gl.POINTS, 0, this.visibleCount ?? this.count);
      if (this.trace && !frame) {
        gl.uniform1i(this.locations.lines, true);
        gl.bindBuffer(gl.ARRAY_BUFFER, this.pathBuffer);
        gl.vertexAttribPointer(this.locations.position, 3, gl.FLOAT, false, 0, 0);
        gl.disableVertexAttribArray(this.locations.color);
        gl.vertexAttrib3f(this.locations.color, 0.85, 0.96, 0.52);
        gl.drawArrays(gl.LINE_STRIP, 0, this.trace.frames.length);
      }
    }

    destroy() {
      if (this.destroyed) return;
      this.destroyed = true;
      this.loadSequence += 1;
      if (this.loadController) this.loadController.abort();
      this.events.abort();
      this.resizeObserver.disconnect();
      const gl = this.gl;
      if (this.positionBuffer) gl.deleteBuffer(this.positionBuffer);
      if (this.colorBuffer) gl.deleteBuffer(this.colorBuffer);
      if (this.pathBuffer) gl.deleteBuffer(this.pathBuffer);
      if (this.program) gl.deleteProgram(this.program);
      if (this.vertexShader) gl.deleteShader(this.vertexShader);
      if (this.fragmentShader) gl.deleteShader(this.fragmentShader);
      const loseContext = gl.getExtension("WEBGL_lose_context");
      if (loseContext) loseContext.loseContext();
      // A lost WebGL context belongs to its canvas. Give the next scene a
      // fresh element while retaining its dimensions, labels, and keyboard target.
      this.canvas.replaceWith(this.canvas.cloneNode(false));
      this.count = 0;
      this.drag = null;
      this.status.textContent = "Viewer closed.";
    }
  }

  window.PointCloudViewer = PointCloudViewer;
}());
