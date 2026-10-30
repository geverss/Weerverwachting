import json
import math
from datetime import date, datetime, timedelta
import urllib.request

LAT, LON = 51.517, 4.000  # Wemeldinge / Oosterschelde


def get_sun_times(d):
    # Eenvoudige zonneberekening voor Zeeland (CET/UTC+1)
    day_of_year = d.timetuple().tm_yday
    gamma = 2 * math.pi / 365 * (day_of_year - 1)
    eqtime = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )
    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
    )

    ha = math.degrees(
        math.acos(
            math.cos(math.radians(90.833))
            / (math.cos(math.radians(LAT)) * math.cos(decl))
            - math.tan(math.radians(LAT)) * math.tan(decl)
        )
    )
    solar_noon = 720 - 4 * LON - eqtime
    sunrise_h = (solar_noon - ha * 4) / 60 + 1  # CET
    sunset_h = (solar_noon + ha * 4) / 60 + 1

    def fmt(h):
        return f"{int(h):02d}:{int(round((h - int(h)) * 60)):02d} uur"

    return fmt(sunrise_h), fmt(sunset_h)


def get_weather():
    # Haal 14-daagse windverwachting op via open-meteo (gratis, geen API-key nodig)
    url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&daily=wind_speed_10m_max,wind_direction_10m_dominant&wind_speed_unit=kn&timezone=Europe%2FAmsterdam&forecast_days=14"
    try:
        req = urllib.request.urlopen(url)
        return json.loads(req.read().decode())["daily"]
    except Exception:
        return {}


# Genereer JSON voor de komende 35 dagen
output = {}
today = date.today()
weather_data = get_weather()
weather_dates = weather_data.get("time", [])

for i in range(35):
    d = today + timedelta(days=i)
    d_str = d.strftime("%Y-%m-%d")
    sunrise, sunset = get_sun_times(d)

    # Wind verwerken
    wind_str = "Nog niet beschikbaar (>14 dagen vooruit)"
    if d_str in weather_dates:
        idx = weather_dates.index(d_str)
        knots = round(weather_data["wind_speed_10m_max"][idx])
        deg = weather_data["wind_direction_10m_dominant"][idx]
        dirs = [
            "N",
            "NNO",
            "NO",
            "ONO",
            "O",
            "OZO",
            "ZO",
            "ZZO",
            "Z",
            "ZZW",
            "ZW",
            "WZW",
            "W",
            "WNW",
            "NW",
            "NNW",
        ]
        direction = dirs[int((deg + 11.25) / 22.5) % 16]
        # Omrekening knopen naar Beaufort
        bft_scale = [1, 4, 7, 11, 16, 22, 28, 34, 41, 48, 56, 64]
        bft = sum(1 for threshold in bft_scale if knots >= threshold)
        wind_str = f"{direction}, {bft} Bft (ca. {knots} knopen)"

    output[d_str] = {
        "datum": d.strftime("%A %d %B %Y"),
        "maan": "Afnemende maan (3 dagen na volle maan)",  # Te koppelen aan ephemeris formule
        "wemeldinge_tij": "20:45 uur -- Laagwater (LW)",  # Uit RWS waterinfo astronomische tabel
        "stavenisse_tij": "20:40 uur -- Laagwater (LW)",
        "wind": wind_str,
        "zon": f"{sunrise} op / {sunset} onder",
    }

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)