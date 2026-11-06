const $ = (id) => document.getElementById(id);
let RID = null;

const SETTING_IDS = ["language", "font", "city", "header_right", "footer_text",
  "cooling_threshold", "heating_threshold", "sun_threshold", "nv_min", "nv_max"];
const TEXT_IDS = ["temperature_text", "sun_text", "ventilation_text", "shading_text", "wind_text", "seasonal_wind_text"];
const FIXED_IDS = ["ventilation_text", "shading_text", "wind_text", "seasonal_wind_text"];
let SHEETS = [];

function settings() {
  const s = {};
  for (const k of SETTING_IDS) s[k] = $(k).value;
  s.utci_sun_exposed = $("utci_sun_exposed").checked;
  s.sheets = SHEETS.filter((k) => $(`sheet_${k}`).checked).join(",");
  for (const k of SHEETS) s[`${k}_title`] = $(`title_${k}`).value;
  s.shading_devices = [...document.querySelectorAll(".dev")].map((r) => ({
    facade_az: r.querySelector(".d-az").value, type: r.querySelector(".d-type").value, overhang_deg: r.querySelector(".d-ov").value,
    fin_deg: r.querySelector(".d-fin").value, fin_side: r.querySelector(".d-side").value,
  }));
  return s;
}
function texts() {
  const t = {};
  for (const k of TEXT_IDS) t[k] = $(k).value;
  return t;
}

// ---------- sheets list + fixed method texts (placeholders show the default wording)
async function loadSheets() {
  const j = await api("/api/sheets", settings0());
  SHEETS = j.sheets.map((x) => x.key);
  $("sheets").innerHTML = j.sheets.map((x) => `
    <label class="sheet-row check"><input type="checkbox" id="sheet_${x.key}" checked>
      <input type="text" id="title_${x.key}" placeholder="${x.title}"></label>`).join("");
  for (const k of SHEETS) {
    $(`sheet_${k}`).addEventListener("change", () => RID && render());
  }
  const opts = (pairs, v) => pairs.map(([o, t]) => `<option value="${o}"${o === v ? " selected" : ""}>${t}</option>`).join("");
  const TYPES = [["none", "Sin protección"], ["overhang", "Voladizo"], ["fins", "Lamas verticales"], ["both", "Voladizo + lamas"]];
  const SIDES = [["right", "Derecha"], ["left", "Izquierda"], ["both", "Ambos lados"]];
  $("devices").innerHTML = j.shading_devices.map((d) => `
    <div class="dev">
      <div class="dev-top"><span class="dev-name">${d.name}</span>
        <select class="d-type">${opts(TYPES, d.type || "both")}</select></div>
      <div class="dev-params">
        <label>Orient. º<input class="d-az" type="number" step="5" min="0" max="355" value="${d.facade_az}"></label>
        <label class="l-ov">Voladizo º<input class="d-ov" type="number" step="5" min="0" max="85" value="${d.overhang_deg}"></label>
        <label class="l-fin">Lamas º<input class="d-fin" type="number" step="5" min="0" max="85" value="${d.fin_deg}"></label>
        <label class="l-fin">Lado<select class="d-side">${opts(SIDES, d.fin_side)}</select></label>
      </div>
    </div>`).join("");
  const NAMES = { 0: "Norte", 90: "Este", 180: "Sur", 270: "Oeste" };
  const syncDev = (row) => {
    const t = row.querySelector(".d-type").value;
    const az = ((Number(row.querySelector(".d-az").value) % 360) + 360) % 360;
    row.querySelector(".dev-name").textContent = `Fachada ${NAMES[az] || az + "°"}`;
    row.querySelector(".l-ov").classList.toggle("off", !(t === "overhang" || t === "both"));
    row.querySelectorAll(".l-fin").forEach((l) => l.classList.toggle("off", !(t === "fins" || t === "both")));
  };
  document.querySelectorAll(".dev").forEach((row) => {
    syncDev(row);
    row.querySelectorAll("input, select").forEach((el) => el.addEventListener("change", () => { syncDev(row); if (RID) render(); }));
  });
  await refreshDefaults();
}
function settings0() {  // settings without the sheet widgets (used before they exist)
  const s = {};
  for (const k of SETTING_IDS) s[k] = $(k).value;
  return s;
}
async function refreshDefaults() {
  const j = await api("/api/sheets", settings0());
  for (const x of j.sheets) {
    const el = $(`title_${x.key}`);
    if (el) el.placeholder = x.title;
  }
  for (const k of FIXED_IDS) { $(k).placeholder = j.method_texts[k] || ""; countWords(k); }
}

