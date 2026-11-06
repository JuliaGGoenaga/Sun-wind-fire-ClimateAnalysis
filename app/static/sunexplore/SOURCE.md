# SunExplore (vendored)

Copied from https://github.com/JuliaGGoenaga/SunExplore at commit 98da63a (2026-10-02).

Local changes (marked `climate-report:` in the code):
- `?embed=1` hides SunExplore's own top bar when shown inside the climate-report tab.
- `?epw=<url>&name=<file>&minT=<°C>` loads an EPW from the climate-report server on start,
  and `window.postMessage({type: "load-epw", url, name, minT})` loads a new one without reloading.
