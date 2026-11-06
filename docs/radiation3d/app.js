// "Sombras y radiación 3D": Rhino .3dm + EPW -> shadows on the key days and cumulative radiation.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { readModel } from "./rhino.js";
import { parseEpw, skyMatrices, daySuns, solarPosition, sunVector, KEY_DAYS } from "./sky.js";

const RHINO_URL = "https://cdn.jsdelivr.net/npm/rhino3dm@8.17.0/rhino3dm.module.min.js";
const PALETTE = ["#4b6ba9", "#7393ca", "#aac8f7", "#c1d5d0", "#f5ef67", "#fce64a", "#ef9c15", "#ea7b00", "#ea4a00", "#ea2600"];
const ROLE_COLOR = { context: 0xdfe2e8, analysis: 0xf6c99a };
const PERIOD = { annual: "Anual", summer: "Verano", winter: "Invierno" };
const MAX_POINTS = 150000;

const $ = (id) => document.getElementById(id);
const S = {
  rh: null, model: null, epw: null, roles: new Map(), meshes: new Map(), offset: [0, 0, 0], radius: 50,
  home: new THREE.Vector3(), mode: "shadow", period: "annual", radiation: null, sunhours: null, sceneKey: null, playing: false,
};

// ---------------------------------------------------------------- status / busy
function status(msg, error = false) { const s = $("status"); s.textContent = msg; s.classList.toggle("is-error", error); }
function busy(title, text) { $("busy-title").textContent = title; $("busy-text").textContent = text || ""; $("busy-bar").style.width = "0";
  $("busy").classList.add("show"); }
const progress = (f) => { $("busy-bar").style.width = `${Math.round(100 * f)}%`; };
const idle = () => $("busy").classList.remove("show");
const nextFrame = () => new Promise((r) => requestAnimationFrame(() => setTimeout(r, 0)));

// ---------------------------------------------------------------- three.js scene
const viewer = $("viewer");
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(2, window.devicePixelRatio));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.setClearColor(0xf4f6f9);
viewer.prepend(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100000);
camera.up.set(0, 0, 1);
camera.position.set(-80, -120, 90);
// Navigation: left drag = orbit, right drag / shift + left = pan, wheel = zoom towards the cursor,
// double click = orbit around that point. Damped (inertia) and rendered on demand.
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.12;
controls.rotateSpeed = 0.7;
controls.zoomSpeed = 1.1;
controls.panSpeed = 0.9;
controls.zoomToCursor = true;
controls.screenSpacePanning = true;
controls.maxPolarAngle = Math.PI * 0.495;  // do not go under the ground
controls.mouseButtons = { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.PAN, RIGHT: THREE.MOUSE.PAN };
controls.addEventListener("change", render);
renderer.domElement.addEventListener("contextmenu", (e) => e.preventDefault());

let fly = null;  // smooth transition to a preset view
(function loop() {
  requestAnimationFrame(loop);
  if (fly) {
    const f = Math.min(1, (performance.now() - fly.t0) / fly.ms), k = f < 0.5 ? 2 * f * f : 1 - (-2 * f + 2) ** 2 / 2;
    camera.position.lerpVectors(fly.p0, fly.p1, k);
    controls.target.lerpVectors(fly.q0, fly.q1, k);
    if (f >= 1) fly = null;
  }
  controls.update();  // fires "change" -> render only while something moves
})();

scene.add(new THREE.HemisphereLight(0xffffff, 0x9aa0ad, 1.1));
const sun = new THREE.DirectionalLight(0xffffff, 3.2);
sun.castShadow = true;
sun.shadow.mapSize.set(4096, 4096);
scene.add(sun, sun.target);

const groundMat = new THREE.MeshLambertMaterial({ color: 0xffffff });
const ground = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), groundMat);
ground.receiveShadow = true;
scene.add(ground);

const modelGroup = new THREE.Group(), resultGroup = new THREE.Group(), edgeGroup = new THREE.Group(), sunGroup = new THREE.Group();
scene.add(modelGroup, resultGroup, edgeGroup, sunGroup);
const sunBall = new THREE.Mesh(new THREE.SphereGeometry(1, 24, 16), new THREE.MeshBasicMaterial({ color: 0xffd400 }));
sunGroup.add(sunBall);
let dayLine = null;

function resize() {
  const w = viewer.clientWidth, h = viewer.clientHeight;
  if (!w || !h) return;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  render();
}
new ResizeObserver(resize).observe(viewer);
window.addEventListener("resize", resize);

function render() {
  renderer.render(scene, camera);
  // compass: screen direction of model north
  const c = controls.target.clone(), n = c.clone().add(new THREE.Vector3(...sunVector(0, 0, north())).multiplyScalar(10));
  c.project(camera); n.project(camera);
  const ang = Math.atan2(-(n.y - c.y), n.x - c.x) * 180 / Math.PI + 90;
  $("compass").style.transform = `rotate(${ang}deg)`;
}