// ---------- feedback: loading modal + toast
let busyTimer = null;
function busy(title, text = "") {
  $("busy-title").textContent = title;
  $("busy-text").textContent = text;
  const t0 = Date.now();
  $("busy-elapsed").textContent = "";
  clearInterval(busyTimer);
  busyTimer = setInterval(() => {
    const s = Math.round((Date.now() - t0) / 1000);
    $("busy-elapsed").textContent = s >= 2 ? `${s} s` : "";
  }, 500);
  $("overlay").classList.add("show");
}
function idle() {
  clearInterval(busyTimer);
  $("overlay").classList.remove("show");
}
let toastTimer = null;
function toast(msg, error = false) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.toggle("error", error);
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), error ? 5000 : 2500);
}
async function withBusy(title, text, fn) {
  busy(title, text);
  try { return await fn(); }
  catch (err) { toast(err.message || "Error", true); }
  finally { idle(); }
}

async function api(path, body, raw = false) {
  const r = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (raw) return r;
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(j.error || j.detail || r.statusText), { data: j });
  return j;
}

async function loadFonts() {
  const j = await api("/api/fonts");
  $("font").innerHTML = j.fonts.map((f) => `<option${f === j.default ? " selected" : ""}>${f}</option>`).join("");
}

const LLM_HINTS = {
  ollama: "por defecto (localhost:11434)",
  lmstudio: "por defecto (localhost:1234)",
  openai: "https://servidor/v1 (obligatoria)",
};
function llmPrefs(save) {  // remember engine, URL and model in this browser (never the API key)
  try {
    if (save) {
      localStorage.setItem("climate-report-llm", JSON.stringify(
        { backend: $("backend").value, url: $("llm_url").value, model: $("model").value }));
      return null;
    }
    return JSON.parse(localStorage.getItem("climate-report-llm") || "null");
  } catch (_) { return null; }
}
function syncLlmFields() {
  const b = $("backend").value;
  $("llm_url").placeholder = LLM_HINTS[b] || "";
  $("llm_key_row").hidden = b === "ollama";
  $("gen").disabled = !$("model").value.trim();
}

async function loadModels() {
  syncLlmFields();
  const q = new URLSearchParams({ backend: $("backend").value });
  if ($("llm_url").value) q.set("url", $("llm_url").value);
  const key = $("llm_key").value.trim();
  const r = await transport("/api/llm/models?" + q, key ? { headers: { "X-Api-Key": key } } : {});
  const j = await r.json().catch(() => ({ ok: false, models: [] }));
  $("model-list").innerHTML = j.models.map((m) => `<option value="${m}"></option>`).join("");
  const current = $("model").value.trim();
  if (!current || (j.ok && j.models.length && !j.models.includes(current))) {
    // prefer the models that follow the reference style best (tested): llama3.1:8b, gemma4
    const pref = ["llama3.1:8b", "gemma4"].map((p) => j.models.find((m) => m.startsWith(p))).find(Boolean);
    $("model").value = pref || j.models[0] || current;
  }
  const el = $("llmstatus");
  el.textContent = j.ok ? `● ${j.models.length} modelo(s) disponible(s)`
    : ($("backend").value === "openai" && $("model").value.trim()
      ? "● No se pudo listar modelos: se usará el que has escrito"
      : "● LLM no disponible: modo manual");
  el.title = j.error || "";
  el.classList.toggle("warn", !j.ok);
  syncLlmFields();
}

async function doRender() {
  const j = await api(`/api/${RID}/preview`, { settings: settings(), texts: texts() });
  $("preview").innerHTML = j.svgs.map((s) => `<div class="sheet">${s.replace(/^<\?xml[^>]*>/, "")}</div>`).join("");
}
async function render() {
  if (!RID) return toast("Primero sube un EPW", true);
  await withBusy("Dibujando láminas", "Componiendo los gráficos A3…", doRender);
}

