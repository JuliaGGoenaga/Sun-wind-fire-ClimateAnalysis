"""All climate calculations from the EPW, done with ladybug (pure, deterministic)."""
from __future__ import annotations

import functools
import re

from ladybug.epw import EPW
from ladybug.sunpath import Sunpath

MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
MONTH_START = [sum(MONTH_DAYS[:i]) for i in range(12)]


def _clean_city(name: str) -> str:
    name = re.sub(r"[._]+", " ", name or "").strip()
    name = re.sub(r"\b(Intl|AP|Airport|Arpt|Field|Love Field|Rgnl|Muni)\b.*$", "", name, flags=re.I).strip(" -")
    return name.title() if name.isupper() else (name or "Location")


class Climate:
    def __init__(self, epw_path: str, utci_sun_exposed: bool = True):
        self.epw = EPW(epw_path)
        self.location = self.epw.location
        self.city = _clean_city(self.location.city)
        self.utci_sun_exposed = utci_sun_exposed
        dbt = self.epw.dry_bulb_temperature
        self.dbt = [float(v) for v in dbt.values]
        self.dts = list(dbt.datetimes)
        self.ghr = [float(v) for v in self.epw.global_horizontal_radiation.values]
        self.rh = [float(v) for v in self.epw.relative_humidity.values]
        self.ws = [float(v) for v in self.epw.wind_speed.values]
        self.wd = [float(v) % 360 for v in self.epw.wind_direction.values]
        self.n = len(self.dbt)
        self.month = [dt.month for dt in self.dts]
        self.hour = [dt.hour for dt in self.dts]
        self.doy = [min(MONTH_START[dt.month - 1] + dt.day - 1, 364) for dt in self.dts]
        self.sunpath = Sunpath.from_location(self.location)
        self.south = self.location.latitude < 0

    # ---------------------------------------------------------------- comfort
    @functools.cached_property
    def utci_condition(self) -> list:
        """UTCI 11-point thermal stress (+5 extreme heat ... -5 extreme cold)."""
        from ladybug_comfort.collection.utci import UTCI
        e = self.epw
        if self.utci_sun_exposed:
            from ladybug_comfort.collection.solarcal import OutdoorSolarCal
            mrt = OutdoorSolarCal(e.location, e.direct_normal_radiation, e.diffuse_horizontal_radiation,
                                  e.horizontal_infrared_radiation_intensity,
                                  e.dry_bulb_temperature).mean_radiant_temperature
        else:
            mrt = e.dry_bulb_temperature
        utci = UTCI(e.dry_bulb_temperature, e.relative_humidity, mrt, e.wind_speed)
        return [int(v) for v in utci.thermal_condition_eleven_point.values]

    # ---------------------------------------------------------- psychrometrics
    @functools.cached_property
    def psychro(self) -> dict:
        """Humidity ratio (g/kg) and enthalpy (kJ/kg) from DBT, RH and station pressure."""
        from ladybug.psychrometrics import enthalpy_from_db_hr, humid_ratio_from_db_rh
        pres = [float(v) for v in self.epw.atmospheric_station_pressure.values]
        hr = [humid_ratio_from_db_rh(t, rh, p if p > 30000 else 101325)
              for t, rh, p in zip(self.dbt, self.rh, pres)]
        return {"hr_gkg": [v * 1000 for v in hr],
                "enthalpy": [enthalpy_from_db_hr(t, h) for t, h in zip(self.dbt, hr)]}

    # -------------------------------------------------------------------- wind
    def wind_hours(self, months=None, hours=None) -> list:
        """Indices of non-calm hours (speed >= 0.1 m/s) matching months / hours-of-day."""
        return [i for i in range(self.n) if self.ws[i] >= 0.1
                and (months is None or self.month[i] in months)
                and (hours is None or self.hour[i] in hours)]

    def prevailing(self, idx: list) -> dict:
        names = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        if not idx:
            return {"direction": None, "share_pct": 0, "mean_speed_ms": 0}
        cnt = [0] * 16
        for i in idx:
            cnt[int(((self.wd[i] + 11.25) % 360) // 22.5)] += 1
        k = max(range(16), key=lambda j: (cnt[j], -j))
        return {"direction": names[k], "share_pct": round(100 * cnt[k] / len(idx)),
                "mean_speed_ms": round(sum(self.ws[i] for i in idx) / len(idx), 1)}

    # ------------------------------------------------------- monthly per hour
    @functools.cached_property
    def monthly_hourly(self) -> dict:
        """{month: {'min','mean','max','ghr'}: 24-value lists} (month 1..12)."""
        acc = {m: {h: [] for h in range(24)} for m in range(1, 13)}
        rad = {m: {h: [] for h in range(24)} for m in range(1, 13)}
        for i in range(self.n):
            acc[self.month[i]][self.hour[i]].append(self.dbt[i])
            rad[self.month[i]][self.hour[i]].append(self.ghr[i])
        out = {}
        for m in range(1, 13):
            out[m] = {
                "min": [min(acc[m][h]) for h in range(24)],
                "max": [max(acc[m][h]) for h in range(24)],
                "mean": [sum(acc[m][h]) / len(acc[m][h]) for h in range(24)],
                "ghr": [sum(rad[m][h]) / len(rad[m][h]) for h in range(24)],
            }
        return out

    # ------------------------------------------------------------------- sun
    @functools.cached_property
    def suns(self) -> list:
        sp = self.sunpath
        return [sp.calculate_sun_from_hoy(dt.hoy) for dt in self.dts]

    def season_months(self) -> list:
        """[winter, spring, summer, autumn] month lists for the hemisphere."""
        north = [[12, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11]]
        if not self.south:
            return north
        return [north[2], north[3], north[0], north[1]]

    def key_days(self) -> dict:
        """Summer solstice, equinoxes and winter solstice as (month, day) lists."""
        jun, dec = [(6, 21)], [(12, 21)]
        return {
            "summer_solstice": dec if self.south else jun,
            "equinox": [(3, 21), (9, 21)],
            "winter_solstice": jun if self.south else dec,
        }

    # ------------------------------------------------------------- LLM facts
    def _summary(self, months: list, cdd: float, hdd: float, s: dict) -> dict:
        """Pre-digested key facts so the model does not have to derive them (fewer mistakes)."""
        from .settings import LABELS
        names = LABELS.get(s.get("language", "en"), LABELS["en"])["month_names"]
        nm = lambda m: names[m - 1]  # noqa: E731
        hrs = {m: sum(1 for i in range(self.n) if self.month[i] == m) for m in range(1, 13)}
        hot = sorted(months, key=lambda r: (-r["mean_daily_max_C"], r["month"]))[:2]
        winter = [r for r in months if r["month"] in self.season_months()[0]]
        summer = [r for r in months if r["month"] in self.season_months()[2]]
        # cooling month: >= 15 % of its hours above the cooling threshold
        cooling = [r["month"] for r in months if r["hours_above_cooling"] >= 0.15 * hrs[r["month"]]]
        # heating month: monthly mean temperature at least 4 K below the heating threshold
        heating = [r["month"] for r in months if r["mean_temp_C"] <= s["heating_threshold"] - 4]
        comfy = sorted(months, key=lambda r: (-r["utci_no_stress_pct"], r["month"]))[:3]
        if cdd > 1.5 * hdd:
            dominant = "cooling"
        elif hdd > 1.5 * cdd:
            dominant = "heating"
        else:
            dominant = "balanced"
        return {
            "dominant_demand": dominant,
            "hottest_months": [{"month": nm(r["month"]), "mean_daily_max_C": r["mean_daily_max_C"]} for r in hot],
            "summer_mean_daily_max_range_C": [min(r["mean_daily_max_C"] for r in summer),
                                              max(r["mean_daily_max_C"] for r in summer)],
            "winter_mean_daily_max_range_C": [min(r["mean_daily_max_C"] for r in winter),
                                              max(r["mean_daily_max_C"] for r in winter)],
            "winter_mean_daily_min_range_C": [min(r["mean_daily_min_C"] for r in winter),
                                              max(r["mean_daily_min_C"] for r in winter)],
            "cooling_months": [nm(m) for m in cooling],
            "heating_months": [nm(m) for m in heating],
            "most_comfortable_months_utci": [nm(r["month"]) for r in comfy],
            "annual_hours_above_cooling_threshold": sum(r["hours_above_cooling"] for r in months),
            "annual_hours_below_heating_threshold": sum(r["hours_below_heating"] for r in months),
            "months_with_most_hours_above_cooling": [nm(r["month"]) for r in sorted(
                months, key=lambda r: (-r["hours_above_cooling"], r["month"]))[:2] if r["hours_above_cooling"] > 0],
            "CDD18": round(cdd), "HDD18": round(hdd),
            "_month_names": names,
        }

    def facts(self, s: dict) -> dict:
        """Compact, deterministic numeric summary passed to the language model."""
        loc = self.location
        mh = self.monthly_hourly
        cool, heat, sun_t = s["cooling_threshold"], s["heating_threshold"], s["sun_threshold"]
        months = []
        daily_mean = {}
        for i in range(self.n):
            daily_mean.setdefault(self.doy[i], []).append(self.dbt[i])
        cdd = sum(max(0.0, sum(v) / len(v) - 18.0) for v in daily_mean.values())
        hdd = sum(max(0.0, 18.0 - sum(v) / len(v)) for v in daily_mean.values())
        cond = self.utci_condition
        for m in range(1, 13):
            idx = [i for i in range(self.n) if self.month[i] == m]
            days = {}
            for i in idx:
                days.setdefault(self.doy[i], []).append(self.dbt[i])
            months.append({
                "month": m,
                "mean_temp_C": round(sum(self.dbt[i] for i in idx) / len(idx), 1),
                "mean_daily_max_C": round(sum(max(v) for v in days.values()) / len(days), 1),
                "mean_daily_min_C": round(sum(min(v) for v in days.values()) / len(days), 1),
                "mean_rh_pct": round(sum(self.rh[i] for i in idx) / len(idx)),
                "ghr_kWh_m2": round(sum(self.ghr[i] for i in idx) / 1000, 1),
                "hours_above_cooling": sum(1 for i in idx if self.dbt[i] > cool),
                "hours_below_heating": sum(1 for i in idx if self.dbt[i] < heat),
                "utci_no_stress_pct": round(100 * sum(1 for i in idx if cond[i] == 0) / len(idx)),
                "utci_heat_stress_pct": round(100 * sum(1 for i in idx if cond[i] > 0) / len(idx)),
                "utci_cold_stress_pct": round(100 * sum(1 for i in idx if cond[i] < 0) / len(idx)),
            })
        sp = self.sunpath
        solar = {}
        for key, days in self.key_days().items():
            mth, d = days[0]
            noon = max((sp.calculate_sun(mth, d, h / 4.0) for h in range(96)), key=lambda x: x.altitude)
            rs = sp.calculate_sunrise_sunset(mth, d)
            length = (rs["sunset"] - rs["sunrise"]).total_seconds() / 3600 if rs["sunrise"] and rs["sunset"] else None
            solar[key] = {"max_altitude_deg": round(noon.altitude, 1),
                          "day_length_h": round(length, 1) if length else None}
        seasons = {}
        names = ["winter", "spring", "summer", "autumn"]
        for name, ms in zip(names, self.season_months()):
            seasons[name] = sum(1 for i in range(self.n)
                                if self.month[i] in ms and self.dbt[i] > sun_t and self.suns[i].altitude > 0)
        quarters = [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12]]
        day = set(range(8, 18))
        night = set(range(24)) - day
        wind = {
            "annual": self.prevailing(self.wind_hours()),
            "calm_pct": round(100 * sum(1 for v in self.ws if v < 0.1) / self.n),
            "pct_hours_above_5ms": round(100 * sum(1 for v in self.ws if v > 5) / self.n),
            "max_speed_ms": round(max(self.ws), 1),
            "by_quarter": [{"months": q, "all": self.prevailing(self.wind_hours(q)),
                            "day_8_18": self.prevailing(self.wind_hours(q, day)),
                            "night_18_8": self.prevailing(self.wind_hours(q, night))} for q in quarters],
        }
        nv_lo, nv_hi = s.get("nv_min", 10.0), s.get("nv_max", 24.0)
        hr = self.psychro["hr_gkg"]
        humidity = [{"month": m,
                     "mean_rh_pct": round(sum(self.rh[i] for i in range(self.n) if self.month[i] == m)
                                          / sum(1 for i in range(self.n) if self.month[i] == m)),
                     "mean_humidity_ratio_gkg": round(sum(hr[i] for i in range(self.n) if self.month[i] == m)
                                                      / sum(1 for i in range(self.n) if self.month[i] == m), 1),
                     "natural_ventilation_hours_pct": round(100 * sum(
                         1 for i in range(self.n) if self.month[i] == m and nv_lo <= self.dbt[i] <= nv_hi)
                         / sum(1 for i in range(self.n) if self.month[i] == m))} for m in range(1, 13)]
        return {
            "wind": wind,
            "humidity_and_ventilation": {"natural_ventilation_range_C": [nv_lo, nv_hi],
                                         "annual_nv_hours_pct": round(100 * sum(
                                             1 for v in self.dbt if nv_lo <= v <= nv_hi) / self.n),
                                         "monthly": humidity},
            "location": {"city": s["city"], "country": loc.country, "latitude": round(loc.latitude, 2),
                         "longitude": round(loc.longitude, 2), "elevation_m": round(loc.elevation),
                         "hemisphere": "south" if self.south else "north"},
            "thresholds_C": {"cooling": cool, "heating": heat, "sun_filter": sun_t},
            "annual": {"mean_temp_C": round(sum(self.dbt) / self.n, 1), "min_temp_C": round(min(self.dbt), 1),
                       "max_temp_C": round(max(self.dbt), 1), "mean_rh_pct": round(sum(self.rh) / self.n),
                       "ghr_kWh_m2": round(sum(self.ghr) / 1000), "CDD18": round(cdd), "HDD18": round(hdd),
                       "hours_above_cooling": sum(1 for v in self.dbt if v > cool),
                       "hours_below_heating": sum(1 for v in self.dbt if v < heat)},
            "summary": self._summary(months, cdd, hdd, s),
            "monthly": months,
            "solar": solar,
            "sunlit_hours_above_sun_filter_by_season": seasons,
            "peak_hourly_ghr_Wh_m2": round(max(max(mh[m]["ghr"]) for m in mh)),
        }
