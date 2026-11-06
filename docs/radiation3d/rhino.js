// Rhino .3dm -> triangle soups (metres, Z up), one entry per object.
// rhino3dm.js cannot mesh NURBS by itself, so Breps / extrusions use the render meshes Rhino stores
// in the file. When a face has none (file saved with "Save small", or made by a script), planar faces
// are rebuilt from their edges and untrimmed curved faces are sampled on a grid.
import { ShapeUtils, Vector2 } from "three";

const UNIT_M = { 0: 1, 1: 1e-6, 2: 1e-3, 3: 1e-2, 4: 1, 5: 1e3, 6: 2.54e-8, 7: 2.54e-5, 8: 0.0254, 9: 0.3048,
  10: 1609.344, 12: 1e-10, 13: 1e-9, 14: 1e-1, 15: 10, 16: 100, 17: 1e6, 18: 1e9, 19: 0.9144 };
const UNIT_NAME = { 2: "mm", 3: "cm", 4: "m", 5: "km", 8: "in", 9: "ft", 19: "yd" };

export function unitsOf(doc) {
  const u = doc.settings().modelUnitSystem;
  const v = typeof u === "number" ? u : (u?.value ?? 4);
  return { scale: UNIT_M[v] ?? 1, name: UNIT_NAME[v] ?? "m" };
}

// ---------- meshes
function pushMesh(out, mesh, xf) {
  const vs = mesh.vertices(), fs = mesh.faces();
  const n = vs.count, P = new Float64Array(n * 3);
  for (let i = 0; i < n; i++) { const p = vs.get(i); P[3 * i] = p[0]; P[3 * i + 1] = p[1]; P[3 * i + 2] = p[2]; }
  const v = (i) => [P[3 * i], P[3 * i + 1], P[3 * i + 2]];
  for (let i = 0, m = fs.count; i < m; i++) {
    const f = fs.get(i);
    tri(out, v(f[0]), v(f[1]), v(f[2]), xf);
    if (f[2] !== f[3]) tri(out, v(f[0]), v(f[2]), v(f[3]), xf);
  }
}

function tri(out, a, b, c, xf) {
  if (xf) { a = xf(a); b = xf(b); c = xf(c); }
  out.push(a[0], a[1], a[2], b[0], b[1], b[2], c[0], c[1], c[2]);
}

// ---------- Brep faces without a render mesh
function sampleCurve(rh, edge) {
  const nc = edge.toNurbsCurve ? edge.toNurbsCurve() : edge;
  if (nc.degree === 1) {
    const cp = nc.points(), pts = [];
    for (let i = 0; i < cp.count; i++) { const p = cp.get(i); const w = p[3] || 1; pts.push([p[0] / w, p[1] / w, p[2] / w]); }
    return pts;
  }
  const [t0, t1] = nc.domain, pts = [], N = 24;
  for (let i = 0; i <= N; i++) pts.push(nc.pointAt(t0 + (t1 - t0) * i / N));
  return pts;
}

const near = (a, b, tol) => Math.abs(a[0] - b[0]) < tol && Math.abs(a[1] - b[1]) < tol && Math.abs(a[2] - b[2]) < tol;

function chainLoops(segs, tol) {
  const loops = [], left = segs.slice();
  while (left.length) {
    let loop = left.shift().slice();
    let grown = true;
    while (grown && !near(loop[0], loop[loop.length - 1], tol)) {
      grown = false;
      const end = loop[loop.length - 1];
      for (let i = 0; i < left.length; i++) {
        const s = left[i];
        if (near(s[0], end, tol)) { loop = loop.concat(s.slice(1)); left.splice(i, 1); grown = true; break; }
        if (near(s[s.length - 1], end, tol)) { loop = loop.concat(s.slice(0, -1).reverse()); left.splice(i, 1); grown = true; break; }
      }
    }
    if (near(loop[0], loop[loop.length - 1], tol)) loop.pop();
    if (loop.length >= 3) loops.push(loop);
  }
  return loops;
}