function setCamera(kind, animate = true) {
  const R = S.radius, t = S.home.clone();
  const dist = R / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2)) * (camera.aspect < 1 ? 1.25 : 0.82);
  const dir = { top: new THREE.Vector3(0, -0.001, 1), axo: new THREE.Vector3(-0.55, -0.8, 0.62) }[kind]
    || camera.position.clone().sub(controls.target);  // "fit": keep the angle, frame the model
  const p1 = t.clone().add(dir.normalize().multiplyScalar(dist));
  camera.near = R / 500; camera.far = R * 60; camera.updateProjectionMatrix();
  if (!animate) { camera.position.copy(p1); controls.target.copy(t); controls.update(); render(); return; }
  fly = { t0: performance.now(), ms: 450, p0: camera.position.clone(), p1, q0: controls.target.clone(), q1: t };
}

// double click on the model: orbit around that point
renderer.domElement.addEventListener("dblclick", (e) => {
  const r = renderer.domElement.getBoundingClientRect();
  ray.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
  const hit = ray.intersectObjects(modelGroup.children.concat(resultGroup.children, [ground]).filter((m) => m.visible), false)[0];
  if (!hit) return;
  const shift = hit.point.clone().sub(controls.target);
  fly = { t0: performance.now(), ms: 350, p0: camera.position.clone(), p1: camera.position.clone().add(shift),
    q0: controls.target.clone(), q1: hit.point.clone() };
});

// ---------------------------------------------------------------- model
const north = () => Number($("north").value) || 0;
const CONTEXT_RX = /context|entorno|exist|vecin|surround|site|urban/i;
const ANALYSIS_RX = /proyect|project|anal|propuest|edific|building|massing|volumen/i;

async function rhino() {
  if (!S.rh) { const mod = await import(RHINO_URL); S.rh = await mod.default(); }
  return S.rh;
}

async function loadModel(file) {
  if (!file) return;
  busy("Leyendo el modelo", file.name);
  try {
    await nextFrame();
    const rh = await rhino();
    const model = readModel(rh, new Uint8Array(await file.arrayBuffer()));
    if (!model.objects.length) throw new Error("El archivo no tiene volúmenes (mallas, polisuperficies o extrusiones).");
    S.model = model;
    S.radiation = S.sunhours = null;
    S.roles = new Map();
    for (const o of model.objects) {
      S.roles.set(o.id, !o.layerVisible ? "ignore"
      : CONTEXT_RX.test(o.layer) ? "context" : ANALYSIS_RX.test(o.layer) ? "analysis" : "context");
    }
    $("model-name").textContent = file.name;
    const n = model.objects.reduce((a, o) => a + o.tris.length / 9, 0);
    const notes = [];
    if (model.warn.rebuilt) notes.push("algunas caras no tenían malla de render y se han reconstruido");
    if (model.warn.curved) notes.push("hay superficies curvas sin malla (guarda en Rhino con vista sombreada)");
    if (model.warn.failed) notes.push(`${model.warn.failed} objetos no se pudieron leer`);
    $("model-info").textContent = `${model.objects.length} volúmenes · ${n.toLocaleString("es")} triángulos · unidades ${model.units.name}`
      + (notes.length ? ` · ${notes.join(" · ")}` : "");
    buildScene();
    renderLayers();
    clearResults();
    setCamera("axo", false);
    status(S.epw ? "Modelo cargado. Elige los volúmenes a analizar." : "Modelo cargado. Falta el EPW (botón de la barra superior).");
  } catch (e) {
    status(e.message || String(e), true);
  } finally { idle(); }
}

function buildScene() {
  for (const g of [modelGroup, edgeGroup]) { g.children.forEach((m) => m.geometry?.dispose()); g.clear(); }
  S.meshes.clear();
  // re-centre: big georeferenced coordinates lose precision in float32
  const box = new THREE.Box3();
  for (const o of S.model.objects) for (let i = 0; i < o.tris.length; i += 3) box.expandByPoint(new THREE.Vector3(o.tris[i], o.tris[i + 1], o.tris[i + 2]));
  const c = box.getCenter(new THREE.Vector3());
  S.offset = [c.x, c.y, box.min.z];
  for (const o of S.model.objects) {
    if (o.centred) continue;
    for (let i = 0; i < o.tris.length; i += 3) { o.tris[i] -= S.offset[0]; o.tris[i + 1] -= S.offset[1]; o.tris[i + 2] -= S.offset[2]; }
    o.centred = true;
  }
  const size = box.getSize(new THREE.Vector3());
  S.radius = Math.max(10, 0.5 * Math.hypot(size.x, size.y, size.z));
  for (const o of S.model.objects) {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(o.tris, 3));
    g.computeVertexNormals();
    const m = new THREE.Mesh(g, new THREE.MeshLambertMaterial({ color: ROLE_COLOR.context, side: THREE.DoubleSide }));
    m.castShadow = m.receiveShadow = true;
    m.userData.id = o.id;
    modelGroup.add(m);
    const e = new THREE.LineSegments(new THREE.EdgesGeometry(g, 25), new THREE.LineBasicMaterial({ color: 0x5b6273, transparent: true, opacity: 0.55 }));
    e.userData.id = o.id;
    edgeGroup.add(e);
    S.meshes.set(o.id, { mesh: m, edges: e });
  }
  const R = S.radius;
  ground.geometry.dispose();
  ground.geometry = new THREE.PlaneGeometry(R * 12, R * 12);
  ground.position.set(0, 0, -0.02);
  S.home.set(0, 0, size.z * 0.35);
  controls.target.copy(S.home);
  sunBall.scale.setScalar(R * 0.035);
  $("empty").hidden = true;
  applyRoles();
  updateSun();
}