// ---------- EPW: one file for both tabs, loaded from the top-bar button (modal)
const epwModal = {
  open() { $("epw-modal").classList.add("show"); },
  close() { $("epw-modal").classList.remove("show"); },
};
$("epw-open").addEventListener("click", () => epwModal.open());
$("epw-close").addEventListener("click", () => epwModal.close());
$("epw-modal").addEventListener("click", (e) => { if (e.target === $("epw-modal")) epwModal.close(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") epwModal.close(); });
const drop = $("epw-drop");
drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("is-dragging"); });
drop.addEventListener("dragleave", () => drop.classList.remove("is-dragging"));
drop.addEventListener("drop", (e) => {
  e.preventDefault();
  drop.classList.remove("is-dragging");
  if (e.dataTransfer.files[0]) loadEpw(e.dataTransfer.files[0]);
});
$("epw").addEventListener("change", (e) => { if (e.target.files[0]) loadEpw(e.target.files[0]); });

async function loadEpw(f) {
  if (!f.name.toLowerCase().endsWith(".epw")) return toast("Selecciona un archivo .epw", true);
  $("epw_name").textContent = f.name;
  epwModal.close();
  await withBusy("Analizando el EPW", "Calculando confort UTCI y posiciones solares…", async () => {
    const fd = new FormData();
    fd.append("file", f);
    const r = await fetch("/api/upload", { method: "POST", body: fd });
    const j = await r.json();
    if (!r.ok) throw new Error(j.detail || "Error al leer el EPW");
    RID = j.id;
    sendEpwToSunExplore(f.name);
    $("loc").textContent = `${j.city}, ${j.country} · ${j.latitude.toFixed(2)}°, ${j.longitude.toFixed(2)}° · ${Math.round(j.elevation)} m`;
    $("epw-chip-text").textContent = `EPW · ${j.city}, ${j.country}`;
    $("epw-open").classList.add("is-loaded");
    $("epw-open").title = `${f.name} · clic para cambiarlo`;
    $("city").placeholder = j.city;
    $("busy-title").textContent = "Dibujando láminas";
    $("busy-text").textContent = "Componiendo los gráficos A3…";
    await doRender();
  });
}

$("gen").addEventListener("click", async () => {
  if (!RID) return toast("Primero sube un EPW", true);
  const steps = [["temperature_text", "texto de temperatura"], ["sun_text", "texto de sol"]];
  busy("El LLM está redactando", "");
  try {
    for (const [i, [key, name]] of steps.entries()) {  // one short request per text
      $("busy-title").textContent = `El LLM está redactando (${i + 1}/${steps.length})`;
      $("busy-text").textContent = `${name} · ${$("model").value}`;
      const j = await api(`/api/${RID}/generate`, {
        settings: settings(), backend: $("backend").value, model: $("model").value.trim(),
        url: $("llm_url").value || null, api_key: $("llm_key").value.trim() || null, keys: [key],
      });
      setTexts(j);
    }
    $("busy-title").textContent = "Dibujando láminas";
    $("busy-text").textContent = "Colocando los textos…";
    await doRender();
    toast("Textos generados");
  } catch (err) {
    const why = (err.message || "").replace(/^\w+ generation failed: /, "");
    toast(`No se pudo generar con el LLM${why ? ": " + why.slice(0, 160) : ""}. Prueba otra vez, otro modelo o el modo manual.`, true);
  } finally {
    idle();
  }
});

$("copyprompt").addEventListener("click", async () => {
  if (!RID) return toast("Primero sube un EPW", true);
  const j = await api(`/api/${RID}/prompt`, settings());
  try { await navigator.clipboard.writeText(j.prompt); toast("Prompt copiado al portapapeles"); }
  catch { $("paste").value = j.prompt; toast("Copia el prompt desde el cuadro «Pegar respuesta»"); }
});

// ---------- word counters (limits come from layout/a3_climate.json)
let LIMITS = {};
function countWords(id) {
  const n = (($(id).value || $(id).placeholder || "").match(/\S+/g) || []).length;
  const max = LIMITS[id] ? LIMITS[id].max_words : null;
  const el = $(id + "_count");
  el.textContent = max ? `${n} / ${max} palabras` : `${n} palabras`;
  el.classList.toggle("over", !!max && n > max);
}
for (const id of TEXT_IDS) $(id).addEventListener("input", () => countWords(id));
function setTexts(j) {
  if (j.temperature_text) $("temperature_text").value = j.temperature_text;
  if (j.sun_text) $("sun_text").value = j.sun_text;
  countWords("temperature_text"); countWords("sun_text");
}

$("paste").addEventListener("input", async () => {
  const v = $("paste").value;
  const a = v.indexOf("{"), b = v.lastIndexOf("}");
  if (a < 0 || b < a) return;
  try { JSON.parse(v.slice(a, b + 1)); } catch { return; /* still typing */ }
  setTexts(await api("/api/parse", { raw: v }));  // same paragraph + word-limit rules as the LLM
  toast("Textos importados y ajustados al límite de palabras");
});

$("render").addEventListener("click", render);
$("backend").addEventListener("change", () => { $("model").value = ""; loadModels(); llmPrefs(true); });
$("refresh").addEventListener("click", loadModels);
for (const id of ["llm_url", "llm_key"]) $(id).addEventListener("change", () => { loadModels(); llmPrefs(true); });
$("model").addEventListener("input", () => { syncLlmFields(); llmPrefs(true); });
(() => {  // restore the last engine / URL / model
  const p = llmPrefs(false);
  if (!p) return;
  if (p.backend) $("backend").value = p.backend;
  $("llm_url").value = p.url || "";
  $("model").value = p.model || "";
})();
for (const id of ["language", "font", "utci_sun_exposed"]) $(id).addEventListener("change", () => RID && render());

document.querySelectorAll(".dl").forEach((btn) => btn.addEventListener("click", async () => {
  if (!RID) return toast("Primero sube un EPW", true);
  const fmt = btn.dataset.fmt;
  await withBusy(`Generando ${fmt.toUpperCase()}`, "Preparando el archivo A3 para descargar…", async () => {
    const r = await api(`/api/${RID}/download/${fmt}`, { settings: settings(), texts: texts() }, true);
    if (!r.ok) throw new Error("Error al generar el archivo");
    const blob = await r.blob();
    const name = (r.headers.get("Content-Disposition") || "").match(/filename="(.+)"/)?.[1] || `report.${fmt}`;
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: name });
    a.click();
    URL.revokeObjectURL(a.href);
    toast(`${name} descargado`);
  });
}));