function planarFace(rh, face, out, xf, tol) {
  const srf = face.underlyingSurface();
  const [u0, u1] = srf.domain(0), [v0, v1] = srf.domain(1);
  const frame = srf.frameAt((u0 + u1) / 2, (v0 + v1) / 2);  // [ok, plane]
  const pl = Array.isArray(frame) ? frame[1] : frame;
  const O = pl.origin, X = pl.xAxis, Y = pl.yAxis;
  let N = pl.zAxis;
  if (face.orientationIsReversed) N = [-N[0], -N[1], -N[2]];
  const single = face.duplicateFace(false), edges = single.edges(), segs = [];
  for (let i = 0; i < edges.count; i++) segs.push(sampleCurve(rh, edges.get(i)));
  const loops = chainLoops(segs, tol);
  if (!loops.length) return false;
  const to2 = (p) => { const d = [p[0] - O[0], p[1] - O[1], p[2] - O[2]];
    return new Vector2(d[0] * X[0] + d[1] * X[1] + d[2] * X[2], d[0] * Y[0] + d[1] * Y[1] + d[2] * Y[2]); };
  const rings = loops.map((l) => ({ pts3: l, pts2: l.map(to2) }));
  rings.forEach((r) => { r.area = Math.abs(ShapeUtils.area(r.pts2)); });
  rings.sort((a, b) => b.area - a.area);
  const outer = rings[0], holes = rings.slice(1);
  const all3 = outer.pts3.concat(...holes.map((h) => h.pts3));
  const faces = ShapeUtils.triangulateShape(outer.pts2, holes.map((h) => h.pts2));
  for (const [i, j, k] of faces) {
    let a = all3[i], b = all3[j], c = all3[k];
    const n = cross(sub(b, a), sub(c, a));
    if (n[0] * N[0] + n[1] * N[1] + n[2] * N[2] < 0) [b, c] = [c, b];
    tri(out, a, b, c, xf);
  }
  return true;
}

function sampledFace(face, out, xf) {
  const srf = face.underlyingSurface();
  const [u0, u1] = srf.domain(0), [v0, v1] = srf.domain(1), n = 16;
  const P = [];
  for (let i = 0; i <= n; i++) for (let j = 0; j <= n; j++) P.push(srf.pointAt(u0 + (u1 - u0) * i / n, v0 + (v1 - v0) * j / n));
  const at = (i, j) => P[i * (n + 1) + j];
  const rev = face.orientationIsReversed;
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
    const a = at(i, j), b = at(i + 1, j), c = at(i + 1, j + 1), d = at(i, j + 1);
    if (rev) { tri(out, a, c, b, xf); tri(out, a, d, c, xf); } else { tri(out, a, b, c, xf); tri(out, a, c, d, xf); }
  }
}

function pushBrep(rh, brep, out, xf, tol, warn) {
  const faces = brep.faces();
  for (let i = 0; i < faces.count; i++) {
    const face = faces.get(i);
    const m = face.getMesh(rh.MeshType.Any) || face.getMesh(rh.MeshType.Render);
    if (m && m.faces().count) { pushMesh(out, m, xf); continue; }
    const srf = face.underlyingSurface();
    let ok = false;
    if (srf.isPlanar(tol)) { try { ok = planarFace(rh, face, out, xf, tol); } catch (e) { ok = false; } }
    if (!ok) { sampledFace(face, out, xf); warn.curved = true; }
    warn.rebuilt = true;
  }
}

function pushGeometry(rh, g, out, xf, tol, warn, doc, depth) {
  if (!g) return;
  const t = g.objectType?.value ?? g.objectType;
  const OT = rh.ObjectType;
  const is = (name) => OT && OT[name] && (t === OT[name] || t === OT[name].value);
  if (g instanceof rh.Mesh || is("Mesh")) return pushMesh(out, g, xf);
  if (g instanceof rh.Extrusion || is("Extrusion")) {
    const m = g.getMesh(rh.MeshType.Any);
    if (m && m.faces().count) return pushMesh(out, m, xf);
    return pushBrep(rh, g.toBrep(true), out, xf, tol, warn);
  }
  if (g instanceof rh.Brep || is("Brep")) return pushBrep(rh, g, out, xf, tol, warn);
  if (rh.SubD && (g instanceof rh.SubD || is("SubD"))) {
    const m = rh.Mesh.createFromSubDControlNet(g);
    if (m) { pushMesh(out, m, xf); warn.subd = true; }
    return;
  }
  if (g instanceof rh.Surface || is("Surface")) return pushBrep(rh, rh.Brep.createFromSurface(g), out, xf, tol, warn);
  if (rh.InstanceReference && (g instanceof rh.InstanceReference || is("InstanceReference")) && depth < 4) {
    const def = doc.instanceDefinitions().findId(g.parentIdefId);
    if (!def) return;
    const M = g.xform.toFloatArray(true);  // row major 4x4
    const local = (p) => [M[0] * p[0] + M[1] * p[1] + M[2] * p[2] + M[3],
      M[4] * p[0] + M[5] * p[1] + M[6] * p[2] + M[7], M[8] * p[0] + M[9] * p[1] + M[10] * p[2] + M[11]];
    const chain = xf ? (p) => xf(local(p)) : local;
    for (const id of def.getObjectIds()) {
      const o = doc.objects().findId(id);
      if (o) pushGeometry(rh, o.geometry(), out, chain, tol, warn, doc, depth + 1);
    }
  }
}