function applyRoles() {
  for (const [id, { mesh, edges }] of S.meshes) {
    const role = S.roles.get(id);
    mesh.visible = edges.visible = role !== "ignore";
    mesh.material.color.setHex(ROLE_COLOR[role] || ROLE_COLOR.context);
  }
  showResults();
  render();
  const nA = [...S.roles.values()].filter((r) => r === "analysis").length;
  $("run").disabled = !(S.epw && nA);
  $("sunhours").disabled = !(S.epw && nA);
}

function setRole(ids, role) {
  ids.forEach((id) => S.roles.set(id, role));
  clearResults();
  applyRoles();
  renderLayers();
}

function renderLayers() {
  const box = $("layers");
  box.innerHTML = "";
  const byLayer = new Map();
  for (const o of S.model.objects) { if (!byLayer.has(o.layer)) byLayer.set(o.layer, []); byLayer.get(o.layer).push(o); }
  const opts = (v) => ["context", "analysis", "ignore"].map((r) => `<option value="${r}"${r === v ? " selected" : ""}>${{ context: "Contexto", analysis: "Analizar", ignore: "Ignorar" }[r]}</option>`).join("");
  const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  for (const [name, objs] of byLayer) {
    const roles = new Set(objs.map((o) => S.roles.get(o.id)));
    const v = roles.size === 1 ? [...roles][0] : "";
    const el = document.createElement("div");
    el.className = "layer";
    const col = objs[0].color;
    el.innerHTML = `<div class="layer-head"><span class="swatch" style="background:rgb(${col.join(",")})"></span>
      <span class="name" title="${esc(name)}">${esc(name)}</span>
      <select autocomplete="off" aria-label="Papel de la capa ${esc(name)}">${v ? "" : '<option value="" selected>Mixto</option>'}${opts(v)}</select></div>
      <details><summary>${objs.length} ${objs.length === 1 ? "objeto" : "objetos"}</summary></details>`;
    el.querySelector("select").addEventListener("change", (ev) => { if (ev.target.value) setRole(objs.map((o) => o.id), ev.target.value); });
    const det = el.querySelector("details");
    objs.forEach((o, i) => {
      const row = document.createElement("div");
      row.className = "obj";
      row.innerHTML = `<span>${esc(o.name || `objeto ${i + 1}`)}</span><select autocomplete="off">${opts(S.roles.get(o.id))}</select>`;
      row.querySelector("select").addEventListener("change", (ev) => setRole([o.id], ev.target.value));
      det.append(row);
    });
    box.append(el);
  }
}

// click on a volume: context <-> analysis
const ray = new THREE.Raycaster(), down = new THREE.Vector2();
renderer.domElement.addEventListener("pointerdown", (e) => down.set(e.clientX, e.clientY));
let clickTimer = null;
renderer.domElement.addEventListener("dblclick", () => { clearTimeout(clickTimer); clickTimer = null; });
renderer.domElement.addEventListener("pointerup", (e) => {
  if (e.button !== 0 || e.shiftKey || !S.model || Math.hypot(e.clientX - down.x, e.clientY - down.y) > 4) return;
  clearTimeout(clickTimer);
  clickTimer = setTimeout(() => toggleAt(e), 260);  // wait: a double click centres the view instead
});
function toggleAt(e) {
  const r = renderer.domElement.getBoundingClientRect();
  ray.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
  const targets = modelGroup.children.filter((m) => m.visible).concat(resultGroup.children.filter((m) => m.visible));
  const hit = ray.intersectObjects(targets, false)[0];
  if (!hit) return;
  const id = hit.object.userData.id;
  setRole([id], S.roles.get(id) === "analysis" ? "context" : "analysis");
}

// ---------------------------------------------------------------- sun / shadows
function fillDays() {
  $("day").innerHTML = KEY_DAYS.map((d, i) => `<option value="${i}"${d.key === "jun" ? " selected" : ""}>${d.label}</option>`).join("");
}
const day = () => KEY_DAYS[Number($("day").value)];
const fmtHour = (h) => `${String(Math.floor(h)).padStart(2, "0")}:${String(Math.round((h % 1) * 60)).padStart(2, "0")}`;

