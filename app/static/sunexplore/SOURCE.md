# SunExplore (vendored)

Copied from https://github.com/JuliaGGoenaga/SunExplore at commit 98da63a (2026-10-02).

Local changes (marked `climate-report:` in the code):
- `?embed=1` hides SunExplore's own top bar when shown inside the climate-report tab.
- `?epw=<url>&name=<file>&minT=<°C>` loads an EPW from the climate-report server on start,
  and `window.postMessage({type: "load-epw", url, name, minT})` loads a new one without reloading.
- The page layout was rebuilt to match the climate analysis tab (side panel on the left with the same
  stylesheet `../style.css`, chart and 3D model on the right); element ids are unchanged, so `app.js`
  works as upstream. Chart and 3D colours use the climate-report palette.
- Vertical fin side accepts "both" (one fin on each side of the window) in the chart, the 3D view and the form
  (also pushed upstream to SunExplore).