const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];

function isClosed(T) {
  const key = (i) => `${Math.round(T[i] * 1e3)},${Math.round(T[i + 1] * 1e3)},${Math.round(T[i + 2] * 1e3)}`;
  const edges = new Map();
  for (let i = 0; i < T.length; i += 9) {
    const k = [key(i), key(i + 3), key(i + 6)];
    for (let e = 0; e < 3; e++) {
      const a = k[e], b = k[(e + 1) % 3], id = a < b ? a + "|" + b : b + "|" + a;
      edges.set(id, (edges.get(id) || 0) + 1);
    }
  }
  for (const n of edges.values()) if (n !== 2) return false;
  return edges.size > 0;
}

// Closed objects: make the triangles face outwards (signed volume > 0). Open surfaces keep their normals.
function orientOutwards(T) {
  if (!isClosed(T)) return 0;
  let vol = 0;
  for (let i = 0; i < T.length; i += 9) {
    vol += T[i] * (T[i + 4] * T[i + 8] - T[i + 5] * T[i + 7]) - T[i + 1] * (T[i + 3] * T[i + 8] - T[i + 5] * T[i + 6])
      + T[i + 2] * (T[i + 3] * T[i + 7] - T[i + 4] * T[i + 6]);
  }
  if (vol < 0) for (let i = 0; i < T.length; i += 9) for (let k = 0; k < 3; k++) {
    const t = T[i + 3 + k]; T[i + 3 + k] = T[i + 6 + k]; T[i + 6 + k] = t;
  }
  return vol / 6;
}

function layerInfo(doc) {
  const L = doc.layers(), out = [];
  for (let i = 0; i < L.count; i++) {
    const l = L.get(i);
    const c = l.color;
    out.push({ index: l.index ?? i, name: l.fullPath || l.name, visible: l.visible !== false,
      color: c ? [c.r, c.g, c.b] : [200, 200, 200] });
  }
  return out;
}

export function readModel(rh, bytes) {
  const doc = rh.File3dm.fromByteArray(bytes);
  if (!doc) throw new Error("No se pudo leer el archivo .3dm");
  const units = unitsOf(doc);
  const tol = (doc.settings().modelAbsoluteTolerance || 0.001) * 10;
  const layers = layerInfo(doc);
  const byIndex = new Map(layers.map((l) => [l.index, l]));
  const objs = doc.objects(), objects = [], warn = {};
  for (let i = 0; i < objs.count; i++) {
    const o = objs.get(i), a = o.attributes();
    if (a.isInstanceDefinitionObject) continue;
    const out = [];
    try { pushGeometry(rh, o.geometry(), out, null, tol, warn, doc, 0); } catch (e) { warn.failed = (warn.failed || 0) + 1; continue; }
    if (!out.length) continue;
    const T = new Float32Array(out.length);
    for (let k = 0; k < out.length; k++) T[k] = out[k] * units.scale;
    const volume = orientOutwards(T);
    const layer = byIndex.get(a.layerIndex) || { name: "—", visible: true, color: [200, 200, 200] };
    objects.push({ id: a.id, name: a.name || "", layer: layer.name, layerIndex: a.layerIndex,
      layerVisible: layer.visible && a.visible !== false, color: layer.color, tris: T, volume });
  }
  return { units, objects, layers, warn };
}