api("/api/limits").then((j) => { LIMITS = j; TEXT_IDS.forEach(countWords); });
for (const id of ["language", "nv_min", "nv_max", "sun_threshold"]) $(id).addEventListener("change", refreshDefaults);
// ---------- tabs: climate analysis / SunExplore (same EPW in both)
let sunexploreName = null;
function sunexploreMsg(name) {
  return { type: "load-epw", url: `/api/${RID}/epw`, name: name || "climate.epw", minT: $("sun_threshold").value };
}
function sendEpwToSunExplore(name) {
  sunexploreName = name;
  const frame = $("sunexplore");
  frame.contentWindow?.postMessage(sunexploreMsg(name), window.location.origin);
}
$("sunexplore").addEventListener("load", () => {  // the tab may load after the upload
  if (RID) $("sunexplore").contentWindow.postMessage(sunexploreMsg(sunexploreName), window.location.origin);
});
document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => {
  const view = tab.dataset.view;
  document.querySelectorAll(".tab").forEach((t) => {
    t.classList.toggle("is-active", t === tab);
    t.setAttribute("aria-selected", t === tab ? "true" : "false");
  });
  $("view-analysis").hidden = view !== "analysis";
  $("view-sunexplore").hidden = view !== "sunexplore";
  // Plotly / three.js measure their container: resize once the tab is visible
  if (view === "sunexplore") $("sunexplore").contentWindow?.dispatchEvent(new Event("resize"));
}));

loadFonts().then(loadSheets).then(loadModels).then(() => { if (!RID) epwModal.open(); });
