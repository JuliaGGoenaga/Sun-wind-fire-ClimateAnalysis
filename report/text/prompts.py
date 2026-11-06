"""Fixed prompts. The model only writes prose; every number comes from ladybug.

Texts are requested as LISTS of paragraphs and then normalised by `fit_text`,
which enforces the paragraph structure and the word limit of each text box
(trimming whole sentences), so the sheet never overflows.
"""
from __future__ import annotations

import json
import re

from ..settings import load_layout

SYSTEM = {
    "en": ("You are a bioclimatic design consultant. You write short, factual texts for architects, in English, "
           "using only the data you are given."),
    "es": ("Eres un consultor de diseño bioclimático. Escribes textos breves y rigurosos para arquitectos, en "
           "español, usando solo los datos que te dan."),
}

LANG = {"en": "English", "es": "Spanish (Spain)"}


def system_prompt(language: str = "en") -> str:
    return SYSTEM.get(language, SYSTEM["en"])


_STOP = {
    "es": [" el ", " la ", " los ", " las ", " de ", " del ", " y ", " en ", " que ", " con ", " por ", " se ", " una ", " es "],
    "en": [" the ", " and ", " of ", " with ", " is ", " are ", " to ", " in ", " a ", " which ", " from ", " this "],
}


def detect_language(text: str) -> str:
    """Rough deterministic check (stop-word counts): 'es' or 'en'."""
    t = " " + " ".join(re.findall(r"[a-záéíóúñü]+", (text or "").lower())) + " "
    es = sum(t.count(w) for w in _STOP["es"])
    en = sum(t.count(w) for w in _STOP["en"])
    return "es" if es > en else "en"


def language_ok(texts: dict, language: str) -> bool:
    body = " ".join(v for v in texts.values() if v)
    return not body.strip() or detect_language(body) == ("es" if language == "es" else "en")


def strict_suffix(language: str) -> str:
    if language == "es":
        return ("\n\nIMPORTANTE: la respuesta anterior estaba en inglés. Escribe TODOS los párrafos en "
                "ESPAÑOL. No uses ni una frase en inglés.")
    return "\n\nIMPORTANT: write ALL paragraphs in ENGLISH."


def limits(layout: dict | None = None) -> dict:
    L = layout or load_layout()
    return {
        f"{k}_text": {"max_words": L[k]["text"]["max_words"], "paragraphs": L[k]["text"]["paragraphs"]}
        for k in L["sheet_order"]
    }


