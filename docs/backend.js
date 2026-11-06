/* Climate report — browser backend (GitHub Pages build).

   The web app (app.js) talks to "/api/..." endpoints. When this file is loaded,
   window.LOCAL_API answers those calls inside the browser instead of a server:
   Python (report/web.py) runs in a Pyodide Web Worker (worker.js), the LLM is
   called directly (Ollama / LM Studio on the user's computer), and PDF / PPTX /
   SVG files are assembled here with jsPDF + svg2pdf, PptxGenJS and JSZip. */
(() => {
  const LIBS = {
    jspdf: "https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js",
    svg2pdf: "https://cdn.jsdelivr.net/npm/svg2pdf.js@2.2.3/dist/svg2pdf.umd.min.js",
    pptx: "https://cdn.jsdelivr.net/npm/pptxgenjs@3.12.0/dist/pptxgen.bundle.js",
    jszip: "https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js",
  };
  const LLM_URLS = { ollama: "http://localhost:11434", lmstudio: "http://localhost:1234" };
  const MM = 1 / 25.4;  // mm -> inch

  // ---------------------------------------------------------------- worker RPC
  const worker = new Worker("./worker.js");
  let seq = 0;
  const pending = new Map();
  let progressText = "Cargando Python en el navegador…";
  let isReady = false;
  worker.onmessage = (e) => {
    const m = e.data;
    if (m.progress) {
      progressText = m.progress;
      const el = document.getElementById("busy-text");
      if (el && document.getElementById("overlay")?.classList.contains("show")) el.textContent = m.progress;
      return;
    }
    const p = pending.get(m.id);
    if (!p) return;
    pending.delete(m.id);
    m.error ? p.reject(new Error(m.error)) : p.resolve(m.result);
  };
  const call = (fn, ...args) => new Promise((resolve, reject) => {
    const id = ++seq;
    pending.set(id, { resolve, reject });
    worker.postMessage({ id, fn, args });
  });
  const ready = call("ping").then(() => { isReady = true; });

  async function waitReady() {
    if (isReady) return;
    const showing = window.busy && !document.getElementById("overlay")?.classList.contains("show");
    if (showing) window.busy("Preparando la herramienta", progressText);
    try { await ready; } finally { if (showing) window.idle(); }
  }

  // ----------------------------------------------------------------- helpers
  const json = (obj, status = 200) => new Response(JSON.stringify(obj), {
    status, headers: { "Content-Type": "application/json" },
  });
  const fileResponse = (blob, name) => new Response(blob, {
    headers: { "Content-Disposition": `attachment; filename="${name}"` },
  });
  const loaded = {};
  const loadScript = (src) => loaded[src] || (loaded[src] = new Promise((res, rej) => {
    const s = Object.assign(document.createElement("script"), { src, onload: res, onerror: () => rej(new Error("No se pudo cargar " + src)) });
    document.head.appendChild(s);
  }));
  const stem = (city) => (city || "climate").replace(/[^A-Za-z0-9]+/g, "_").replace(/^_|_$/g, "") || "climate";

  // ------------------------------------------------------------------- LLM
  async function llmModels(backend, url) {
    const base = (url || LLM_URLS[backend]).replace(/\/$/, "");
    try {
      if (backend === "ollama") {
        const r = await fetch(`${base}/api/tags`);
        if (!r.ok) throw new Error(r.statusText);
        return { ok: true, models: (await r.json()).models.map((m) => m.name).sort() };
      }
      const r = await fetch(`${base}/v1/models`);
      if (!r.ok) throw new Error(r.statusText);
      return { ok: true, models: (await r.json()).data.map((m) => m.id).sort() };
    } catch (err) {
      return { ok: false, models: [], error: `${backend} no accesible en ${base}: ${err.message}. ` +
        "Si está abierto, permite esta web (Ollama: OLLAMA_ORIGINS; LM Studio: activar CORS)." };
    }
  }

  async function llmGenerate(backend, url, model, system, prompt) {
    const base = (url || LLM_URLS[backend]).replace(/\/$/, "");
    const messages = [{ role: "system", content: system }, { role: "user", content: prompt }];
    let r;
    if (backend === "ollama") {
      r = await fetch(`${base}/api/chat`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model, messages, stream: false,
          options: { temperature: 0, seed: 42, top_k: 1, num_ctx: 8192 } }),
      });
      if (!r.ok) throw new Error(`${backend}: ${r.status} ${r.statusText}`);
      return (await r.json()).message.content.trim();
    }
    r = await fetch(`${base}/v1/chat/completions`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model, messages, temperature: 0, seed: 42, stream: false }),
    });
    if (!r.ok) throw new Error(`${backend}: ${r.status} ${r.statusText}`);
    return (await r.json()).choices[0].message.content.trim();
  }

  async function generate(body) {
    const spec = JSON.parse(await call("text_prompts", JSON.stringify(body)));
    const texts = {};
    try {
      for (const [key, prompt] of Object.entries(spec.prompts)) {
        let raw = await llmGenerate(body.backend || "ollama", body.url, body.model, spec.system, prompt);
        if (!JSON.parse(await call("check_language", raw, spec.language))) {  // one stricter retry
          raw = await llmGenerate(body.backend || "ollama", body.url, body.model, spec.system, prompt + spec.strict_suffix);
        }
        texts[key] = JSON.parse(await call("fit", key, raw));
      }
    } catch (err) {
      const p = JSON.parse(await call("prompt", JSON.stringify(body.settings || {})));
      return json({ error: err.message, prompt: p.prompt }, 503);
    }
    return json(texts);
  }

  // ---------------------------------------------------------------- exports
  const PDF_FONT = (family) => /times|georgia/i.test(family) ? "times" : /courier/i.test(family) ? "courier" : "helvetica";

  async function toPdf(body) {
    await loadScript(LIBS.jspdf);
    await loadScript(LIBS.svg2pdf);
    const data = JSON.parse(await call("svg_pages", JSON.stringify(body)));
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF({ orientation: "landscape", unit: "mm", format: [420, 297], compress: true });
    const font = PDF_FONT(data.font);
    for (let i = 0; i < data.svgs.length; i++) {
      if (i) doc.addPage([420, 297], "landscape");
      // standard PDF fonts only in the browser: map the family, keep the layout
      const svgText = data.svgs[i].replace(/^<\?xml[^>]*>/, "").replace(/font-family="[^"]*"/g, `font-family="${font}"`);
      const el = new DOMParser().parseFromString(svgText, "image/svg+xml").documentElement;
      await doc.svg(el, { x: 0, y: 0, width: 420, height: 297 });
    }
    return fileResponse(doc.output("blob"), `${stem(data.city)}_climate_analysis.pdf`);
  }

  async function svgToPng(svg, wmm, hmm, dpi = 300) {
    const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
    try {
      const img = await new Promise((res, rej) => {
        const im = new Image();
        im.onload = () => res(im);
        im.onerror = () => rej(new Error("No se pudo rasterizar un gráfico"));
        im.src = url;
      });
      const w = Math.max(1, Math.round(wmm * MM * dpi)), h = Math.max(1, Math.round(hmm * MM * dpi));
      const canvas = Object.assign(document.createElement("canvas"), { width: w, height: h });
      const ctx = canvas.getContext("2d");
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, w, h);
      ctx.drawImage(img, 0, 0, w, h);
      return canvas.toDataURL("image/png");
    } finally {
      URL.revokeObjectURL(url);
    }
  }

  async function toPptx(body) {
    await loadScript(LIBS.pptx);
    const spec = JSON.parse(await call("pptx_spec", JSON.stringify(body)));
    const pptx = new window.PptxGenJS();
    pptx.defineLayout({ name: "A3", width: 420 * MM, height: 297 * MM });
    pptx.layout = "A3";
    for (const page of spec.pages) {
      const slide = pptx.addSlide();
      for (const it of page.items) {
        if (it.type === "image") {
          const data = await svgToPng(it.svg, it.w, it.h);
          slide.addImage({ data, x: it.x * MM, y: it.y * MM, w: it.w * MM, h: it.h * MM, altText: it.name });
        } else if (it.type === "line") {
          slide.addShape(pptx.ShapeType.line, {
            x: Math.min(it.x1, it.x2) * MM, y: Math.min(it.y1, it.y2) * MM,
            w: Math.abs(it.x2 - it.x1) * MM, h: Math.abs(it.y2 - it.y1) * MM,
            line: { color: it.color.replace("#", ""), width: it.width * 72 / 25.4, dashType: it.dash ? "dash" : "solid" },
          });
        } else if (it.type === "text") {
          const runs = it.paragraphs.map((p, i) => ({ text: p, options: { breakLine: i < it.paragraphs.length - 1 } }));
          const opts = {
            x: it.x * MM, y: it.y * MM, w: it.w * MM, h: it.h * MM, margin: 0, valign: "top",
            fontFace: spec.font, fontSize: it.size, color: it.color.replace("#", ""), align: it.align,
            fit: "none", wrap: it.paragraphs.length > 1 || it.w > 60,
          };
          if (it.leading) {
            opts.lineSpacing = it.size * it.leading;
            opts.paraSpaceAfter = it.size * it.leading;
          }
          slide.addText(runs, opts);
        }
      }
    }
    const blob = await pptx.write({ outputType: "blob" });
    return fileResponse(blob, `${stem(spec.city)}_climate_analysis.pptx`);
  }

  async function toSvgZip(body) {
    await loadScript(LIBS.jszip);
    const data = JSON.parse(await call("svg_pages", JSON.stringify(body)));
    const zip = new window.JSZip();
    const s = stem(data.city);
    data.svgs.forEach((svg, i) => zip.file(`${s}_${i + 1}.svg`, svg, { date: new Date("2020-01-01T00:00:00") }));
    return fileResponse(await zip.generateAsync({ type: "blob" }), `${s}_climate_analysis_svg.zip`);
  }

  // ------------------------------------------------------------------ router
  async function LOCAL_API(path, opts = {}) {
    await waitReady();
    const url = new URL(path, window.location.href);
    const p = url.pathname.replace(/^.*\/api\//, "/api/");
    const body = opts.body && typeof opts.body === "string" ? JSON.parse(opts.body) : opts.body;
    try {
      if (p === "/api/fonts") return json(JSON.parse(await call("fonts")));
      if (p === "/api/limits") return json(JSON.parse(await call("text_limits")));
      if (p === "/api/sheets") return json(JSON.parse(await call("sheets", JSON.stringify(body || {}))));
      if (p === "/api/parse") return json(JSON.parse(await call("parse", body.raw || "")));
      if (p === "/api/llm/models") {
        return json(await llmModels(url.searchParams.get("backend") || "ollama", url.searchParams.get("url")));
      }
      if (p === "/api/upload") {
        const file = body.get("file");
        const text = await file.text();
        if (!text.slice(0, 200).includes("LOCATION")) return json({ detail: "Esto no parece un archivo EPW" }, 400);
        if (window.EPW_URL) URL.revokeObjectURL(window.EPW_URL);
        window.EPW_URL = URL.createObjectURL(new Blob([text], { type: "text/plain" }));  // for the SunExplore tab
        return json(JSON.parse(await call("writeEpw", text)));
      }
      let m = p.match(/^\/api\/[^/]+\/(preview|prompt|generate)$/);
      if (m) {
        if (m[1] === "preview") return json(JSON.parse(await call("preview", JSON.stringify(body))));
        if (m[1] === "prompt") return json(JSON.parse(await call("prompt", JSON.stringify(body || {}))));
        return await generate(body);
      }
      m = p.match(/^\/api\/[^/]+\/download\/(pdf|pptx|svg)$/);
      if (m) return await { pdf: toPdf, pptx: toPptx, svg: toSvgZip }[m[1]](body);
      return json({ detail: "not found: " + p }, 404);
    } catch (err) {
      return json({ error: err.message, detail: err.message }, 500);
    }
  }

  // ------------------------------------------------------- logo (browser only)
  async function setLogo(file) {
    const ext = /svg/i.test(file.type) || /\.svg$/i.test(file.name) ? "svg" : "png";
    await call("writeLogo", await file.arrayBuffer(), ext);
  }
  async function restoreLogo() {
    try {
      const saved = JSON.parse(localStorage.getItem("climate-report-logo") || "null");
      if (!saved) return false;
      const bytes = Uint8Array.from(atob(saved.b64), (c) => c.charCodeAt(0));
      await call("writeLogo", bytes.buffer, saved.ext);
      return saved.name;
    } catch (_) { return false; }
  }
  function addLogoPicker() {
    const modal = document.querySelector("#epw-modal .epw-modal");
    if (!modal) return;
    const wrap = document.createElement("div");
    wrap.className = "logo-pick";
    wrap.innerHTML = `
      <label class="file" id="logo-drop">
        <input type="file" id="logo-file" accept=".png,.svg,image/png,image/svg+xml">
        <span class="file-btn">Logo</span>
        <span class="file-name" id="logo-name">Opcional: PNG o SVG para el pie de las láminas</span>
      </label>`;
    modal.appendChild(wrap);
    const name = wrap.querySelector("#logo-name");
    wrap.querySelector("#logo-file").addEventListener("change", async (e) => {
      const f = e.target.files[0];
      if (!f) return;
      await setLogo(f);
      name.textContent = f.name;
      try {
        const u8 = new Uint8Array(await f.arrayBuffer());
        let bin = "";
        for (let i = 0; i < u8.length; i += 0x8000) bin += String.fromCharCode(...u8.subarray(i, i + 0x8000));
        const b64 = btoa(bin);
        localStorage.setItem("climate-report-logo", JSON.stringify({ name: f.name, b64, ext: /svg/i.test(f.type) ? "svg" : "png" }));
      } catch (_) { /* storage full or blocked: logo kept for this session only */ }
      try { if (RID) render(); } catch (_) { /* no EPW loaded yet */ }  // RID / render live in app.js
    });
    ready.then(restoreLogo).then((n) => { if (n) name.textContent = n; });
  }

  window.LOCAL_API = LOCAL_API;
  window.IS_STATIC_BUILD = true;
  document.addEventListener("DOMContentLoaded", addLogoPicker);
})();