function daySpan() {
  if (!S.epw) return [6, 20];
  const suns = daySuns(S.epw, day().month, day().day, north(), 0.25);
  if (!suns.length) return [12, 12];
  return [Math.ceil(suns[0].t * 4) / 4, Math.floor(suns[suns.length - 1].t * 4) / 4];
}

function updateDayLimits() {
  const [a, b] = daySpan(), h = $("hour");
  h.min = a; h.max = b;
  if (+h.value < a || +h.value > b) h.value = Math.min(b, Math.max(a, 12));
}

function updateDayLine() {
  if (dayLine) { sunGroup.remove(dayLine); dayLine.geometry.dispose(); dayLine = null; }
  if (!S.epw || !S.model) return;
  const R = S.radius * 2.2, pts = daySuns(S.epw, day().month, day().day, north(), 0.1)
    .map((s) => new THREE.Vector3(...s.v).multiplyScalar(R));
  if (pts.length < 2) return;
  dayLine = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),
    new THREE.LineDashedMaterial({ color: 0xef9c15, dashSize: R * 0.03, gapSize: R * 0.02 }));
  dayLine.computeLineDistances();
  sunGroup.add(dayLine);
}

function updateSun() {
  const h = Number($("hour").value);
  $("hour-value").textContent = fmtHour(h);
  if (!S.epw) { sun.intensity = 1.2; sun.position.set(-1, -2, 3).multiplyScalar(S.radius); sunBall.visible = false;
    $("sun-pill").textContent = "Sin EPW"; render(); return; }
  const d = day(), p = solarPosition(d.month, d.day, h, S.epw.lat, S.epw.lon, S.epw.tz);
  const v = new THREE.Vector3(...sunVector(p.azimuth, p.elevation, north()));
  const R = S.radius;
  const up = p.elevation > 0;
  sun.intensity = up ? 3.2 : 0;
  sun.position.copy(v).multiplyScalar(R * 3);
  sun.target.position.set(0, 0, 0);
  const cam = sun.shadow.camera;
  cam.left = cam.bottom = -R * 2.2; cam.right = cam.top = R * 2.2; cam.near = R * 0.1; cam.far = R * 7;
  cam.updateProjectionMatrix();
  sun.shadow.bias = -0.0004; sun.shadow.normalBias = R * 0.0015;
  sunBall.visible = up && !!S.model;
  sunBall.position.copy(v).multiplyScalar(R * 2.2);
  $("sun-pill").textContent = up
    ? `${d.label.split(" ·")[0]} · ${fmtHour(h)} · az ${p.azimuth.toFixed(0)}° · alt ${p.elevation.toFixed(0)}°`
    : `${d.label.split(" ·")[0]} · ${fmtHour(h)} · sol bajo el horizonte`;
  render();
}

function play() {
  if (S.playing) { S.playing = false; $("play").textContent = "▶ Recorrido del día"; return; }
  setMode("shadow");
  S.playing = true;
  $("play").textContent = "■ Parar";
  const h = $("hour"), a = +h.min, b = +h.max, t0 = performance.now(), dur = 8000;
  const step = (t) => {
    if (!S.playing) return;
    const f = (t - t0) / dur;
    h.value = a + (b - a) * Math.min(1, f);
    updateSun();
    if (f < 1) requestAnimationFrame(step); else play();
  };
  requestAnimationFrame(step);
}

// ---------------------------------------------------------------- analysis grid
function analysisGrid(maxEdge) {
  const pts = [], nrm = [], area = [], owner = [], tris = [];
  const lim = maxEdge * Math.SQRT2;
  for (const o of S.model.objects) {
    if (S.roles.get(o.id) !== "analysis") continue;
    const T = o.tris;
    for (let i = 0; i < T.length; i += 9) {
      const stack = [[T[i], T[i + 1], T[i + 2], T[i + 3], T[i + 4], T[i + 5], T[i + 6], T[i + 7], T[i + 8]]];
      while (stack.length) {
        const t = stack.pop();
        const l0 = Math.hypot(t[3] - t[0], t[4] - t[1], t[5] - t[2]);
        const l1 = Math.hypot(t[6] - t[3], t[7] - t[4], t[8] - t[5]);
        const l2 = Math.hypot(t[0] - t[6], t[1] - t[7], t[2] - t[8]);
        const L = Math.max(l0, l1, l2);
        if (L > lim) {
          // split the longest edge
          const [a, b, c] = l0 === L ? [0, 3, 6] : l1 === L ? [3, 6, 0] : [6, 0, 3];
          const m = [(t[a] + t[b]) / 2, (t[a + 1] + t[b + 1]) / 2, (t[a + 2] + t[b + 2]) / 2];
          const A = t.slice(a, a + 3), B = t.slice(b, b + 3), C = t.slice(c, c + 3);
          stack.push([...A, ...m, ...C], [...m, ...B, ...C]);
          if (pts.length / 3 + stack.length > MAX_POINTS) throw new Error(`Demasiados puntos (> ${MAX_POINTS.toLocaleString("es")}). Aumenta el tamaño de malla.`);
          continue;
        }
        const ux = t[3] - t[0], uy = t[4] - t[1], uz = t[5] - t[2], vx = t[6] - t[0], vy = t[7] - t[1], vz = t[8] - t[2];
        const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx, len = Math.hypot(nx, ny, nz);
        if (len < 1e-9) continue;
        // faces resting on the ground (downward, at the lowest level) are not exposed
        if (nz / len < -0.9 && Math.max(t[2], t[5], t[8]) < 0.05) continue;
        const off = 0.02;
        pts.push((t[0] + t[3] + t[6]) / 3 + nx / len * off, (t[1] + t[4] + t[7]) / 3 + ny / len * off, (t[2] + t[5] + t[8]) / 3 + nz / len * off);
        nrm.push(nx / len, ny / len, nz / len);
        area.push(len / 2);
        owner.push(o.id);
        tris.push(...t);
      }
    }
  }
  return { pts: new Float32Array(pts), nrm: new Float32Array(nrm), area: new Float32Array(area), owner, tris: new Float32Array(tris) };
}

