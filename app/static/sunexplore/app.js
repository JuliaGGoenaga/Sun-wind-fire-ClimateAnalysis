const MONTHS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
const REFERENCE_WINDOW_DIMENSION = 1.5;

function parseCsvRow(line) {
  const values = [];
  let value = "";
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const character = line[index];
    if (character === '"') {
      if (quoted && line[index + 1] === '"') {
        value += '"';
        index += 1;
      } else {
        quoted = !quoted;
      }
    } else if (character === "," && !quoted) {
      values.push(value);
      value = "";
    } else {
      value += character;
    }
  }
  values.push(value);
  return values;
}

function parseEpwText(text) {
  const lines = text.replace(/^\uFEFF/, "").split(/\r?\n/);
  const locationRow = lines.slice(0, 10).map(parseCsvRow).find(row => row[0]?.trim().toUpperCase() === "LOCATION");
  if (!locationRow || locationRow.length < 10) {
    throw new Error("No se encuentra la cabecera LOCATION del archivo EPW.");
  }

  const latitude = Number(locationRow[6]);
  const longitude = Number(locationRow[7]);
  const timezone = Number(locationRow[8]);
  if (![latitude, longitude, timezone].every(Number.isFinite) || Math.abs(latitude) > 90 || Math.abs(longitude) > 180) {
    throw new Error("La ubicación del archivo EPW no contiene coordenadas válidas.");
  }

  const records = [];
  for (const line of lines) {
    if (!/^\s*\d{4},/.test(line)) continue;
    const row = parseCsvRow(line);
    if (row.length < 7) continue;
    const year = Number(row[0]);
    const month = Number(row[1]);
    const day = Number(row[2]);
    const hour = Number(row[3]);
    const temperature = Number(row[6]);
    if (!Number.isInteger(month) || month < 1 || month > 12 || !Number.isInteger(day) || day < 1 || day > 31 || !Number.isInteger(hour) || hour < 1 || hour > 24) continue;
    if (!Number.isFinite(temperature) || temperature < -70 || temperature > 70) continue;
    const position = solarPosition(year, month, day, hour - 0.5, latitude, longitude, timezone);
    if (position.elevation > 0) records.push({ year, month, day, hour, temperature, ...position });
  }

  if (!records.length) throw new Error("No hay horas de sol con temperatura válida en este archivo.");
  const city = locationRow[1]?.trim() || "Ubicación sin nombre";
  const country = locationRow[3]?.trim();
  return { city, country, latitude, longitude, timezone, records };
}

function solarPosition(year, month, day, localHour, latitude, longitude, timezone) {
  const date = new Date(Date.UTC(year, month - 1, day));
  const dayOfYear = Math.floor((date - Date.UTC(date.getUTCFullYear(), 0, 0)) / 86400000);
  const yearLength = new Date(Date.UTC(year + 1, 0, 1) - Date.UTC(year, 0, 1)).getTime() / 86400000;
  const gamma = 2 * Math.PI / yearLength * (dayOfYear - 1 + (localHour - 12) / 24);
  const equationOfTime = 229.18 * (0.000075 + 0.001868 * Math.cos(gamma) - 0.032077 * Math.sin(gamma) - 0.014615 * Math.cos(2 * gamma) - 0.040849 * Math.sin(2 * gamma));
  const declination = 0.006918 - 0.399912 * Math.cos(gamma) + 0.070257 * Math.sin(gamma) - 0.006758 * Math.cos(2 * gamma) + 0.000907 * Math.sin(2 * gamma) - 0.002697 * Math.cos(3 * gamma) + 0.00148 * Math.sin(3 * gamma);
  const solarMinutes = localHour * 60 + equationOfTime + 4 * longitude - 60 * timezone;
  const hourAngle = (solarMinutes / 4 - 180) * Math.PI / 180;
  const latitudeRadians = latitude * Math.PI / 180;
  const cosineZenith = Math.max(-1, Math.min(1, Math.sin(latitudeRadians) * Math.sin(declination) + Math.cos(latitudeRadians) * Math.cos(declination) * Math.cos(hourAngle)));
  const elevation = 90 - Math.acos(cosineZenith) * 180 / Math.PI;
  const azimuth = (Math.atan2(Math.sin(hourAngle), Math.cos(hourAngle) * Math.sin(latitudeRadians) - Math.tan(declination) * Math.cos(latitudeRadians)) * 180 / Math.PI + 180 + 360) % 360;
  return { azimuth, elevation };
}

