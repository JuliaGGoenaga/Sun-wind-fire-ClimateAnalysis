"""Layout loading, user-editable settings and label translations."""
from __future__ import annotations

import copy
import json
import os

from .fonts import default_font

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAYOUT_PATH = os.path.join(ROOT, "layout", "a3_climate.json")


def load_layout(path: str = LAYOUT_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def logo_path() -> str | None:
    for name in ("idom_logo.svg", "idom_logo.png"):
        p = os.path.join(ROOT, "assets", name)
        if os.path.exists(p):
            return p
    return None


LABELS = {
    "en": {
        "temperature_title": "TEMPERATURE AND RADIATION ANALYSIS",
        "sun_title": "SUN ANALYSIS",
        "ventilation_title": "NATURAL VENTILATION AND HUMIDITY",
        "shading_title": "SOLAR PROTECTION ANALYSIS",
        "wind_title": "WIND ANALYSIS",
        "seasonal_wind_title": "SEASONAL WIND ANALYSIS",
        "nv_title": "NATURAL VENTILATION",
        "humidity_title": "HUMIDITY",
        "humidity_labels": ["Humidity Ratio (g/kg)", "Enthalpy (kJ/kg)", "Relative Humidity (%)"],
        "dbt_title": "DRY BULB TEMPERATURE",
        "month_upper": ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST",
                        "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"],
        "quarters": ["January - March", "April - June", "July - September", "October - December"],
        "day": "DAY ({a}:00 - {b}:00)",
        "night": "NIGHT ({b}:00 - {a}:00)",
        "freq_lines": "Frequency lines: {n} hours",
        "wind_speed": "WIND SPEED",
        "feeling": ["FEELING OF", "TEMPERATURE", "REDUCTION"],
        "wind_dir_label": "Wind from {name} ({a}° - {b}°) · {p}% of hours",
        "sector_names": ["NORTH", "EAST", "SOUTH", "WEST"],
        "degrees": "degrees",
        "facades": {"0": "NORTH FAÇADE", "90": "EAST FAÇADE", "180": "SOUTH FAÇADE", "270": "WEST FAÇADE"},
        "overhang": "Overhang", "fins": "Vertical fins", "none": "none",
        "coverage": "Blocks {p}% of {n} hot sunlit hours",
        "facade_generic": "FAÇADE",
        "sides": {"right": "right", "left": "left", "both": "both sides"},
        "dbt_legend": "Dry Bulb Temperature (ºC)",
        "method_texts": {
            "ventilation_text": "NATURAL VENTILATION AND HUMIDITY\n\nThe relative humidity of the site and its variation throughout the seasons are studied.\n\nThe natural ventilation chart shows the hours in which the dry bulb temperature lies between {nv_min} and {nv_max}ºC.",
            "wind_text": "WIND ANALYSIS\n\nWind patterns are studied from the hourly data of the weather file, considering direction and speed for each quarter of the year and for the whole year.\n\nThe hourly charts show, for each sector of origin, when the wind blows from it. The table relates air speed to the reduction in perceived temperature.",
            "seasonal_wind_text": "WIND ANALYSIS\n\nWind patterns are studied considering their direction and speed according to the season and the time of day (day {day_a}:00 - {day_b}:00, night {day_b}:00 - {day_a}:00).",
            "shading_text": "SUN SHADING ELEMENTS\n\nThe need for solar protection is studied for each orientation in order to define the shading elements of each opening.\n\nTo do so, the need to block direct radiation is determined for the moments when the temperature is above {sun_t}º. Each chart shows the fixed shadow mask of a basic shading element (overhang and vertical fins) and the share of those hours it blocks.",
        },

        "sheet_names": {"temperature": "Temperature & radiation", "ventilation": "Natural ventilation & humidity",
                        "sun": "Sun analysis", "shading": "Solar protection", "wind": "Wind",
                        "seasonal_wind": "Seasonal wind"},

        "header_right": "{city} - Climate analysis",
        "comfort_title": "COMFORT ANALYSIS",
        "condition": "condition",
        "utci": ["Extreme Heat", "Very Strong Heat", "Strong Heat", "Moderate Heat", "Slight Heat",
                 "No Thermal Stress", "Slight Cold", "Moderate Cold", "Strong Cold",
                 "Very Strong Cold", "Extreme Cold"],
        "monthly_title": "DRY BULB TEMPERATURE AND GLOBAL HORIZONTAL RADIATION",
        "monthly_subtitle": "(Monthly averages)",
        "legend_dbt": "DRY BULB TEMPERATURE",
        "legend_ghr": "GLOBAL HORIZONTAL RADIATION",
        "axis_temp": "Temperature (C)",
        "axis_rad": "Radiation (Wh/m2)",
        "cooling_title": "COOLING _ Temperature > {t}ºC",
        "heating_title": "HEATING _ Temperature < {t}ºC",
        "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "month_names": ["january", "february", "march", "april", "may", "june", "july",
                        "august", "september", "october", "november", "december"],
        "summer_solstice": "SUMMER SOLSTICE",
        "equinox": "SPRING AND AUTUMN EQUINOX",
        "winter_solstice": "WINTER SOLSTICE",
        "equinox_dates": "(21 march and 21 september)",
        "seasons": ["WINTER", "SPRING", "SUMMER", "AUTUMN"],
        "season_filter": "{season} (T > {t}ºC)",
        "hours": ["12 AM", "6 AM", "12 PM", "6 PM", "12 AM"],
        "hours3": ["12 AM", "3 AM", "6 AM", "9 AM", "12 PM", "3 PM", "6 PM", "9 PM", "12 AM"],
    },
    "es": {
        "temperature_title": "ANÁLISIS DE TEMPERATURA Y RADIACIÓN",
        "sun_title": "ANÁLISIS SOLAR",
        "ventilation_title": "VENTILACIÓN NATURAL Y HUMEDAD",
        "shading_title": "ANÁLISIS DE PROTECCIÓN SOLAR",
        "wind_title": "ANÁLISIS DE VIENTO",
        "seasonal_wind_title": "ANÁLISIS ESTACIONAL DE VIENTO",
        "nv_title": "VENTILACIÓN NATURAL",
        "humidity_title": "HUMEDAD",
        "humidity_labels": ["Humedad específica (g/kg)", "Entalpía (kJ/kg)", "Humedad relativa (%)"],
        "dbt_title": "TEMPERATURA DE BULBO SECO",
        "month_upper": ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO",
                        "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"],
        "quarters": ["Enero - Marzo", "Abril - Junio", "Julio - Septiembre", "Octubre - Diciembre"],
        "day": "DÍA ({a}:00 - {b}:00)",
        "night": "NOCHE ({b}:00 - {a}:00)",
        "freq_lines": "Líneas de frecuencia: {n} horas",
        "wind_speed": "VELOCIDAD DEL VIENTO",
        "feeling": ["REDUCCIÓN DE", "TEMPERATURA", "PERCIBIDA"],
        "wind_dir_label": "Viento del {name} ({a}° - {b}°) · {p}% de las horas",
        "sector_names": ["NORTE", "ESTE", "SUR", "OESTE"],
        "degrees": "grados",
        "facades": {"0": "FACHADA NORTE", "90": "FACHADA ESTE", "180": "FACHADA SUR", "270": "FACHADA OESTE"},
        "overhang": "Voladizo", "fins": "Lamas verticales", "none": "sin protección",
        "coverage": "Bloquea el {p}% de {n} horas de sol calurosas",
        "facade_generic": "FACHADA",
        "sides": {"right": "derecha", "left": "izquierda", "both": "ambos lados"},
        "dbt_legend": "Temperatura de bulbo seco (ºC)",
        "method_texts": {
            "ventilation_text": "HUMEDAD Y VENTILACIÓN NATURAL\n\nSe estudia la humedad relativa de la zona y su oscilación dependiendo de la estación del año.\n\nSe observa en el gráfico las horas en las que la temperatura de bulbo seco se sitúa entre {nv_min}-{nv_max}ºC.",
            "wind_text": "ANÁLISIS DE VIENTO\n\nSe estudian los patrones de viento a partir de los datos horarios del archivo climático, considerando su dirección y velocidad por trimestre y en el conjunto del año.\n\nLos gráficos horarios muestran en qué momentos sopla el viento desde cada sector. La tabla relaciona la velocidad del aire con la reducción de la temperatura percibida.",
            "seasonal_wind_text": "ANÁLISIS DE VIENTO\n\nSe estudian los patrones de viento, considerando su dirección y velocidad según la estación y la franja horaria (día {day_a}:00 - {day_b}:00, noche {day_b}:00 - {day_a}:00).",
            "shading_text": "ELEMENTOS DE PROTECCIÓN SOLAR\n\nSe realiza un estudio de la necesidad de protección solar en cada orientación con el objetivo de definir los elementos de protección en cada hueco.\n\nPara ello, se determina la necesidad de proteger de la radiación directa en los momentos en los que la temperatura es mayor a {sun_t}º. Cada carta muestra la máscara de sombras fija de un elemento básico de protección (voladizo y lamas verticales) y el porcentaje de esas horas que bloquea.",
        },

        "sheet_names": {"temperature": "Temperatura y radiación", "ventilation": "Ventilación natural y humedad",
                        "sun": "Análisis solar", "shading": "Protección solar", "wind": "Viento",
                        "seasonal_wind": "Viento estacional"},

        "header_right": "{city} - Análisis climático",
        "comfort_title": "ANÁLISIS DE CONFORT",
        "condition": "condición",
        "utci": ["Calor extremo", "Calor muy fuerte", "Calor fuerte", "Calor moderado", "Calor ligero",
                 "Sin estrés térmico", "Frío ligero", "Frío moderado", "Frío fuerte",
                 "Frío muy fuerte", "Frío extremo"],
        "monthly_title": "TEMPERATURA DE BULBO SECO Y RADIACIÓN GLOBAL HORIZONTAL",
        "monthly_subtitle": "(Medias mensuales)",
        "legend_dbt": "TEMPERATURA DE BULBO SECO",
        "legend_ghr": "RADIACIÓN GLOBAL HORIZONTAL",
        "axis_temp": "Temperatura (C)",
        "axis_rad": "Radiación (Wh/m2)",
        "cooling_title": "REFRIGERACIÓN _ Temperatura > {t}ºC",
        "heating_title": "CALEFACCIÓN _ Temperatura < {t}ºC",
        "months": ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"],
        "month_names": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                        "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
        "summer_solstice": "SOLSTICIO DE VERANO",
        "equinox": "EQUINOCCIO DE PRIMAVERA Y OTOÑO",
        "winter_solstice": "SOLSTICIO DE INVIERNO",
        "equinox_dates": "(21 marzo y 21 septiembre)",
        "seasons": ["INVIERNO", "PRIMAVERA", "VERANO", "OTOÑO"],
        "season_filter": "{season} (T > {t}ºC)",
        "hours": ["0 h", "6 h", "12 h", "18 h", "24 h"],
        "hours3": ["0 h", "3 h", "6 h", "9 h", "12 h", "15 h", "18 h", "21 h", "24 h"],
    },
}


