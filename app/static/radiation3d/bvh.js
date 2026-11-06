// Small bounding-volume hierarchy for shadow rays (any-hit occlusion), no dependencies.
// Triangles: Float32Array, 9 floats per triangle.

export function buildBVH(tris) {
  const n = tris.length / 9;
  const cen = new Float32Array(3 * n), bmin = new Float32Array(3 * n), bmax = new Float32Array(3 * n);
  for (let t = 0; t < n; t++) for (let k = 0; k < 3; k++) {
    const a = tris[9 * t + k], b = tris[9 * t + 3 + k], c = tris[9 * t + 6 + k];
    bmin[3 * t + k] = Math.min(a, b, c); bmax[3 * t + k] = Math.max(a, b, c); cen[3 * t + k] = (a + b + c) / 3;
  }
  const order = new Uint32Array(n);
  for (let i = 0; i < n; i++) order[i] = i;
  const nodes = [];  // [minx,miny,minz,maxx,maxy,maxz, left|start, right|count, isLeaf]
  const LEAF = 4;
  function build(start, end) {
    const id = nodes.length;
    const node = { min: [Infinity, Infinity, Infinity], max: [-Infinity, -Infinity, -Infinity], a: 0, b: 0, leaf: false };
    nodes.push(node);
    const cmin = [Infinity, Infinity, Infinity], cmax = [-Infinity, -Infinity, -Infinity];
    for (let i = start; i < end; i++) {
      const t = order[i];
      for (let k = 0; k < 3; k++) {
        node.min[k] = Math.min(node.min[k], bmin[3 * t + k]); node.max[k] = Math.max(node.max[k], bmax[3 * t + k]);
        cmin[k] = Math.min(cmin[k], cen[3 * t + k]); cmax[k] = Math.max(cmax[k], cen[3 * t + k]);
      }
    }
    const count = end - start;
    let axis = 0;
    for (let k = 1; k < 3; k++) if (cmax[k] - cmin[k] > cmax[axis] - cmin[axis]) axis = k;
    if (count <= LEAF || cmax[axis] - cmin[axis] < 1e-9) { node.leaf = true; node.a = start; node.b = count; return id; }
    const mid = (cmin[axis] + cmax[axis]) / 2;
    let i = start, j = end - 1;
    while (i <= j) {
      if (cen[3 * order[i] + axis] < mid) i++;
      else { const tmp = order[i]; order[i] = order[j]; order[j] = tmp; j--; }
    }
    let split = i;
    if (split === start || split === end) split = (start + end) >> 1;
    node.a = build(start, split);
    node.b = build(split, end);
    return id;
  }
  if (n) build(0, n);
  const N = nodes.length;
  const box = new Float32Array(6 * N), link = new Int32Array(3 * N);
  nodes.forEach((nd, i) => {
    box.set(nd.min, 6 * i); box.set(nd.max, 6 * i + 3);
    link[3 * i] = nd.a; link[3 * i + 1] = nd.b; link[3 * i + 2] = nd.leaf ? 1 : 0;
  });
  const T = new Float32Array(tris.length);
  for (let i = 0; i < n; i++) T.set(tris.subarray(9 * order[i], 9 * order[i] + 9), 9 * i);
  return { box, link, tris: T, size: N };
}

// true if the ray o + t d (t > eps) hits any triangle
export function occluded(bvh, ox, oy, oz, dx, dy, dz, stack) {
  if (!bvh.size) return false;
  const { box, link, tris: T } = bvh;
  const ix = 1 / dx, iy = 1 / dy, iz = 1 / dz;
  let sp = 0;
  stack[sp++] = 0;
  while (sp) {
    const n = stack[--sp], b = 6 * n;
    let t0 = (box[b] - ox) * ix, t1 = (box[b + 3] - ox) * ix;
    let tmin = Math.min(t0, t1), tmax = Math.max(t0, t1);
    t0 = (box[b + 1] - oy) * iy; t1 = (box[b + 4] - oy) * iy;
    tmin = Math.max(tmin, Math.min(t0, t1)); tmax = Math.min(tmax, Math.max(t0, t1));
    t0 = (box[b + 2] - oz) * iz; t1 = (box[b + 5] - oz) * iz;
    tmin = Math.max(tmin, Math.min(t0, t1)); tmax = Math.min(tmax, Math.max(t0, t1));
    if (tmax < Math.max(tmin, 0)) continue;
    const l = 3 * n;
    if (link[l + 2]) {
      for (let k = link[l], e = link[l] + link[l + 1]; k < e; k++) {
        const p = 9 * k;
        const e1x = T[p + 3] - T[p], e1y = T[p + 4] - T[p + 1], e1z = T[p + 5] - T[p + 2];
        const e2x = T[p + 6] - T[p], e2y = T[p + 7] - T[p + 1], e2z = T[p + 8] - T[p + 2];
        const px = dy * e2z - dz * e2y, py = dz * e2x - dx * e2z, pz = dx * e2y - dy * e2x;
        const det = e1x * px + e1y * py + e1z * pz;
        if (det > -1e-12 && det < 1e-12) continue;
        const inv = 1 / det;
        const sx = ox - T[p], sy = oy - T[p + 1], sz = oz - T[p + 2];
        const u = (sx * px + sy * py + sz * pz) * inv;
        if (u < 0 || u > 1) continue;
        const qx = sy * e1z - sz * e1y, qy = sz * e1x - sx * e1z, qz = sx * e1y - sy * e1x;
        const v = (dx * qx + dy * qy + dz * qz) * inv;
        if (v < 0 || u + v > 1) continue;
        if ((e2x * qx + e2y * qy + e2z * qz) * inv > 1e-4) return true;
      }
    } else {
      stack[sp++] = link[l];
      stack[sp++] = link[l + 1];
    }
  }
  return false;
}