function visibleRecords(climate, threshold) {
  if (threshold === "" || threshold === null || threshold === undefined || !Number.isFinite(Number(threshold))) return climate.records;
  return climate.records.filter(record => record.temperature >= Number(threshold));
}

function horizontalShadePolygon(orientation, overhang, windowHeight) {
  if (overhang <= 0) return null;
  const theta = [];
  const radius = [];
  for (let offset = -90; offset <= 90; offset += 1) {
    const cosine = Math.max(0, Math.cos(offset * Math.PI / 180));
    const minimumElevation = Math.atan2(windowHeight * cosine, overhang) * 180 / Math.PI;
    theta.push((orientation + offset + 360) % 360);
    radius.push(90 - minimumElevation);
  }
  theta.push((orientation + 90) % 360, (orientation + 270) % 360);
  radius.push(0, 0);
  return { theta, r: radius };
}

function verticalShadePolygon(orientation, angle, side) {
  const center = (orientation + 180) % 360;
  const base = center + (side === "left" ? 90 : -90);
  const start = side === "left" ? base : base - angle;
  const end = side === "left" ? base + angle : base;
  const arc = Array.from({ length: 61 }, (_, index) => start + (end - start) * index / 60);
  return {
    theta: [start, ...arc, end].map(value => (value % 360 + 360) % 360),
    r: [0, ...Array(61).fill(90), 0]
  };
}

function oppositeOrientationPolygon(orientation) {
  const start = (orientation + 90) % 360;
  const end = (orientation + 270) % 360;
  const arc = Array.from({ length: 181 }, (_, index) => start + index);
  return {
    theta: [start, ...arc, end].map(value => (value % 360 + 360) % 360),
    r: [0, ...Array(181).fill(90), 0]
  };
}

function makeShadeTrace(polygon) {
  return {
    type: "scatterpolar",
    mode: "lines",
    theta: polygon.theta,
    r: polygon.r,
    fill: "toself",
    fillcolor: "rgba(42, 69, 165, 0.22)",
    line: { color: "rgba(42, 69, 165, 0.45)", width: 1 },
    hoverinfo: "skip",
    showlegend: false
  };
}

function makeChartTraces(climate, records, orientation, shadeOptions = {}) {
  const traces = [];
  const shadeTraces = [];
  for (let month = 1; month <= 12; month += 1) {
    const day21 = climate.records.filter(record => record.month === month && record.day === 21);
    if (day21.length) {
      traces.push({
        type: "scatterpolar",
        mode: "lines",
        name: MONTHS[month - 1],
        theta: day21.map(record => record.azimuth),
        r: day21.map(record => 90 - record.elevation),
        line: { color: "rgba(29, 36, 51, 0.30)", width: 1 },
        hoverinfo: "skip",
        showlegend: false
      });
    }
  }

  shadeTraces.push(makeShadeTrace(oppositeOrientationPolygon(orientation)));

  if (shadeOptions.horizontalEnabled) {
    const overhang = Math.max(Number(shadeOptions.horizontalLength) || 0, 0);
    const polygon = horizontalShadePolygon(orientation, overhang, REFERENCE_WINDOW_DIMENSION);
    if (polygon) shadeTraces.push(makeShadeTrace(polygon));
  }
  if (shadeOptions.verticalEnabled) {
    const angle = Math.atan(Math.max(Number(shadeOptions.verticalLength) || 0, 0) / REFERENCE_WINDOW_DIMENSION) * 180 / Math.PI;
    const chartSide = shadeOptions.verticalSide === "left" ? "right" : "left";
    if (angle > 0) shadeTraces.push(makeShadeTrace(verticalShadePolygon(orientation, angle, chartSide)));
  }

  traces.push({
    type: "scatterpolar",
    mode: "markers",
    name: "Horas de sol",
    theta: records.map(record => record.azimuth),
    r: records.map(record => 90 - record.elevation),
    customdata: records.map(record => [record.elevation, record.temperature, record.month, record.day, record.hour]),
    marker: {
      size: 5,
      opacity: 0.76,
      color: records.map(record => record.temperature),
      colorscale: [[0, "#4b6ba9"], [0.25, "#aac8f7"], [0.45, "#f5ef67"], [0.7, "#ef9c15"], [1, "#ea2600"]],
      cmin: -10,
      cmax: 35,
      colorbar: { title: { text: "°C", side: "right" }, thickness: 11, len: 0.72, outlinewidth: 0 },
      showscale: true
    },
    hovertemplate: "Azimut %{theta:.1f}°<br>Altura %{customdata[0]:.1f}°<br>Temperatura %{customdata[1]:.1f}°C<br>%{customdata[2]:02d}/%{customdata[3]:02d} · hora %{customdata[4]}<extra></extra>"
  });

  traces.push(...shadeTraces);

  traces.push({
    type: "scatterpolar",
    mode: "lines",
    name: "Orientación",
    theta: [orientation, orientation],
    r: [0, 90],
    line: { color: "#2a45a5", width: 2, dash: "dot" },
    hovertemplate: `Orientación ${orientation}°<extra></extra>`,
    showlegend: false
  });
  return traces;
}