function sceneTris() {
  const parts = S.model.objects.filter((o) => S.roles.get(o.id) !== "ignore").map((o) => o.tris);
  const out = new Float32Array(parts.reduce((a, p) => a + p.length, 0));
  let k = 0;
  for (const p of parts) { out.set(p, k); k += p.length; }
  return out;
}

// ---------------------------------------------------------------- workers
const NW = Math.max(1, Math.min(6, (navigator.hardwareConcurrency || 4) - 1));
let pool = null, poolKey = null;

async function workers() {
  const key = [...S.roles.entries()].map(([k, v]) => k + v).join("|");
  if (pool && poolKey === key) return pool;
  pool?.forEach((w) => w.terminate());
  const tris = sceneTris();
  pool = Array.from({ length: NW }, () => new Worker(new URL("./worker.js", import.meta.url), { type: "module" }));
  await Promise.all(pool.map((w) => new Promise((res, rej) => {
    w.onmessage = (e) => (e.data.type === "scene-ok" ? res() : rej(new Error(e.data.message)));
    w.onerror = (e) => rej(new Error(e.message || "Error en el worker"));
    w.postMessage({ type: "scene", tris });
  })));
  poolKey = key;
  return pool;
}

// split points across the workers; job(slice) -> message; returns the per-worker results in order
async function runJob(grid, makeMsg) {
  const ws = await workers(), n = grid.pts.length / 3, chunk = Math.ceil(n / ws.length), done = new Array(ws.length).fill(0);
  return Promise.all(ws.map((w, i) => new Promise((res, rej) => {
    const a = i * chunk, b = Math.min(n, a + chunk);
    if (a >= b) return res(null);
    w.onmessage = (e) => {
      const m = e.data;
      if (m.type === "progress") { done[i] = m.done; progress(done.reduce((x, y) => x + y, 0) / n); }
      else if (m.type === "error") rej(new Error(m.message));
      else res(m.res);
    };
    w.postMessage(makeMsg(grid.pts.slice(3 * a, 3 * b), grid.nrm.slice(3 * a, 3 * b)));
  })));
}

function joinChunks(parts, n) {
  const out = new Float32Array(n);
  let k = 0;
  for (const p of parts) if (p) { out.set(p, k); k += p.length; }
  return out;
}