# Reference texts. "cooling" = the user's own Dallas sheet (complete). "heating" = same style for a
# heating-dominated climate. The example shown to the model matches the climate of the EPW, so the
# model never copies cooling conclusions into a cold climate (or the opposite).
EXAMPLES = {
    "cooling": {
        "en": {
            "temperature_paragraphs": [
                "Dallas has a humid subtropical climate characterized by hot summers and mild winters. Average daytime "
                "temperatures exceed 35°C during July and August, while winter temperatures generally remain between "
                "14 and 16°C.",
                "As a result, cooling demand clearly dominates the annual energy balance, particularly from May through "
                "September, when outdoor conditions frequently exceed thermal comfort thresholds.",
                "Heating requirements are comparatively moderate and are mainly concentrated between December and February.",
                "From a bioclimatic perspective, the primary design challenge in Dallas is mitigating excessive solar heat "
                "gains and reducing summer overheating, while still taking advantage of beneficial solar exposure during "
                "the cooler months to offset heating needs.",
            ],
            "sun_paragraphs": [
                "Dallas benefits from high levels of solar radiation throughout the year, with particularly intense solar "
                "exposure during spring, summer and early autumn. The sun-path diagram filtered for temperatures above "
                "{t}°C highlights that much of the incident solar radiation coincides with periods when solar gains "
                "become undesirable for indoor comfort.",
                "- East and west façades are the most critical orientations, receiving low-angle morning and afternoon sun "
                "that can significantly increase overheating risk and glare.",
                "- South-facing façades experience the highest annual solar exposure but can be effectively controlled "
                "with horizontal shading devices that block the high summer sun while allowing beneficial winter solar gains.",
                "- North façades receive limited direct solar radiation and are generally less sensitive to overheating.",
                "Consequently, vertical shading is recommended for east and west orientations, horizontal overhangs for "
                "south-facing façades, and a more selective approach for north orientations.",
            ],
        },
        "es": {
            "temperature_paragraphs": [
                "Dallas tiene un clima subtropical húmedo, caracterizado por veranos calurosos e inviernos suaves. Las "
                "temperaturas medias diurnas superan los 35°C en julio y agosto, mientras que en invierno se mantienen "
                "generalmente entre 14 y 16°C.",
                "Como consecuencia, la demanda de refrigeración domina claramente el balance energético anual, "
                "especialmente de mayo a septiembre, cuando las condiciones exteriores superan con frecuencia los "
                "umbrales de confort térmico.",
                "Las necesidades de calefacción son comparativamente moderadas y se concentran principalmente entre "
                "diciembre y febrero.",
                "Desde el punto de vista bioclimático, el principal reto de diseño en Dallas es mitigar las ganancias "
                "solares excesivas y reducir el sobrecalentamiento en verano, aprovechando a la vez la radiación solar "
                "beneficiosa en los meses más fríos para compensar la demanda de calefacción.",
            ],
            "sun_paragraphs": [
                "Dallas recibe niveles elevados de radiación solar durante todo el año, con una exposición especialmente "
                "intensa en primavera, verano y principios de otoño. La carta solar filtrada para temperaturas superiores "
                "a {t}°C muestra que gran parte de la radiación incidente coincide con periodos en los que las ganancias "
                "solares resultan indeseables para el confort interior.",
                "- Las fachadas este y oeste son las orientaciones más críticas: reciben sol de mañana y de tarde con poca "
                "altura, que puede aumentar notablemente el riesgo de sobrecalentamiento y deslumbramiento.",
                "- Las fachadas sur reciben la mayor exposición solar anual, pero se controlan eficazmente con elementos de "
                "sombra horizontales que bloquean el sol alto de verano y dejan pasar las ganancias solares de invierno.",
                "- Las fachadas norte reciben poca radiación solar directa y, en general, son menos sensibles al "
                "sobrecalentamiento.",
                "En consecuencia, se recomienda protección vertical en las orientaciones este y oeste, voladizos "
                "horizontales en las fachadas sur y un enfoque más selectivo en las orientaciones norte.",
            ],
        },
    },
    "heating": {
        "en": {
            "temperature_paragraphs": [
                "The city has a temperate oceanic climate with mild summers and cool, humid winters. Average daytime "
                "temperatures reach about 25°C in August, while winter maxima generally remain between 11 and 13°C.",
                "As a result, heating demand clearly dominates the annual energy balance, particularly from November "
                "through April, when outdoor temperatures stay below thermal comfort thresholds for most of the day.",
                "Cooling requirements are limited and occasional, and are mainly concentrated in a few hours of July "
                "and August.",
                "From a bioclimatic perspective, the primary design challenge is to maximise useful solar gains and "
                "reduce heat losses during the cold season, while preventing occasional overheating in summer.",
            ],
            "sun_paragraphs": [
                "The city receives moderate solar radiation, concentrated between spring and late summer, with low "
                "availability in winter. The sun-path diagram filtered for temperatures above {t}°C shows that only a "
                "limited number of hours combine strong sun and high temperatures, mostly on summer afternoons.",
                "- East and west façades receive low-angle sun that is useful on cold-season mornings but can cause "
                "glare and occasional overheating on summer afternoons.",
                "- South-facing façades are the main source of useful winter solar gains; small horizontal overhangs "
                "block the high summer sun without reducing winter radiation.",
                "- North façades receive almost no direct radiation and should prioritise insulation and controlled glazing.",
                "Consequently, solar gains should be maximised on the south façade with light horizontal protection, "
                "adjustable shading is recommended for east and west, and the north façade should limit heat losses.",
            ],
        },
        "es": {
            "temperature_paragraphs": [
                "La ciudad tiene un clima templado oceánico, con veranos suaves e inviernos frescos y húmedos. Las "
                "temperaturas medias diurnas alcanzan unos 25°C en agosto, mientras que las máximas de invierno se "
                "mantienen generalmente entre 11 y 13°C.",
                "Como consecuencia, la demanda de calefacción domina claramente el balance energético anual, "
                "especialmente de noviembre a abril, cuando las temperaturas exteriores se mantienen por debajo de los "
                "umbrales de confort durante la mayor parte del día.",
                "Las necesidades de refrigeración son limitadas y puntuales, y se concentran en unas pocas horas de "
                "julio y agosto.",
                "Desde el punto de vista bioclimático, el principal reto de diseño es maximizar las ganancias solares "
                "útiles y reducir las pérdidas de calor en la estación fría, evitando a la vez el sobrecalentamiento "
                "puntual en verano.",
            ],
            "sun_paragraphs": [
                "La ciudad recibe una radiación solar moderada, concentrada entre la primavera y el final del verano, "
                "con poca disponibilidad en invierno. La carta solar filtrada para temperaturas superiores a {t}°C "
                "muestra que solo un número limitado de horas combina sol intenso y temperaturas altas, sobre todo en "
                "las tardes de verano.",
                "- Las fachadas este y oeste reciben sol con poca altura, útil en las mañanas de la estación fría pero "
                "que puede provocar deslumbramiento y sobrecalentamiento puntual en las tardes de verano.",
                "- Las fachadas sur son la principal fuente de ganancias solares útiles en invierno; pequeños voladizos "
                "horizontales bloquean el sol alto de verano sin reducir la radiación invernal.",
                "- Las fachadas norte apenas reciben radiación directa y deben priorizar el aislamiento y un "
                "acristalamiento controlado.",
                "En consecuencia, conviene maximizar las ganancias solares en la fachada sur con una protección "
                "horizontal ligera, emplear protecciones regulables en este y oeste y limitar las pérdidas de calor en "
                "la fachada norte.",
            ],
        },
    },
}