function chartLayout() {
  return {
    margin: { t: 22, r: 50, b: 24, l: 50 },
    paper_bgcolor: "#ffffff",
    plot_bgcolor: "#ffffff",
    font: { family: "system-ui, -apple-system, Segoe UI, sans-serif", color: "#6b7385", size: 11 },
    polar: {
      bgcolor: "#ffffff",
      radialaxis: { range: [0, 90], tickvals: [0, 15, 30, 45, 60, 75, 90], ticktext: ["90°", "75°", "60°", "45°", "30°", "15°", "0°"], gridcolor: "#e6e9f0", linecolor: "#dfe3eb", tickfont: { size: 9 } },
      angularaxis: { direction: "clockwise", rotation: 90, tickvals: [0, 90, 180, 270], ticktext: ["N · 0°", "E · 90°", "S · 180°", "O · 270°"], gridcolor: "#e6e9f0", linecolor: "#dfe3eb", tickfont: { size: 10 } }
    },
    showlegend: false
  };
}

function csvContent(records) {
  const rows = [["fecha", "hora_epw", "azimut_deg", "altura_deg", "temperatura_seca_c"]];
  for (const record of records) {
    rows.push([`${record.year}-${String(record.month).padStart(2, "0")}-${String(record.day).padStart(2, "0")}`, record.hour, record.azimuth.toFixed(2), record.elevation.toFixed(2), record.temperature]);
  }
  return rows.map(row => row.join(",")).join("\r\n");
}