SHEETS = ["temperature", "ventilation", "sun", "shading", "wind", "seasonal_wind"]

DEFAULT_SETTINGS = {
    "language": "en",
    "font": None,                 # None -> fonts.default_font()
    "sheets": None,               # None -> all, in SHEETS order
    "header_right": None,         # None -> "{city} - Climate analysis"
    "footer_text": "",
    "city": None,                 # None -> taken from the EPW
    "cooling_threshold": 26.0,
    "heating_threshold": 19.0,
    "sun_threshold": 24.0,
    "nv_min": 10.0,
    "nv_max": 24.0,
    "utci_sun_exposed": True,
    "shading_devices": None,      # None -> layout shading.masks.devices; else list of 4 dicts
    **{f"{k}_title": None for k in SHEETS},  # None -> translated default
}
LEGACY = {"page1_title": "temperature_title", "page2_title": "sun_title"}


def resolve(settings: dict | None, city_from_epw: str) -> dict:
    s = copy.deepcopy(DEFAULT_SETTINGS)
    for k, v in (settings or {}).items():
        k = LEGACY.get(k, k)
        if k in s and v not in (None, ""):
            s[k] = v
    lab = LABELS.get(s["language"], LABELS["en"])
    s["font"] = s["font"] or default_font()
    s["city"] = s["city"] or city_from_epw
    for k in SHEETS:
        s[f"{k}_title"] = s[f"{k}_title"] or lab[f"{k}_title"]
    sheets = s["sheets"]
    if isinstance(sheets, str):
        sheets = [x.strip() for x in sheets.split(",")]
    s["sheets"] = [k for k in SHEETS if not sheets or k in sheets] or list(SHEETS)
    s["header_right"] = (s["header_right"] or lab["header_right"]).replace("{city}", s["city"])
    for k in ("cooling_threshold", "heating_threshold", "sun_threshold", "nv_min", "nv_max"):
        s[k] = float(s[k])
    s["utci_sun_exposed"] = bool(s["utci_sun_exposed"]) if not isinstance(s["utci_sun_exposed"], str) \
        else s["utci_sun_exposed"].lower() in ("1", "true", "yes", "on")
    return s


def fmt_t(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


FIXED_TEXT_KEYS = ["ventilation_text", "wind_text", "seasonal_wind_text", "shading_text"]
LLM_TEXT_KEYS = ["temperature_text", "sun_text"]


def method_text(key: str, s: dict, layout: dict) -> str:
    """Fixed explanatory text (same for every EPW) with the user's thresholds filled in."""
    a, b = layout["seasonal_wind"]["day_hours"]
    return LABELS[s["language"]]["method_texts"][key].format(
        nv_min=fmt_t(s["nv_min"]), nv_max=fmt_t(s["nv_max"]), sun_t=fmt_t(s["sun_threshold"]),
        day_a=a, day_b=b)