async function runRadiation() {
  if (!S.model || !S.epw) return;
  busy("Radiación acumulada", "Preparando la malla de análisis…");
  try {
    await nextFrame();
    const grid = analysisGrid(Math.max(0.25, Number($("grid").value) || 1));
    const n = grid.pts.length / 3;
    if (!n) throw new Error("No hay volúmenes marcados como «Analizar».");
    const sky = skyMatrices(S.epw, north(), Math.min(1, Math.max(0, Number($("albedo").value) || 0)));
    $("busy-text").textContent = `${n.toLocaleString("es")} puntos × ${sky.dirs.length / 3} direcciones de cielo · ${NW} hilos`;
    const t0 = performance.now();
    const parts = await runJob(grid, (pts, nrm) => ({ type: "radiation", pts, nrm, dirs: sky.dirs, energies: sky.energies }));
    const res = {};
    for (const k of Object.keys(PERIOD)) res[k] = joinChunks(parts.map((p) => p && p[k]), n);
    S.radiation = { grid, res, seasons: sky.seasons };
    const mn = (ms) => ms.map((m) => ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"][m - 1]).join("–");
    $("season-info").textContent = `Verano: ${mn([sky.seasons.summer[0], sky.seasons.summer[2]])} · Invierno: ${mn([sky.seasons.winter[0], sky.seasons.winter[2]])}. `
      + `${n.toLocaleString("es")} puntos en ${((performance.now() - t0) / 1000).toFixed(1)} s.`;
    $("mode").querySelector('[data-m="radiation"]').disabled = false;
    setMode("radiation");
    status("Radiación calculada.");
  } catch (e) { status(e.message || String(e), true); } finally { idle(); }
}

async function runSunHours() {
  if (!S.model || !S.epw) return;
  const d = day();
  busy("Horas de sol directo", d.label);
  try {
    await nextFrame();
    const grid = analysisGrid(Math.max(0.25, Number($("grid").value) || 1));
    const n = grid.pts.length / 3;
    if (!n) throw new Error("No hay volúmenes marcados como «Analizar».");
    const step = 1 / 6, suns = daySuns(S.epw, d.month, d.day, north(), step).map((s) => s.v);
    const parts = await runJob(grid, (pts, nrm) => ({ type: "sunhours", pts, nrm, suns, step }));
    S.sunhours = { grid, res: joinChunks(parts, n), day: d, max: suns.length * step };
    $("mode").querySelector('[data-m="sunhours"]').disabled = false;
    setMode("sunhours");
    status(`Horas de sol del ${d.label.split(" ·")[0]} calculadas.`);
  } catch (e) { status(e.message || String(e), true); } finally { idle(); }
}

function clearResults() {
  S.radiation = null; S.sunhours = null;
  $("mode").querySelector('[data-m="radiation"]').disabled = true;
  $("mode").querySelector('[data-m="sunhours"]').disabled = true;
  if (S.mode !== "shadow") setMode("shadow"); else showResults();
}

// ---------------------------------------------------------------- colours / legend
const PAL = PALETTE.map((c) => new THREE.Color(c));
function colorAt(f, out) {
  f = Math.min(1, Math.max(0, f)) * (PAL.length - 1);
  const i = Math.min(PAL.length - 2, Math.floor(f));
  return out.copy(PAL[i]).lerp(PAL[i + 1], f - i);
}

function niceRange(vals) {
  let lo = Infinity, hi = -Infinity;
  for (const v of vals) { if (v < lo) lo = v; if (v > hi) hi = v; }
  if (!Number.isFinite(lo)) return [0, 1];
  return [lo, hi > lo ? hi : lo + 1];
}

function current() {
  if (S.mode === "radiation" && S.radiation) {
    return { grid: S.radiation.grid, vals: S.radiation.res[S.period], unit: "kWh/m²",
      title: `Radiación acumulada · ${PERIOD[S.period]}`, digits: 0 };
  }
  if (S.mode === "sunhours" && S.sunhours) {
    return { grid: S.sunhours.grid, vals: S.sunhours.res, unit: "h", fixed: [0, Math.ceil(S.sunhours.max)],
      title: `Horas de sol directo · ${S.sunhours.day.label.split(" ·")[0]}`, digits: 1 };
  }
  return null;
}

function showResults() {
  resultGroup.children.forEach((m) => m.geometry.dispose());
  resultGroup.clear();
  const cur = current();
  const hideAnalysed = !!cur;
  for (const [id, { mesh }] of S.meshes) if (S.roles.get(id) === "analysis") mesh.visible = !hideAnalysed;
  $("legend").hidden = !cur;
  $("summary-card").hidden = !cur;
  ground.visible = !cur || S.mode === "sunhours";
  sun.castShadow = !cur;
  sunGroup.visible = !cur || S.mode === "sunhours";
  $("view-title").textContent = cur ? cur.title : "Sombras";
  if (!cur) { render(); return; }
  const auto = cur.fixed || niceRange(cur.vals);
  const lo = $("lmin").value !== "" ? Number($("lmin").value) : auto[0];
  const hi = $("lmax").value !== "" ? Number($("lmax").value) : auto[1];
  const { grid, vals } = cur, n = vals.length;
  const col = new Float32Array(9 * n), c = new THREE.Color();
  for (let i = 0; i < n; i++) { colorAt((vals[i] - lo) / (hi - lo || 1), c); for (let k = 0; k < 3; k++) col.set([c.r, c.g, c.b], 9 * i + 3 * k); }
  // one mesh per analysed object, so a click still knows which volume it is
  const byOwner = new Map();
  grid.owner.forEach((id, i) => { if (!byOwner.has(id)) byOwner.set(id, []); byOwner.get(id).push(i); });
  for (const [id, idx] of byOwner) {
    const P = new Float32Array(9 * idx.length), C = new Float32Array(9 * idx.length);
    idx.forEach((i, k) => { P.set(grid.tris.subarray(9 * i, 9 * i + 9), 9 * k); C.set(col.subarray(9 * i, 9 * i + 9), 9 * k); });
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(P, 3));
    g.setAttribute("color", new THREE.BufferAttribute(C, 3));
    const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide }));
    m.userData.id = id;
    resultGroup.add(m);
  }
  drawLegend(cur, lo, hi);
  drawSummary(cur);
  render();
}

function drawLegend(cur, lo, hi) {
  const fmt = (v) => v.toLocaleString("es", { maximumFractionDigits: cur.digits });
  const steps = 10, cells = [], c = new THREE.Color();
  for (let i = 0; i < steps; i++) cells.push(`<span style="background:#${colorAt((i + 0.5) / steps, c).getHexString()}"></span>`);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => `<span>${fmt(lo + (hi - lo) * f)}</span>`).join("");
  $("legend").innerHTML = `<div class="t">${cur.title} (${cur.unit})</div><div class="bar">${cells.join("")}</div><div class="ticks">${ticks}</div>`;
}