function initApp() {
  const fileInput = document.getElementById("epw-file");
  const filePicker = document.querySelector(".file-picker");
  const orientationInput = document.getElementById("orientation");
  const temperatureInput = document.getElementById("min-temperature");
  const status = document.getElementById("status");
  const climateLocation = document.getElementById("location");
  const downloadCsv = document.getElementById("download-csv");
  const downloadPng = document.getElementById("download-png");
  const shadeInputs = ["horizontal-enabled", "horizontal-length", "window-height", "vertical-enabled", "vertical-length", "window-width", "vertical-side"].map(id => document.getElementById(id));
  let climate = null;
  let currentRecords = [];

  const updateShadePreview = () => {
    const width = Math.max(Number(document.getElementById("window-width").value) || REFERENCE_WINDOW_DIMENSION, 0.1);
    const height = Math.max(Number(document.getElementById("window-height").value) || REFERENCE_WINDOW_DIMENSION, 0.1);
    const horizontalLength = Math.max(Number(document.getElementById("horizontal-length").value) || 0, 0);
    const verticalLength = Math.max(Number(document.getElementById("vertical-length").value) || 0, 0);
    window.sunShade3d?.update({
      width,
      height,
      horizontalEnabled: document.getElementById("horizontal-enabled").checked,
      horizontalLength,
      verticalEnabled: document.getElementById("vertical-enabled").checked,
      verticalLength,
      verticalSide: document.getElementById("vertical-side").value
    });
    document.getElementById("horizontal-length-value").textContent = horizontalLength.toFixed(1);
    document.getElementById("vertical-length-value").textContent = verticalLength.toFixed(1);
    document.getElementById("preview-dimensions").textContent = `${width.toFixed(1)} × ${height.toFixed(1)} m`;
  };

  const setStatus = (message, isError = false) => {
    status.textContent = message;
    status.classList.toggle("is-error", isError);
  };

  const render = () => {
    updateShadePreview();
    if (!climate) return;
    const orientation = (Number(orientationInput.value) % 360 + 360) % 360;
    const records = visibleRecords(climate, temperatureInput.value);
    currentRecords = records;
    const shadeOptions = {
      horizontalEnabled: document.getElementById("horizontal-enabled").checked,
      horizontalLength: document.getElementById("horizontal-length").value,
      verticalEnabled: document.getElementById("vertical-enabled").checked,
      verticalLength: document.getElementById("vertical-length").value,
      verticalSide: document.getElementById("vertical-side").value
    };
    Plotly.react("solar-chart", makeChartTraces(climate, records, orientation, shadeOptions), chartLayout(), { responsive: true, displaylogo: false, modeBarButtonsToRemove: ["lasso2d", "select2d"] });
    document.getElementById("record-count").textContent = `${records.length.toLocaleString("es-ES")} ${records.length === 1 ? "hora de sol" : "horas de sol"}`;
    downloadCsv.disabled = records.length === 0;
    downloadPng.disabled = records.length === 0;
    setStatus(records.length ? "Carta actualizada." : "No hay horas que cumplan ese umbral.", records.length === 0);
  };

  const loadFile = async file => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".epw")) {
      setStatus("Selecciona un archivo con extensión .epw.", true);
      return;
    }
    setStatus("Leyendo archivo climático…");
    try {
      const parsed = parseEpwText(await file.text());
      climate = parsed;
      orientationInput.disabled = false;
      temperatureInput.disabled = false;
      shadeInputs.forEach(input => { input.disabled = false; });
      document.getElementById("file-name").textContent = file.name;
      document.getElementById("file-hint").textContent = `${parsed.records.length.toLocaleString("es-ES")} horas solares válidas`;
      document.getElementById("location-name").textContent = `${parsed.city}${parsed.country ? `, ${parsed.country}` : ""} · ${parsed.latitude.toFixed(2)}°, ${parsed.longitude.toFixed(2)}°`;
      climateLocation.classList.add("is-loaded");
      document.getElementById("chart-title").textContent = `Carta solar · ${parsed.city}`;
      render();
    } catch (error) {
      climate = null;
      orientationInput.disabled = true;
      temperatureInput.disabled = true;
      setStatus(error.message || "No se pudo leer el archivo EPW.", true);
    }
  };

  // climate-report: load an EPW served by the climate-report app (URL params or postMessage)
  const loadFromUrl = async (url, name, minT) => {
    if (!url) return;
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error(response.statusText);
      if (minT !== undefined && minT !== null && minT !== "") temperatureInput.value = minT;
      await loadFile(new File([await response.blob()], name || "climate.epw"));
    } catch (error) {
      setStatus(`No se pudo cargar el EPW del análisis: ${error.message}`, true);
    }
  };
  const params = new URLSearchParams(window.location.search);
  if (params.get("embed") === "1") document.body.classList.add("is-embedded");
  if (params.get("epw")) loadFromUrl(params.get("epw"), params.get("name"), params.get("minT"));
  window.addEventListener("message", event => {
    if (event.origin !== window.location.origin || !event.data || event.data.type !== "load-epw") return;
    loadFromUrl(event.data.url, event.data.name, event.data.minT);
  });

  fileInput.addEventListener("change", event => loadFile(event.target.files[0]));
  orientationInput.addEventListener("input", render);
  temperatureInput.addEventListener("input", render);
  shadeInputs.forEach(input => input.addEventListener("input", render));
  document.getElementById("vertical-side").addEventListener("change", render);
  filePicker.addEventListener("dragover", event => { event.preventDefault(); filePicker.classList.add("is-dragging"); });
  filePicker.addEventListener("dragleave", () => filePicker.classList.remove("is-dragging"));
  filePicker.addEventListener("drop", event => {
    event.preventDefault();
    filePicker.classList.remove("is-dragging");
    loadFile(event.dataTransfer.files[0]);
  });
  downloadCsv.addEventListener("click", () => {
    const blob = new Blob(["\uFEFF", csvContent(currentRecords)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "carta-solar.csv";
    link.click();
    URL.revokeObjectURL(url);
  });
  downloadPng.addEventListener("click", () => Plotly.downloadImage("solar-chart", { format: "png", filename: "carta-solar", width: 1200, height: 900, scale: 2 }));
  updateShadePreview();
  Plotly.newPlot("solar-chart", [{ type: "scatterpolar", mode: "markers", theta: [], r: [] }], chartLayout(), { responsive: true, displayModeBar: false, staticPlot: true });
}

if (typeof document !== "undefined") initApp();
if (typeof module !== "undefined" && module.exports) module.exports = { parseEpwText, solarPosition, visibleRecords, csvContent };