def fmt_num(v) -> str:
    v = float(v)
    return str(int(round(v))) if abs(v - round(v)) < 0.05 else f"{v:.0f}"


def _join(items: list, lang: str) -> str:
    items = [str(x) for x in items]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + (" y " if lang == "es" else " and ") + items[-1]


def _range(r) -> str:
    a, b = fmt_num(r[0]), fmt_num(r[1])
    return a if a == b else f"{a}-{b}"


def facts_lines(facts: dict, lang: str, key: str) -> list:
    """The few facts each text needs, already interpreted, as short sentences (no JSON)."""
    sm, loc, an = facts["summary"], facts["location"], facts["annual"]
    es = lang == "es"
    regime = sm["dominant_demand"]
    reg_txt = {"heating": ("domina la CALEFACCIÓN", "HEATING dominates"),
               "cooling": ("domina la REFRIGERACIÓN", "COOLING dominates"),
               "balanced": ("calefacción y refrigeración EQUILIBRADAS", "heating and cooling are BALANCED")}[regime]
    hot = _join([f"{h['month']} ({fmt_num(h['mean_daily_max_C'])} °C)" for h in sm["hottest_months"]], lang)
    L = []
    if key == "temperature_text":
        L += [
            (f"Demanda dominante: {reg_txt[0]}." if es else f"Dominant demand: {reg_txt[1]}."),
            (f"Meses más calurosos (máxima media diaria): {hot}." if es else
             f"Hottest months (mean daily maximum): {hot}."),
            (f"Máximas medias en verano: {_range(sm['summer_mean_daily_max_range_C'])} °C. "
             f"Máximas medias en invierno: {_range(sm['winter_mean_daily_max_range_C'])} °C. "
             f"Mínimas medias en invierno: {_range(sm['winter_mean_daily_min_range_C'])} °C." if es else
             f"Summer mean daily maxima: {_range(sm['summer_mean_daily_max_range_C'])} °C. "
             f"Winter mean daily maxima: {_range(sm['winter_mean_daily_max_range_C'])} °C. "
             f"Winter mean daily minima: {_range(sm['winter_mean_daily_min_range_C'])} °C."),
        ]
        cm = sm["cooling_months"]
        few = _join(sm["months_with_most_hours_above_cooling"], lang)
        if cm:
            L.append(f"Meses con refrigeración: {_join(cm, lang)}." if es else f"Cooling months: {_join(cm, lang)}.")
        elif few:
            L.append(f"Refrigeración: no hay meses de refrigeración; solo horas puntuales de calor, sobre todo en {few}."
                     if es else f"Cooling: no cooling months; only occasional hot hours, mainly in {few}.")
        else:
            L.append("Refrigeración: prácticamente innecesaria." if es else "Cooling: practically unnecessary.")
        hm = sm["heating_months"]
        L.append((f"Meses con calefacción: {_join(hm, lang)}." if hm else "Calefacción: mínima.") if es else
                 (f"Heating months: {_join(hm, lang)}." if hm else "Heating: minimal."))
        L.append(f"Meses más confortables: {_join(sm['most_comfortable_months_utci'], lang)}." if es else
                 f"Most comfortable months: {_join(sm['most_comfortable_months_utci'], lang)}.")
        L.append(f"Humedad relativa media anual: {an['mean_rh_pct']} %." if es else
                 f"Mean annual relative humidity: {an['mean_rh_pct']} %.")
    else:
        names = sm["_month_names"]
        mon = sorted(facts["monthly"], key=lambda r: (-r["ghr_kWh_m2"], r["month"]))
        top, low = [names[r["month"] - 1] for r in mon[:2]], [names[r["month"] - 1] for r in mon[-2:]]
        seasons = facts["sunlit_hours_above_sun_filter_by_season"]
        total = sum(seasons.values())
        amount = ("muchas" if total > 800 else "bastantes" if total > 300 else "pocas") if es else \
                 ("many" if total > 800 else "a fair number of" if total > 300 else "few")
        sname = {"winter": ("invierno", "winter"), "spring": ("primavera", "spring"),
                 "summer": ("verano", "summer"), "autumn": ("otoño", "autumn")}
        main = [sname[k][0 if es else 1] for k, v in sorted(seasons.items(), key=lambda kv: -kv[1]) if v > 0.15 * max(1, total)]
        sol = facts["solar"]
        south = loc["hemisphere"] == "north"
        L += [
            (f"Radiación global anual: {an['ghr_kWh_m2']} kWh/m². Meses con más radiación: {_join(top, lang)}; "
             f"con menos: {_join(low, lang)}." if es else
             f"Annual global radiation: {an['ghr_kWh_m2']} kWh/m². Sunniest months: {_join(top, lang)}; "
             f"least sunny: {_join(low, lang)}."),
            (f"Carta solar filtrada para T > {fmt_num(facts['thresholds_C']['sun_filter'])} °C: hay {amount} horas de "
             f"sol calurosas, sobre todo en {_join(main, lang) or 'verano'}." if es else
             f"Sun-path filtered for T > {fmt_num(facts['thresholds_C']['sun_filter'])} °C: there are {amount} hot "
             f"sunny hours, mainly in {_join(main, lang) or 'summer'}."),
            (f"Altura solar máxima: {fmt_num(sol['summer_solstice']['max_altitude_deg'])}° en verano y "
             f"{fmt_num(sol['winter_solstice']['max_altitude_deg'])}° en invierno." if es else
             f"Maximum solar altitude: {fmt_num(sol['summer_solstice']['max_altitude_deg'])}° in summer and "
             f"{fmt_num(sol['winter_solstice']['max_altitude_deg'])}° in winter."),
            (f"Demanda dominante: {reg_txt[0]}." if es else f"Dominant demand: {reg_txt[1]}."),
            (("Fachada al ecuador: SUR. Fachada al polo: NORTE." if south else
              "Hemisferio sur: fachada al ecuador: NORTE. Fachada al polo: SUR.") if es else
             ("Equator-facing façade: SOUTH. Pole-facing façade: NORTH." if south else
              "Southern hemisphere: equator-facing façade: NORTH. Pole-facing façade: SOUTH.")),
        ]
    return L