function drawSummary(cur) {
  const grid = cur.grid, rows = new Map();
  grid.owner.forEach((id, i) => {
    if (!rows.has(id)) rows.set(id, { a: 0, s: 0, mx: -Infinity, mn: Infinity, extra: {} });
    const r = rows.get(id), v = cur.vals[i], A = grid.area[i];
    r.a += A; r.s += v * A; r.mx = Math.max(r.mx, v); r.mn = Math.min(r.mn, v);
    if (S.mode === "radiation") {
      for (const k of Object.keys(PERIOD)) r.extra[k] = (r.extra[k] || 0) + S.radiation.res[k][i] * A;
      r.mxA = Math.max(r.mxA ?? -Infinity, S.radiation.res.annual[i]);
    }
  });
  const name = (id) => { const o = S.model.objects.find((x) => x.id === id); return o.name || o.layer; };
  const f0 = (v) => v.toLocaleString("es", { maximumFractionDigits: 0 }), f1 = (v) => v.toLocaleString("es", { maximumFractionDigits: 1 });
  let html;
  if (S.mode === "radiation") {
    html = "<tr><th>Volumen</th><th>Superficie m²</th><th>Anual kWh/m²</th><th>Verano kWh/m²</th><th>Invierno kWh/m²</th><th>Máx. anual</th><th>Total anual MWh</th></tr>";
    for (const [id, r] of rows) html += `<tr><td>${name(id)}</td><td>${f0(r.a)}</td><td>${f0(r.extra.annual / r.a)}</td><td>${f0(r.extra.summer / r.a)}</td>`
      + `<td>${f0(r.extra.winter / r.a)}</td><td>${f0(r.mxA)}</td><td>${f1(r.extra.annual / 1000)}</td></tr>`;
    $("summary-title").textContent = "Radiación acumulada";
  } else {
    html = "<tr><th>Volumen</th><th>Superficie m²</th><th>Media h</th><th>Mín. h</th><th>Máx. h</th></tr>";
    for (const [id, r] of rows) html += `<tr><td>${name(id)}</td><td>${f0(r.a)}</td><td>${f1(r.s / r.a)}</td><td>${f1(r.mn)}</td><td>${f1(r.mx)}</td></tr>`;
    $("summary-title").textContent = cur.title;
  }
  $("summary").innerHTML = html;
}

function setMode(m) {
  S.mode = m;
  if (m !== "shadow" && S.playing) play();
  $("mode").querySelectorAll("button").forEach((b) => b.classList.toggle("is-on", b.dataset.m === m));
  showResults();
}

// ---------------------------------------------------------------- exports
function download(name, blob) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
const base = () => ($("model-name").textContent || "modelo").replace(/\.3dm$/i, "");

function pngView() {
  render();
  const tag = { shadow: `sombras-${day().key}-${fmtHour(Number($("hour").value)).replace(":", "")}`,
    sunhours: `horas-sol-${S.sunhours?.day.key}`, radiation: `radiacion-${PERIOD[S.period].toLowerCase()}` }[S.mode];
  renderer.domElement.toBlob((b) => download(`${base()}-${tag}.png`, b));
}

async function png4() {
  const prevMode = S.mode, prevDay = $("day").value, prevHour = $("hour").value;
  if (prevMode !== "shadow") setMode("shadow");
  const W = renderer.domElement.width, H = renderer.domElement.height;
  const cv = Object.assign(document.createElement("canvas"), { width: 2 * W, height: 2 * H });
  const ctx = cv.getContext("2d");
  const hour = Number(prevHour);
  KEY_DAYS.forEach((d, i) => {
    $("day").value = i;
    updateDayLimits();
    $("hour").value = hour;
    updateDayLine();
    updateSun();
    ctx.drawImage(renderer.domElement, (i % 2) * W, Math.floor(i / 2) * H);
    ctx.font = `600 ${Math.round(H / 26)}px system-ui, sans-serif`;
    ctx.fillStyle = "#1d2433";
    ctx.fillText(`${d.label} · ${fmtHour(hour)}`, (i % 2) * W + H / 30, Math.floor(i / 2) * H + H / 16);
  });
  ctx.strokeStyle = "#dfe3eb"; ctx.lineWidth = 2;
  ctx.strokeRect(W, 0, 0, 2 * H); ctx.beginPath(); ctx.moveTo(W, 0); ctx.lineTo(W, 2 * H); ctx.moveTo(0, H); ctx.lineTo(2 * W, H); ctx.stroke();
  $("day").value = prevDay; updateDayLimits(); $("hour").value = prevHour; updateDayLine(); updateSun();
  if (prevMode !== "shadow") setMode(prevMode);
  cv.toBlob((b) => download(`${base()}-sombras-4-dias-${fmtHour(hour).replace(":", "")}.png`, b));
}

