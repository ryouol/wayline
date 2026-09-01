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
    const primitive = document.meshes?.[0]?.primitives?.find((item) => item.mode === 0);
    if (!primitive || primitive.attributes?.POSITION == null) {
      throw new Error("This viewer currently supports GLB point-cloud primitives.");
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
    return { positions, colors };
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
        varying vec3 vColor;
        void main() {
          float cy = cos(uYaw); float sy = sin(uYaw);
          float cp = cos(uPitch); float sp = sin(uPitch);
          vec3 first = vec3(cy * aPosition.x - sy * aPosition.z, aPosition.y, sy * aPosition.x + cy * aPosition.z);
          vec3 point = vec3(first.x, cp * first.y - sp * first.z, sp * first.y + cp * first.z - uDistance);
          float near = 0.1; float far = 100.0; float focal = 2.41421356;
          gl_Position = vec4(point.x * focal / uAspect, point.y * focal,
            ((far + near) / (near - far)) * point.z + (2.0 * far * near / (near - far)), -point.z);
          gl_PointSize = uPointSize;
          vColor = aColor;
        }
      `);
      const fragment = shader(gl, gl.FRAGMENT_SHADER, `
        precision mediump float;
        varying vec3 vColor;
        void main() {
          vec2 offset = gl_PointCoord - vec2(0.5);
          if (dot(offset, offset) > 0.25) discard;
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
      };
      this.positionBuffer = gl.createBuffer();
      this.colorBuffer = gl.createBuffer();
    }

    bindControls() {
      const signal = this.events.signal;
      this.canvas.addEventListener("pointerdown", (event) => {
        this.canvas.setPointerCapture(event.pointerId);
        this.drag = { id: event.pointerId, x: event.clientX, y: event.clientY };
      }, { signal });
      this.canvas.addEventListener("pointermove", (event) => {
        if (!this.drag || event.pointerId !== this.drag.id) return;
        this.yaw += (event.clientX - this.drag.x) * 0.008;
        this.pitch = Math.max(-1.45, Math.min(1.45, this.pitch + (event.clientY - this.drag.y) * 0.008));
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
        this.distance = Math.max(1.4, Math.min(8, this.distance * Math.exp(event.deltaY * 0.001)));
        this.draw();
      }, { passive: false, signal });
      this.canvas.addEventListener("keydown", (event) => {
        const key = event.key;
        if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "+", "=", "-", "0"].includes(key)) {
          event.preventDefault();
        }
        if (key === "ArrowLeft") this.yaw -= 0.12;
        else if (key === "ArrowRight") this.yaw += 0.12;
        else if (key === "ArrowUp") this.pitch = Math.max(-1.45, this.pitch - 0.1);
        else if (key === "ArrowDown") this.pitch = Math.min(1.45, this.pitch + 0.1);
        else if (key === "+" || key === "=") this.distance = Math.max(1.4, this.distance * 0.9);
        else if (key === "-") this.distance = Math.min(8, this.distance * 1.1);
        else if (key === "0") { this.yaw = -0.65; this.pitch = -0.38; this.distance = 3.2; }
        else return;
        this.draw();
      }, { signal });
    }

    async load(url) {
      if (this.destroyed) throw new Error("The viewer has been closed.");
      const sequence = ++this.loadSequence;
      if (this.loadController) this.loadController.abort();
      this.loadController = new AbortController();
      this.status.textContent = "Loading stored point cloud.";
      const response = await fetch(url, {
        credentials: "same-origin",
        signal: this.loadController.signal,
      });
      if (!response.ok) throw new Error("The stored scene could not be loaded.");
      const parsed = parseGlb(await response.arrayBuffer());
      if (this.destroyed || sequence !== this.loadSequence) return;
      const raw = parsed.positions.values;
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
      this.status.textContent = `${this.count.toLocaleString()} points loaded. Drag or use arrow keys to orbit.`;
      this.draw();
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
      gl.clearColor(0.031, 0.047, 0.067, 1);
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
      gl.drawArrays(gl.POINTS, 0, this.count);
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
      if (this.program) gl.deleteProgram(this.program);
      if (this.vertexShader) gl.deleteShader(this.vertexShader);
      if (this.fragmentShader) gl.deleteShader(this.fragmentShader);
      const loseContext = gl.getExtension("WEBGL_lose_context");
      if (loseContext) loseContext.loseContext();
      this.count = 0;
      this.drag = null;
      this.status.textContent = "Viewer closed.";
    }
  }

  window.PointCloudViewer = PointCloudViewer;
}());