PLAN = {
    "temperature_text": {
        "es": ["Tipo de clima, carácter de veranos e inviernos y temperaturas típicas (meses más calurosos y rango "
               "de invierno).",
               "La demanda dominante y sus meses.",
               "La otra demanda (secundaria) y sus meses.",
               "El principal reto de diseño bioclimático, coherente con la demanda dominante."],
        "en": ["Climate type, character of summers and winters and typical temperatures (hottest months and winter "
               "range).",
               "The dominant demand and its months.",
               "The other (secondary) demand and its months.",
               "The main bioclimatic design challenge, coherent with the dominant demand."],
    },
    "sun_text": {
        "es": ["Radiación solar a lo largo del año y lo que muestra la carta solar filtrada por temperatura.",
               "- Fachadas este y oeste.",
               "- Fachada al ecuador.",
               "- Fachada al polo.",
               "Frase final que empiece por \"En consecuencia,\" con la estrategia por orientación, coherente con la "
               "demanda dominante."],
        "en": ["Solar radiation along the year and what the temperature-filtered sun-path shows.",
               "- East and west façades.",
               "- Equator-facing façade.",
               "- Pole-facing façade.",
               "Closing sentence starting with \"Consequently,\" with the strategy per orientation, coherent with the "
               "dominant demand."],
    },
}