function csv() {
  const g = (S.radiation || S.sunhours)?.grid;
  if (!g) { status("Calcula primero la radiación o las horas de sol.", true); return; }
  const name = new Map(S.model.objects.map((o) => [o.id, o.name || o.layer]));
  const head = ["objeto", "x", "y", "z", "nx", "ny", "nz", "area_m2"];
  const sameGrid = S.radiation && S.sunhours && S.radiation.grid.pts.length === S.sunhours.grid.pts.length;
  if (S.radiation) head.push("anual_kWh_m2", "verano_kWh_m2", "invierno_kWh_m2");
  if (S.sunhours && (!S.radiation || sameGrid)) head.push(`horas_sol_${S.sunhours.day.key}`);
  const lines = [head.join(";")];
  const n = g.pts.length / 3, o = S.offset, f = (v, d = 3) => v.toFixed(d).replace(".", ",");
  for (let i = 0; i < n; i++) {
    const row = [name.get(g.owner[i]), f(g.pts[3 * i] + o[0]), f(g.pts[3 * i + 1] + o[1]), f(g.pts[3 * i + 2] + o[2]),
      f(g.nrm[3 * i]), f(g.nrm[3 * i + 1]), f(g.nrm[3 * i + 2]), f(g.area[i])];
    if (S.radiation) row.push(f(S.radiation.res.annual[i], 1), f(S.radiation.res.summer[i], 1), f(S.radiation.res.winter[i], 1));
    if (S.sunhours && (!S.radiation || sameGrid)) row.push(f(S.sunhours.res[i], 2));
    lines.push(row.join(";"));
  }
  download(`${base()}-resultados.csv`, new Blob(["﻿" + lines.join("\n")], { type: "text/csv;charset=utf-8" }));
}

// ---------------------------------------------------------------- EPW
function setEpw(text, name) {
  try {
    S.epw = parseEpw(text);
    $("epw-name").textContent = name || S.epw.city;
    S.radiation = null;
    clearResults();
    updateDayLimits(); updateDayLine(); updateSun();
    applyRoles();
    status(S.model ? `EPW de ${S.epw.city} cargado.` : `EPW de ${S.epw.city} cargado. Carga ahora un .3dm.`);
  } catch (e) { status(e.message, true); }
}

window.addEventListener("message", async (ev) => {
  if (ev.origin !== window.location.origin || ev.data?.type !== "load-epw") return;
  try { const r = await fetch(ev.data.url); setEpw(await r.text(), ev.data.name); } catch (e) { status(`No se pudo leer el EPW: ${e.message}`, true); }
});

// ---------------------------------------------------------------- wiring
if (new URLSearchParams(location.search).get("embed") === "1") document.body.classList.add("is-embedded");
fillDays();
$("epw-file").addEventListener("change", async (e) => { const f = e.target.files[0]; if (f) setEpw(await f.text(), f.name); });
$("model-file").addEventListener("change", (e) => loadModel(e.target.files[0]));
for (const el of [$("model-drop"), viewer]) {
  el.addEventListener("dragover", (e) => { e.preventDefault(); el.classList.add("is-dragging"); });
  el.addEventListener("dragleave", () => el.classList.remove("is-dragging"));
  el.addEventListener("drop", (e) => { e.preventDefault(); el.classList.remove("is-dragging"); loadModel(e.dataTransfer.files[0]); });
}
$("sample").addEventListener("click", async () => {
  const r = await fetch(new URL("./ejemplo.3dm", import.meta.url));
  loadModel(new File([await r.blob()], "ejemplo.3dm"));
});
$("north").addEventListener("change", () => { clearResults(); updateDayLimits(); updateDayLine(); updateSun(); });
$("day").addEventListener("change", () => { updateDayLimits(); updateDayLine(); updateSun(); });
$("hour").addEventListener("input", () => { if (S.mode === "radiation") setMode("shadow"); updateSun(); });
$("play").addEventListener("click", play);
$("run").addEventListener("click", runRadiation);
$("sunhours").addEventListener("click", runSunHours);
$("grid").addEventListener("change", clearResults);
$("albedo").addEventListener("change", () => { if (S.radiation) clearResults(); });
for (const id of ["lmin", "lmax"]) $(id).addEventListener("input", showResults);
$("period").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b) return;
  S.period = b.dataset.p;
  $("period").querySelectorAll("button").forEach((x) => x.classList.toggle("is-on", x === b));
  if (S.radiation) setMode("radiation");
});
$("mode").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b && !b.disabled) setMode(b.dataset.m); });
$("cams").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) setCamera(b.dataset.c); });
$("png").addEventListener("click", pngView);
$("png4").addEventListener("click", png4);
$("csv").addEventListener("click", csv);
const enableExports = () => { const on = !!S.model; $("png").disabled = !on; $("png4").disabled = !(on && S.epw); $("csv").disabled = !on; };
new MutationObserver(enableExports).observe($("status"), { childList: true });
updateDayLimits(); updateSun(); resize();
