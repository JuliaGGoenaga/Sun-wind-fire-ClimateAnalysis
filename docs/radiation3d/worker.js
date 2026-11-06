// Ray casting off the main thread: cumulative radiation (sky patches) and direct sun hours (one day).
import { buildBVH, occluded } from "./bvh.js";

let bvh = null;
const stack = new Int32Array(256);

self.onmessage = (ev) => {
  const m = ev.data;
  try {
    if (m.type === "scene") { bvh = buildBVH(m.tris); self.postMessage({ type: "scene-ok", nodes: bvh.size }); return; }
    if (m.type === "radiation") return radiation(m);
    if (m.type === "sunhours") return sunhours(m);
  } catch (e) {
    self.postMessage({ type: "error", message: String(e && e.message || e) });
  }
};

function radiation({ pts, nrm, dirs, energies, id }) {
  const n = pts.length / 3, P = dirs.length / 3;
  const keys = Object.keys(energies);
  const res = Object.fromEntries(keys.map((k) => [k, new Float32Array(n)]));
  const E = keys.map((k) => energies[k]), R = keys.map((k) => res[k]);
  let last = 0;
  for (let i = 0; i < n; i++) {
    const ox = pts[3 * i], oy = pts[3 * i + 1], oz = pts[3 * i + 2];
    const nx = nrm[3 * i], ny = nrm[3 * i + 1], nz = nrm[3 * i + 2];
    const acc = new Float64Array(keys.length);
    for (let p = 0; p < P; p++) {
      const dx = dirs[3 * p], dy = dirs[3 * p + 1], dz = dirs[3 * p + 2];
      const c = nx * dx + ny * dy + nz * dz;
      if (c <= 0) continue;
      if (occluded(bvh, ox, oy, oz, dx, dy, dz, stack)) continue;
      for (let k = 0; k < keys.length; k++) acc[k] += c * E[k][p];
    }
    for (let k = 0; k < keys.length; k++) R[k][i] = acc[k] / 1000;  // kWh/m2
    if (i - last > 400) { last = i; self.postMessage({ type: "progress", id, done: i, total: n }); }
  }
  self.postMessage({ type: "radiation-ok", id, res }, keys.map((k) => res[k].buffer));
}

function sunhours({ pts, nrm, suns, step, id }) {
  const n = pts.length / 3, out = new Float32Array(n);
  let last = 0;
  for (let i = 0; i < n; i++) {
    const ox = pts[3 * i], oy = pts[3 * i + 1], oz = pts[3 * i + 2];
    const nx = nrm[3 * i], ny = nrm[3 * i + 1], nz = nrm[3 * i + 2];
    let h = 0;
    for (const v of suns) {
      if (nx * v[0] + ny * v[1] + nz * v[2] <= 0) continue;
      if (!occluded(bvh, ox, oy, oz, v[0], v[1], v[2], stack)) h += step;
    }
    out[i] = h;
    if (i - last > 2000) { last = i; self.postMessage({ type: "progress", id, done: i, total: n }); }
  }
  self.postMessage({ type: "sunhours-ok", id, res: out }, [out.buffer]);
}
