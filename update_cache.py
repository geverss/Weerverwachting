import json
import math
import urllib.request
from datetime import date, datetime, timedelta

# Coördinaten
LAT_ZEELAND, LON_ZEELAND = 51.517, 4.000  # Wemeldinge / Oosterschelde
LAT_NIJLEN, LON_NIJLEN = 51.161, 4.670  # Nijlen

WIND_DIRECTIONS = [
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
BFT_THRESHOLDS = [1, 4, 7, 11, 16, 22, 28, 34, 41, 48, 56, 64]


def knots_to_bft(knots):
    return sum(1 for t in BFT_THRESHOLDS if knots >= t)


def deg_to_dir(deg):
    return WIND_DIRECTIONS[int((deg + 11.25) / 22.5) % 16]


def get_sun_times(d, lat, lon):
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
            / (math.cos(math.radians(lat)) * math.cos(decl))
            - math.tan(math.radians(lat)) * math.tan(decl)
        )
    )
    solar_noon = 720 - 4 * lon - eqtime
    sunrise_h = (solar_noon - ha * 4) / 60 + 1  # CET
    sunset_h = (solar_noon + ha * 4) / 60 + 1

    def fmt(h):
        hh = int(h)
        mm = int(round((h - hh) * 60))
        if mm == 60:
            hh += 1
            mm = 0
        return f"{hh:02d}:{mm:02d} uur"

    return fmt(sunrise_h), fmt(sunset_h)


def get_moon_phase(target_date):
    # Referentie nieuwe maan: 18 jan 2026, 16:52 UTC
    ref_new_moon = datetime(2026, 1, 18, 16, 52)
    diff_days = (
        datetime.combine(target_date, datetime.min.time()) - ref_new_moon
    ).total_seconds() / 86400.0
    synodic = 29.53058867
    cycle_age = diff_days % synodic

    phases = [
        (0.0, "Nieuwe Maan"),
        (7.3826, "Eerste Kwartier (halve maan)"),
        (14.7653, "Volle Maan"),
        (22.1479, "Laatste Kwartier (halve maan)"),
        (29.5306, "Nieuwe Maan"),
    ]

    diffs = [abs(cycle_age - p[0]) for p in phases]
    idx = diffs.index(min(diffs))
    nearest = phases[idx]

    delta = cycle_age - nearest[0]
    days_rnd = round(abs(delta))

    phase_angle = (cycle_age / synodic) * 2 * math.pi
    illumination = round((1 - math.cos(phase_angle)) / 2 * 100)

    if days_rnd == 0:
        rel = f"vandaag {nearest[1]}"
    elif delta > 0:
        rel = f"{days_rnd} {'dag' if days_rnd == 1 else 'dagen'} na {nearest[1]}"
    else:
        rel = (
            f"{days_rnd} {'dag' if days_rnd == 1 else 'dagen'} vóór {nearest[1]}"
        )

    trend = "wassende maan" if cycle_age < 14.765 else "afnemende maan"
    tide_type = (
        "springtijperiode"
        if (abs(cycle_age - 0) < 3.5 or abs(cycle_age - 14.765) < 3.5)
        else "doodtijperiode"
    )

    return f"{rel}; {trend} (ca. {illumination}% verlicht, {tide_type})"


def get_last_tide(target_date):
    # Referentiegetij Wemeldinge: 27 okt 2026 22:11 CET (LW)
    ref_time = datetime(2026, 10, 27, 22, 11)
    ref_type = "LW"
    half_cycle = timedelta(minutes=372.5)  # Gemiddeld semi-diurnaal interval

    start_day = datetime.combine(target_date, datetime.min.time())
    end_day = datetime.combine(target_date, datetime.max.time())

    steps = int((start_day - ref_time).total_seconds() / half_cycle.total_seconds()) - 2
    t = ref_time + steps * half_cycle
    typ = ref_type if (steps % 2 == 0) else ("HW" if ref_type == "LW" else "LW")

    day_tides = []
    while t <= end_day + timedelta(hours=8):
        if t.date() == target_date:
            day_tides.append((t, typ))
        t += half_cycle
        typ = "HW" if typ == "LW" else "LW"

    if not day_tides:
        return "18:00 uur — Hoogwater (HW)", "17:55 uur — Hoogwater (HW)"

    last_t, last_typ = day_tides[-1]
    stav_t = last_t - timedelta(minutes=5)

    wem_label = "Hoogwater (HW)" if last_typ == "HW" else "Laagwater (LW)"
    stav_label = "Hoogwater (HW)" if last_typ == "HW" else "Laagwater (LW)"

    return (
        f"{last_t.strftime('%H:%M')} uur — {wem_label}",
        f"{stav_t.strftime('%H:%M')} uur — {stav_label}",
    )


def fetch_weather(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        "&daily=wind_speed_10m_max,wind_direction_10m_dominant,temperature_2m_max,precipitation_probability_max"
        "&wind_speed_unit=kn&timezone=Europe%2FBrussels&forecast_days=14"
    )
    req = urllib.request.Request(
        url, headers={"User-Agent": "OosterscheldeDuikplanner/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8")).get("daily", {})
    except Exception as e:
        print(f"Weer ophalen mislukt voor {lat},{lon}: {e}")
        return {}


def format_weather(daily_data, d_str):
    times = daily_data.get("time", [])
    if not times or d_str not in times:
        return "Geen modelverwachting (>14 dagen vooruit)"

    idx = times.index(d_str)
    knots = round(daily_data["wind_speed_10m_max"][idx])
    deg = daily_data["wind_direction_10m_dominant"][idx]
    temp = round(daily_data["temperature_2m_max"][idx])
    rain = daily_data["precipitation_probability_max"][idx]

    direction = deg_to_dir(deg)
    bft = knots_to_bft(knots)

    return f"{direction}, {bft} Bft (ca. {knots} knopen) — {temp}°C, {rain}% regen"


today = date.today()
weather_zeeland = fetch_weather(LAT_ZEELAND, LON_ZEELAND)
weather_nijlen = fetch_weather(LAT_NIJLEN, LON_NIJLEN)

cache = {}

for i in range(35):
    d = today + timedelta(days=i)
    d_str = d.strftime("%Y-%m-%d")

    sunrise, sunset = get_sun_times(d, LAT_ZEELAND, LON_ZEELAND)
    wem_tij, stav_tij = get_last_tide(d)
    moon = get_moon_phase(d)
    w_zeeland = format_weather(weather_zeeland, d_str)
    w_nijlen = format_weather(weather_nijlen, d_str)

    cache[d_str] = {
        "datum": d.strftime("%A %d %B %Y"),
        "maan": moon,
        "wemeldinge_tij": wem_tij,
        "stavenisse_tij": stav_tij,
        "wind_oosterschelde": w_zeeland,
        "weer_nijlen": w_nijlen,
        "wind": w_zeeland,  # Backwards-compatibility alias
        "zon": f"Zonsopgang: {sunrise} / Zonsondergang: {sunset}",
    }

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(cache, f, ensure_ascii=False, indent=2)

print(f"data.json succesvol gegenereerd voor {len(cache)} dagen.")