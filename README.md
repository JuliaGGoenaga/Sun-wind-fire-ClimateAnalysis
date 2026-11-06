# Climate report A3 (EPW → PDF / PPTX / SVG)

Genera las láminas A3 de análisis climático (formato IDOM) para cualquier archivo EPW del mundo.
Los gráficos se calculan con **ladybug** y son deterministas: mismo EPW + mismos ajustes = mismo
archivo, byte a byte. Los textos de temperatura y sol los redacta un **LLM local** (Ollama o
LM Studio) o se escriben / pegan a mano; el resto de láminas lleva un texto base fijo que explica el método.

## Instalación y uso

Requiere Python 3.10 o superior.

```bash
./run.sh            # macOS / Linux: crea .venv la primera vez, instala dependencias y arranca http://localhost:8000
```

En Windows, doble clic en `run.bat` (hace lo mismo y abre el navegador).

La web tiene dos pestañas que comparten el mismo EPW:

- **Análisis climático**: las láminas A3 y sus descargas (lo que se describe abajo).
- **SunExplore · carta solar**: el visualizador interactivo [SunExplore](https://github.com/JuliaGGoenaga/SunExplore)
  (carta solar con filtro de temperatura, protección horizontal / vertical y vista 3D de la ventana).
  Al subir un EPW en el análisis se carga también aquí, con el mismo umbral de temperatura; también se
  puede subir otro EPW directamente en esta pestaña. Su código está en `app/static/sunexplore/`
  (ver `SOURCE.md`); usa Plotly y three.js desde CDN, así que necesita conexión a Internet.

1. Sube el `.epw`.
2. Ajusta idioma, tipografía, encabezado, pie de página, umbrales y las láminas a incluir.
3. Protección solar: elige para cada fachada (N, S, E, O) sin protección, voladizo, lamas o ambos, con su ángulo.
4. Textos: «Generar con LLM» con Ollama (`:11434`), LM Studio (`:1234`) o **cualquier servicio compatible con
   OpenAI** (BionicGPT, vLLM, Jan, LocalAI…: URL del API, clave si la pide y nombre del modelo, que también se
   puede escribir a mano); recomendado `llama3.1:8b` o `gemma4`,
   o «Copiar prompt», pégalo en otro asistente y pega el JSON de respuesta, o escribe directamente.
5. Descarga **PDF** (vectorial, fuente embebida), **PPTX** (A3; cada gráfico es una imagen de 300 ppp y
   los textos, títulos, encabezado y pie son editables) o **SVG** (vectorial completo).

Sin webapp:

```bash
.venv/bin/python cli.py ciudad.epw --out out --texts textos.json --settings ajustes.json
```

### Versión web sin instalación (GitHub Pages, Python en el navegador)

La carpeta `docs/` es la misma web pero **sin servidor**: el código Python de `report/` se ejecuta en
el navegador con [Pyodide](https://pyodide.org) (en un *web worker*), y el PDF / PPTX / SVG se montan en
el propio navegador (jsPDF + svg2pdf, PptxGenJS, JSZip). Nada se sube a ningún servidor.

- **Publicar**: GitHub → *Settings → Pages → Deploy from a branch* → rama y carpeta `/docs`.
- **Reconstruir** `docs/` después de cambiar `report/`, `layout/` o `app/static/`:
  `python tools/build_web.py`.
- **Primera carga**: 2–5 s (descarga Python y ladybug; luego queda en caché del navegador).
- **Logo**: se sube desde la ventana del EPW (botón «Logo»); se recuerda en ese navegador.
- **Tipografías**: Arial, Verdana, Georgia, Tahoma, Trebuchet MS, Times New Roman, Courier New
  (`report/font_metrics/` guarda solo los anchos de los caracteres; el texto se dibuja con la fuente del
  ordenador). En el PDF del navegador se usan las fuentes estándar del PDF (Helvetica / Times / Courier).
- **LLM**: la web llama directamente al Ollama / LM Studio del ordenador de cada usuario. Hay que permitir
  la web una vez:
  - Ollama (Mac): `launchctl setenv OLLAMA_ORIGINS "https://juliaggoenaga.github.io"` y reiniciar Ollama
    (Windows: variable de entorno `OLLAMA_ORIGINS` con esa URL).
  - LM Studio: *Developer → Settings → Enable CORS*.
  Si no, queda el modo manual (copiar el prompt y pegar la respuesta).

### Archivos que no están en el repo

- **Logo**: copia el logo en `assets/idom_logo.svg` (vectorial, necesita `pip install svglib`) o
  `assets/idom_logo.png`. Sin logo, las láminas se generan igual, sin él.
- **EPW de prueba**: copia uno o varios `.epw` en `tests/fixtures/` para ejecutar `pytest`
  (si no hay ninguno, los tests se saltan).
- **Tipografías propias**: copia el `.ttf` *Regular* en `fonts/`.

## Láminas (se eligen en la web)

1. **Temperatura y radiación**: confort UTCI, bandas mensuales de temperatura + radiación global, mapas de refrigeración / calefacción. *Texto: LLM.*
2. **Ventilación natural y humedad**: horas con T entre 10–24 °C, humedad específica, entalpía y humedad relativa, y temperatura seca mes a mes. *Texto base fijo.*
3. **Análisis solar**: cartas estereográficas de solsticios / equinoccio con soles en amarillo, alzados y cartas por estación con T > 24 °C. *Texto: LLM.*
4. **Protección solar**: carta con las horas del día 21 de cada mes coloreadas por temperatura y 4 máscaras de sombras **fijas** (método [SunExplore](https://github.com/JuliaGGoenaga/SunExplore): mitad posterior, voladizo y lama vertical sobre ventana de 1,5 m), con el % de horas calurosas que bloquea cada una. Por defecto voladizo y lamas de 30°; se editan en la web o en `layout/a3_climate.json` → `shading.masks.devices`. *Texto base fijo.*
5. **Viento**: rosas trimestrales y anual (0–15 m/s), tabla velocidad / reducción de temperatura percibida y mapas horarios por sector N/E/S/O. *Texto base fijo.*
6. **Viento estacional**: rosas trimestrales completas, de día (8–18 h) y de noche. *Texto base fijo.*

## Textos con LLM

- Se hace **una llamada corta por texto** (temperatura, sol) con los datos ya interpretados en frases
  (clima dominante, meses más calurosos, meses de calefacción / refrigeración, radiación…), un guion por
  párrafo y un ejemplo de estilo **del mismo tipo de clima** (cálido → texto de referencia de Dallas;
  frío → equivalente para clima de calefacción).
- El modelo responde con párrafos de texto; el servidor fija el número de párrafos, recorta por frases
  completas al límite de palabras de cada caja y comprueba el idioma (si no coincide, repite una vez).
- Temperatura 0 y semilla fija; el resultado se guarda en caché por EPW + ajustes + modelo.

## Estructura

```
layout/a3_climate.json   posiciones (mm), colores, paletas, tamaños de letra, límites de palabras, máscaras por defecto
report/climate.py        cálculos con ladybug (EPW, UTCI, Sunpath, viento, psicrometría, datos para el LLM)
report/charts/           heatmap · monthly · sunpath · wind · shading · common (leyendas)
report/pages.py          compone las láminas a partir del layout
report/primitives.py     primitivas de dibujo en mm (una sola geometría para todos los formatos)
report/writers/          svg.py · pdf.py (reportlab) · pptx.py (python-pptx)
report/text/             prompts.py (datos en frases + guion + ejemplo) · llm.py (Ollama / LM Studio)
report/fonts.py          fuentes TTF del sistema o de fonts/ + medición para cortar líneas igual siempre
app/                     FastAPI + HTML/JS sin dependencias de build (app/static/sunexplore = pestaña SunExplore)
cli.py                   generación por línea de comandos
report/web.py            funciones para la versión del navegador (Pyodide)
web/                     backend.js (responde a /api/... en el navegador) · worker.js (Pyodide)
tools/build_web.py       genera docs/ (GitHub Pages) · tools/make_font_metrics.py (tablas de anchos)
docs/                    versión estática generada (no editar a mano)
tests/                   test de determinismo y tamaño A3
```
