/* Climate report — Python (Pyodide) running in a Web Worker, so the page never freezes.
   Messages in:  {id, fn, args}   fn = a function of report/web.py, or "writeEpw" / "writeLogo"
   Messages out: {id, result} | {id, error} | {progress: "text"} */
const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.27.2/full/";
importScripts(PYODIDE + "pyodide.js");

const APP_DIR = "/home/pyodide/app";
let web = null;

const ready = (async () => {
  postMessage({ progress: "Cargando Python en el navegador…" });
  const py = await loadPyodide({ indexURL: PYODIDE });
  await py.loadPackage("micropip");
  postMessage({ progress: "Instalando ladybug…" });
  await py.pyimport("micropip").install([
    "ladybug-geometry==1.35.7", "ladybug-core==0.45.0", "ladybug-comfort==0.19.15",
  ]);
  postMessage({ progress: "Cargando el generador de láminas…" });
  const zip = await (await fetch("./py.zip", { cache: "no-cache" })).arrayBuffer();
  py.FS.mkdirTree(APP_DIR);
  py.unpackArchive(zip, "zip", { extractDir: APP_DIR });
  py.FS.mkdirTree(APP_DIR + "/assets");
  py.runPython(`import sys; sys.path.insert(0, "${APP_DIR}")`);
  web = py.pyimport("report.web");
  self.py = py;
  return py;
})();

onmessage = async (event) => {
  const { id, fn, args = [] } = event.data;
  try {
    const py = await ready;
    let result;
    if (fn === "ping") {
      result = "ok";
    } else if (fn === "writeEpw") {
      py.FS.writeFile("/tmp/input.epw", args[0]);
      result = web.load_epw();
    } else if (fn === "writeLogo") {
      const [bytes, ext] = args;  // ext: "png" | "svg"
      for (const e of ["png", "svg"]) {
        try { py.FS.unlink(`${APP_DIR}/assets/idom_logo.${e}`); } catch (_) { /* not there */ }
      }
      if (bytes) py.FS.writeFile(`${APP_DIR}/assets/idom_logo.${ext}`, new Uint8Array(bytes));
      result = "ok";
    } else {
      result = web[fn](...args);
    }
    postMessage({ id, result });
  } catch (err) {
    postMessage({ id, error: String(err && err.message ? err.message : err) });
  }
};