WHAT = {"temperature_text": ("el texto de TEMPERATURA", "the TEMPERATURE text"),
        "sun_text": ("el texto de SOL", "the SUN text")}
EX_KEY = {"temperature_text": "temperature_paragraphs", "sun_text": "sun_paragraphs"}


def build_text_prompt(facts: dict, language: str, key: str) -> str:
    """Short prompt for ONE text: data as sentences, a 4-5 line plan, one example of the same climate.
    Answer = plain paragraphs separated by a blank line (no JSON)."""
    lang = "es" if language == "es" else "en"
    es = lang == "es"
    city = facts["location"]["city"]
    lim = limits()[key]
    regime = facts["summary"]["dominant_demand"]
    sun_t = fmt_num(facts["thresholds_C"]["sun_filter"])
    ex_regime = "cooling" if regime == "cooling" else "heating" if regime == "heating" else "cooling"
    example = [p.replace("{t}", sun_t).replace("The city", city).replace("La ciudad", city)
               for p in EXAMPLES[ex_regime][lang][EX_KEY[key]]]
    plan = "\n".join(f"{i}. {x}" for i, x in enumerate(PLAN[key][lang], 1))
    data = "\n".join(f"- {x}" for x in facts_lines(facts, lang, key))
    if es:
        return (f"Escribe en español {WHAT[key][0]} de una lámina de análisis climático de {city}.\n\n"
                f"DATOS DE {city.upper()}:\n{data}\n\n"
                f"ESTRUCTURA: exactamente {lim['paragraphs']} párrafos, máximo {lim['max_words']} palabras en total:\n"
                f"{plan}\n\n"
                "ESTILO: copia el tono, la estructura y la longitud de este ejemplo de otra ciudad con un clima "
                "parecido, pero usa SOLO los datos de arriba:\n\n" + "\n\n".join(example) + "\n\n"
                "Responde solo con los párrafos, separados por una línea en blanco. Sin títulos ni markdown.")
    return (f"Write in English {WHAT[key][1]} of a climate analysis sheet for {city}.\n\n"
            f"DATA FOR {city.upper()}:\n{data}\n\n"
            f"STRUCTURE: exactly {lim['paragraphs']} paragraphs, {lim['max_words']} words maximum in total:\n"
            f"{plan}\n\n"
            "STYLE: copy the tone, structure and length of this example from another city with a similar climate, "
            "but use ONLY the data above:\n\n" + "\n\n".join(example) + "\n\n"
            "Answer only with the paragraphs, separated by a blank line. No headings, no markdown.")


