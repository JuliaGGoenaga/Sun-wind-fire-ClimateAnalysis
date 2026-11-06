// EPW -> sun positions and cumulative sky matrices (Reinhart 577 sky patches + ground hemisphere).
// Direct normal irradiance of each hour goes to the patch that contains the sun; diffuse sky is
// isotropic (DHI / pi radiance) and the ground reflects albedo * GHI isotropically from below.
// Every patch stores E = energy through a surface normal to the patch direction (Wh/m2), so the
// irradiation on a surface with normal n is  sum_p visible_p * max(0, n.d_p) * E_p.

function csv(line) { return line.split(","); }

export function parseEpw(text) {
  const lines = text.replace(/^﻿/, "").split(/\r?\n/);
  const loc = csv(lines.find((l) => l.toUpperCase().startsWith("LOCATION")) || "");
  const lat = Number(loc[6]), lon = Number(loc[7]), tz = Number(loc[8]);
  if (![lat, lon, tz].every(Number.isFinite)) throw new Error("EPW sin cabecera LOCATION válida");
  const hours = [];
  for (const l of lines) {
    if (!/^\s*\d{4},/.test(l)) continue;
    const r = csv(l);
    if (r.length < 16) continue;
    hours.push({ month: +r[1], day: +r[2], hour: +r[3], t: +r[6], ghi: Math.max(0, +r[13] || 0),
      dni: Math.max(0, +r[14] || 0), dhi: Math.max(0, +r[15] || 0) });
  }
  if (hours.length < 8760) throw new Error("El EPW no tiene 8760 horas");
  return { city: (loc[1] || "").trim(), country: (loc[3] || "").trim(), lat, lon, tz, hours: hours.slice(0, 8760) };
}

// NOAA solar position (same formula as the SunExplore tab). localHour = local standard time.
export function solarPosition(month, day, localHour, lat, lon, tz) {
  const date = Date.UTC(2021, month - 1, day);
  const doy = Math.floor((date - Date.UTC(2021, 0, 0)) / 86400000);
  const g = 2 * Math.PI / 365 * (doy - 1 + (localHour - 12) / 24);
  const eot = 229.18 * (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g) - 0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g));
  const decl = 0.006918 - 0.399912 * Math.cos(g) + 0.070257 * Math.sin(g) - 0.006758 * Math.cos(2 * g)
    + 0.000907 * Math.sin(2 * g) - 0.002697 * Math.cos(3 * g) + 0.00148 * Math.sin(3 * g);
  const ha = ((localHour * 60 + eot + 4 * lon - 60 * tz) / 4 - 180) * Math.PI / 180;
  const la = lat * Math.PI / 180;
  const cz = Math.max(-1, Math.min(1, Math.sin(la) * Math.sin(decl) + Math.cos(la) * Math.cos(decl) * Math.cos(ha)));
  const elevation = 90 - Math.acos(cz) * 180 / Math.PI;
  const azimuth = (Math.atan2(Math.sin(ha), Math.cos(ha) * Math.sin(la) - Math.tan(decl) * Math.cos(la)) * 180 / Math.PI + 540) % 360;
  return { azimuth, elevation };
}

// Direction (model coordinates, Z up). Azimuth clockwise from north; north = +Y rotated by northDeg
// counter-clockwise (same convention as Ladybug's "north" input).
export function sunVector(azimuth, elevation, northDeg = 0) {
  const a = (azimuth - northDeg) * Math.PI / 180, e = elevation * Math.PI / 180;
  return [Math.sin(a) * Math.cos(e), Math.cos(a) * Math.cos(e), Math.sin(e)];
}

const ROWS = [60, 60, 60, 60, 48, 48, 48, 48, 36, 36, 24, 24, 12, 12];  // Reinhart MF2, 6 deg rows
const TREG = [30, 30, 24, 24, 18, 12, 6];                                // Tregenza, 12 deg rows (ground)

function patchSet(rows, band, sign) {
  const out = [];
  rows.forEach((n, r) => {
    const a0 = r * band, a1 = a0 + band, ac = (a0 + a1) / 2;
    const omega = 2 * Math.PI * (Math.sin(a1 * Math.PI / 180) - Math.sin(a0 * Math.PI / 180)) / n;
    for (let j = 0; j < n; j++) out.push({ alt: sign * ac, az: (j + 0.5) * 360 / n, omega, row: r, n });
  });
  const top = rows.length * band;
  out.push({ alt: sign * 90, az: 0, omega: 2 * Math.PI * (1 - Math.sin(top * Math.PI / 180)), row: rows.length, n: 1 });
  return out;
}

export function skyPatches() {
  const sky = patchSet(ROWS, 6, 1), ground = patchSet(TREG, 12, -1);
  return { sky, ground, all: sky.concat(ground) };
}

function skyIndex(alt, az) {
  const r = Math.floor(alt / 6);
  if (r >= ROWS.length) return ROWS.reduce((a, b) => a + b, 0);
  let base = 0;
  for (let i = 0; i < r; i++) base += ROWS[i];
  return base + Math.floor(((az % 360) + 360) % 360 / (360 / ROWS[r]));
}

export function seasonMonths(lat) {
  return lat >= 0 ? { summer: [6, 7, 8], winter: [12, 1, 2] } : { summer: [12, 1, 2], winter: [6, 7, 8] };
}

// Returns directions (Float32Array 3*N) and energies per period (Float32Array N, Wh/m2).
export function skyMatrices(epw, northDeg, albedo) {
  const P = skyPatches(), nSky = P.sky.length, N = P.all.length;
  const dirs = new Float32Array(3 * N);
  P.all.forEach((p, i) => dirs.set(sunVector(p.az, p.alt, northDeg), 3 * i));
  const seasons = seasonMonths(epw.lat);
  const periods = { annual: () => true, summer: (m) => seasons.summer.includes(m), winter: (m) => seasons.winter.includes(m) };
  const out = {};
  for (const [key, inPeriod] of Object.entries(periods)) {
    const E = new Float64Array(N);
    let dhi = 0, ghi = 0;
    for (const h of epw.hours) {
      if (!inPeriod(h.month)) continue;
      dhi += h.dhi; ghi += h.ghi;
      if (h.dni <= 0) continue;
      const s = solarPosition(h.month, h.day, h.hour - 0.5, epw.lat, epw.lon, epw.tz);
      if (s.elevation <= 0) continue;
      E[skyIndex(s.elevation, s.azimuth)] += h.dni;
    }
    for (let i = 0; i < nSky; i++) E[i] += dhi / Math.PI * P.all[i].omega;
    for (let i = nSky; i < N; i++) E[i] += albedo * ghi / Math.PI * P.all[i].omega;
    out[key] = Float32Array.from(E);
  }
  return { dirs, energies: out, seasons, nSky };
}

export const KEY_DAYS = [
  { key: "mar", label: "21 de marzo · equinoccio", month: 3, day: 21 },
  { key: "jun", label: "21 de junio · solsticio", month: 6, day: 21 },
  { key: "sep", label: "23 de septiembre · equinoccio", month: 9, day: 23 },
  { key: "dec", label: "21 de diciembre · solsticio", month: 12, day: 21 },
];

// Sun vectors of one day every `step` hours (mid-interval), only with the sun above the horizon.
export function daySuns(epw, month, day, northDeg, step = 1 / 6) {
  const out = [];
  for (let t = step / 2; t < 24; t += step) {
    const s = solarPosition(month, day, t, epw.lat, epw.lon, epw.tz);
    if (s.elevation > 0.5) out.push({ t, ...s, v: sunVector(s.azimuth, s.elevation, northDeg) });
  }
  return out;
}