def build_prompt(facts: dict, language: str = "en") -> str:
    """Manual mode (copy & paste into another assistant): both texts, answer as JSON."""
    es = language == "es"
    t = build_text_prompt(facts, language, "temperature_text")
    s = build_text_prompt(facts, language, "sun_text")
    head = ("Vas a redactar DOS textos. Devuelve un JSON {\"temperature_text\": \"...\", \"sun_text\": \"...\"} con "
            "los párrafos separados por \\n\\n.\n\n=== TEXTO 1 ===\n" if es else
            "You will write TWO texts. Return a JSON {\"temperature_text\": \"...\", \"sun_text\": \"...\"} with "
            "paragraphs separated by \\n\\n.\n\n=== TEXT 1 ===\n")
    return head + t + ("\n\n=== TEXTO 2 ===\n" if es else "\n\n=== TEXT 2 ===\n") + s


_SENT = re.compile(r"(?<=[.!?])\s+(?=[\"'(\-–A-ZÁÉÍÓÚÑ0-9])")


def _sentences(p: str) -> list:
    return [x.strip() for x in _SENT.split(p) if x.strip()]


def _split_even(sentences: list, n: int) -> list:
    """Group sentences into n paragraphs of similar word count (deterministic)."""
    if n <= 1 or len(sentences) <= 1:
        return [" ".join(sentences)]
    total = sum(len(s.split()) for s in sentences)
    target, out, cur, acc = total / n, [], [], 0
    for s in sentences:
        cur.append(s)
        acc += len(s.split())
        if acc >= target * (len(out) + 1) and len(out) < n - 1:
            out.append(" ".join(cur))
            cur = []
    if cur:
        out.append(" ".join(cur))
    return out


def fit_text(text_or_list, max_words: int, paragraphs: int) -> str:
    """Normalise to paragraphs separated by a blank line and cap the word count
    by dropping whole trailing sentences (never cutting a sentence in half)."""
    _strip = lambda x: re.sub(r"\s*\([^()]*\b(?:HDD|CDD)\d*\b[^()]*\)", "", str(x))  # noqa: E731
    if isinstance(text_or_list, list):
        text_or_list = [_strip(p) for p in text_or_list]
    else:
        text_or_list = _strip(text_or_list)
    if isinstance(text_or_list, list):
        paras = [" ".join(str(p).split()) for p in text_or_list if str(p).strip()]
    else:
        raw = str(text_or_list or "").replace("\r", "")
        paras = [" ".join(p.split()) for p in re.split(r"\n\s*\n|\n(?=- )", raw) if p.strip()]
    if len(paras) == 1 and paragraphs > 1:  # model ignored the structure: rebuild it
        paras = _split_even(_sentences(paras[0]), paragraphs)
    out, used = [], 0
    for p in paras:
        kept = []
        for s in _sentences(p):
            n = len(s.split())
            if used + n > max_words:
                break
            kept.append(s)
            used += n
        if kept:
            out.append(" ".join(kept))
        if used >= max_words or len(kept) < len(_sentences(p)):
            break
    return "\n\n".join(out)


def parse_response(raw: str) -> dict:
    """Accept JSON (lists or strings, possibly wrapped in prose / code fences)."""
    lim = limits()
    raw = (raw or "").strip()
    data = {}
    a, b = raw.find("{"), raw.rfind("}")
    if a != -1 and b > a:
        try:
            data = json.loads(raw[a:b + 1])
        except json.JSONDecodeError:
            data = {}
    temp = data.get("temperature_paragraphs", data.get("temperature_text", raw if not data else ""))
    sun = data.get("sun_paragraphs", data.get("sun_text", ""))
    return {
        "temperature_text": fit_text(temp, **lim["temperature_text"]),
        "sun_text": fit_text(sun, **lim["sun_text"]),
    }
