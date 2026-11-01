"""
Karur & Textile Hub Live Weather & Outdoor Hank-Drying Radar
tools/weather_radar_tool.py - 100% Free Open-Meteo REST API integration.
Fetches real-time temperature, humidity, precipitation probability, and wind speed.
Evaluates industrial outdoor sun-drying feasibility for SGC yarn dyeing operations.
"""
import sys
import urllib.request
import urllib.parse
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger("weather_radar_tool")
IST_TZ = timezone(timedelta(hours=5, minutes=30))

# Standard Coordinates for Tamil Nadu Textile Hubs
# Expanded Geographical Coordinates for Tamil Nadu & South India Hubs
COORDINATES = {
    "karur": (10.9601, 78.0766),
    "tirupur": (11.1085, 77.3411),
    "coimbatore": (11.0168, 76.9558),
    "erode": (11.3410, 77.7172),
    "dindigul": (10.3673, 77.9803),
    "salem": (11.6643, 78.1460),
    "trichy": (10.7905, 78.7047),
    "tiruchirappalli": (10.7905, 78.7047),
    "madurai": (9.9252, 78.1198),
    "chennai": (13.0827, 80.2707),
    "bangalore": (12.9716, 77.5946),
    "bengaluru": (12.9716, 77.5946),
    "namakkal": (11.2189, 78.1674),
    "ooty": (11.4102, 76.6950),
    "kodaikanal": (10.2381, 77.4892),
    "vellore": (12.9165, 79.1325),
    "thanjavur": (10.7870, 79.1378),
    "tirunelveli": (8.7139, 77.7567)
}

OVERRIDE_FILE = None
try:
    from pathlib import Path
    OVERRIDE_FILE = Path(__file__).resolve().parent.parent / "storage" / "memory" / "weather_override.json"
except Exception:
    pass


def set_active_location(new_city: str) -> Dict[str, Any]:
    """Updates Mukil's active primary location in user profile dynamically."""
    from pathlib import Path
    profile_path = Path(__file__).resolve().parent.parent / "storage" / "memory" / "user_profile.json"
    city_clean = new_city.strip().capitalize()
    
    if profile_path.exists():
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                pdata = json.load(f)
            pdata.setdefault("personal_details", {})["location"] = f"{city_clean}, Tamil Nadu"
            with open(profile_path, "w", encoding="utf-8") as f:
                json.dump(pdata, f, indent=2, ensure_ascii=False)
            logger.info(f"Updated primary location to {city_clean}")
            return {"success": True, "new_location": city_clean}
        except Exception as e:
            return {"success": False, "error": str(e)}
    return {"success": False, "error": "Profile file not found"}


def set_weather_simulation_override(temp_c: float = None, rain_prob_pct: int = None, humidity_pct: int = None, active: bool = True) -> Dict[str, Any]:
    """Sets or clears a manual weather override/simulation for testing alarms."""
    if not OVERRIDE_FILE:
        return {"success": False, "error": "Override path unavailable"}
    
    OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not active:
        if OVERRIDE_FILE.exists():
            OVERRIDE_FILE.unlink()
        return {"success": True, "override_active": False, "message": "Weather override cleared. Live satellite metrics active."}

    data = {
        "active": True,
        "temperature_c": temp_c,
        "rain_prob_pct": rain_prob_pct,
        "humidity_pct": humidity_pct
    }
    with open(OVERRIDE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return {"success": True, "override_active": True, "data": data}


def _fetch_from_open_meteo(lat: float, lon: float, timeout: int = 8) -> Optional[dict]:
    """Primary provider: Open-Meteo REST API."""
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&"
            f"current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,cloud_cover,wind_speed_10m,wind_gusts_10m,uv_index,is_day&"
            f"hourly=precipitation_probability"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "AURA-SGC-TextileEngine/2.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        curr = data.get("current", {})
        if "temperature_2m" not in curr:
            return None

        hourly_probs = data.get("hourly", {}).get("precipitation_probability", [0])[:6]
        max_rain_prob = max(hourly_probs) if hourly_probs else 0

        temp = float(curr.get("temperature_2m"))
        apparent_temp = float(curr.get("apparent_temperature", temp))
        return {
            "source": "open-meteo",
            "temperature_c": temp,
            "apparent_temperature_c": apparent_temp,
            "relative_humidity_pct": int(curr.get("relative_humidity_2m", 50)),
            "current_precipitation_mm": float(curr.get("precipitation", 0.0)),
            "cloud_cover_pct": int(curr.get("cloud_cover", 20)),
            "wind_speed_kmh": float(curr.get("wind_speed_10m", 10.0)),
            "wind_gusts_kmh": float(curr.get("wind_gusts_10m", 12.0)),
            "uv_index": float(curr.get("uv_index", 3.0)),
            "is_day": int(curr.get("is_day", 1)),
            "next_6h_rain_probability_pct": max_rain_prob
        }
    except Exception as e:
        logger.warning(f"Open-Meteo fetch failed ({e}), falling back to secondary radar.")
        return None


def _fetch_from_wttr_in(location: str, timeout: int = 6) -> Optional[dict]:
    """Secondary provider: wttr.in high-availability JSON."""
    try:
        clean_loc = urllib.parse.quote(location)
        url = f"https://wttr.in/{clean_loc}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.88.1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        curr = data.get("current_condition", [{}])[0]
        if not curr or "temp_C" not in curr:
            return None

        temp = float(curr.get("temp_C", 26.0))
        apparent = float(curr.get("FeelsLikeC", temp))
        humidity = int(curr.get("humidity", 60))
        wind = float(curr.get("windspeedKmph", 8.0))
        precip = float(curr.get("precipMM", 0.0))
        cloud = int(curr.get("cloudcover", 30))
        uv = float(curr.get("uvIndex", 3.0))

        rain_p = 0
        try:
            weather_list = data.get("weather", [{}])
            if weather_list:
                hourly = weather_list[0].get("hourly", [])
                if hourly:
                    rain_p = int(hourly[0].get("chanceofrain", 0))
        except Exception:
            pass

        now_ist = datetime.now(IST_TZ)
        is_day = 1 if 6 <= now_ist.hour < 18 else 0

        return {
            "source": "wttr.in",
            "temperature_c": temp,
            "apparent_temperature_c": apparent,
            "relative_humidity_pct": humidity,
            "current_precipitation_mm": precip,
            "cloud_cover_pct": cloud,
            "wind_speed_kmh": wind,
            "wind_gusts_kmh": round(wind * 1.3, 1),
            "uv_index": uv,
            "is_day": is_day,
            "next_6h_rain_probability_pct": rain_p
        }
    except Exception as e:
        logger.warning(f"wttr.in fetch failed ({e}), falling back to time-of-day baseline.")
        return None


def _get_time_of_day_baseline(location: str) -> dict:
    """Realistic Tamil Nadu textile hub climatic baseline when completely offline."""
    now_ist = datetime.now(IST_TZ)
    hour = now_ist.hour

    if 5 <= hour < 8:       # Early Morning
        temp, apparent, hum, cloud = 25.0, 27.0, 80, 25
    elif 8 <= hour < 11:    # Morning Warming
        temp, apparent, hum, cloud = 28.0, 31.0, 65, 20
    elif 11 <= hour < 15:   # Midday Peak
        temp, apparent, hum, cloud = 33.5, 36.0, 48, 15
    elif 15 <= hour < 18:   # Late Afternoon
        temp, apparent, hum, cloud = 30.5, 32.5, 55, 25
    elif 18 <= hour < 22:   # Evening
        temp, apparent, hum, cloud = 27.0, 28.5, 70, 30
    else:                   # Night
        temp, apparent, hum, cloud = 23.5, 24.5, 85, 20

    is_day = 1 if 6 <= hour < 18 else 0
    return {
        "source": "time_of_day_baseline",
        "temperature_c": temp,
        "apparent_temperature_c": apparent,
        "relative_humidity_pct": hum,
        "current_precipitation_mm": 0.0,
        "cloud_cover_pct": cloud,
        "wind_speed_kmh": 6.0,
        "wind_gusts_kmh": 12.0,
        "uv_index": 3.0 if 8 <= hour < 16 else 0.0,
        "is_day": is_day,
        "next_6h_rain_probability_pct": 10
    }


def get_live_weather_radar(location: str = "karur", manual_override: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Fetches real-time weather metrics and assesses outdoor hank yarn drying feasibility.
    Supports dynamic city selection across Tamil Nadu with resilient multi-tier failover:
    Tier 1: Open-Meteo REST API
    Tier 2: wttr.in Real-Time Weather
    Tier 3: Time-of-Day Textile Hub Climatic Baseline
    """
    loc_key = location.lower().strip().replace(" ", "")
    lat, lon = COORDINATES.get(loc_key, COORDINATES["karur"])

    # Check for persistent override file if not supplied
    if not manual_override and OVERRIDE_FILE and OVERRIDE_FILE.exists():
        try:
            with open(OVERRIDE_FILE, "r", encoding="utf-8") as f:
                saved_ov = json.load(f)
                if saved_ov.get("active"):
                    manual_override = saved_ov
        except Exception:
            pass

    # Tier 1: Open-Meteo
    metrics = _fetch_from_open_meteo(lat, lon, timeout=8)

    # Tier 2: wttr.in
    if not metrics:
        metrics = _fetch_from_wttr_in(location, timeout=6)

    # Tier 3: Time-of-day baseline
    if not metrics:
        metrics = _get_time_of_day_baseline(location)

    temp = metrics["temperature_c"]
    apparent_temp = metrics["apparent_temperature_c"]
    humidity = metrics["relative_humidity_pct"]
    precip = metrics["current_precipitation_mm"]
    wind = metrics["wind_speed_kmh"]
    gusts = metrics["wind_gusts_kmh"]
    cloud_cov = metrics["cloud_cover_pct"]
    uv = metrics["uv_index"]
    is_day = metrics["is_day"]
    max_rain_prob = metrics["next_6h_rain_probability_pct"]
    source = metrics["source"]

    # Apply manual simulation overrides if active
    if manual_override:
        if manual_override.get("temperature_c") is not None:
            temp = float(manual_override["temperature_c"])
            apparent_temp = temp + 1.5
        if manual_override.get("humidity_pct") is not None:
            humidity = int(manual_override["humidity_pct"])
        if manual_override.get("rain_prob_pct") is not None:
            max_rain_prob = int(manual_override["rain_prob_pct"])
        if manual_override.get("cloud_cover_pct") is not None:
            cloud_cov = int(manual_override["cloud_cover_pct"])

    # Assess Hank Drying Suitability
    if precip > 0 or max_rain_prob > 35:
        drying_status = "⚠️ NOT SAFE - Rain risk high. Keep yarn inside drying shed."
        safe_for_outdoor = False
    elif temp >= 30 and humidity < 65 and max_rain_prob <= 15:
        drying_status = "☀️ EXCELLENT - High heat, low humidity. Optimal for rapid, even sun-drying."
        safe_for_outdoor = True
    elif temp >= 24 and max_rain_prob <= 25:
        drying_status = "⛅ MODERATE - Suitable for drying, monitor sky for sudden clouds."
        safe_for_outdoor = True
    else:
        drying_status = "☁️ SLOW - High humidity or cool breeze. Drying will take longer."
        safe_for_outdoor = True

    return {
        "success": True,
        "source": source,
        "location": location.capitalize(),
        "temperature_c": temp,
        "apparent_temperature_c": apparent_temp,
        "relative_humidity_pct": humidity,
        "cloud_cover_pct": cloud_cov,
        "uv_index": uv,
        "is_day": is_day,
        "current_precipitation_mm": precip,
        "next_6h_rain_probability_pct": max_rain_prob,
        "wind_speed_kmh": wind,
        "wind_gusts_kmh": gusts,
        "safe_for_outdoor_drying": safe_for_outdoor,
        "drying_operational_status": drying_status,
        "recommendation_tanglish": (
            f"☀️ Maapla, {location.capitalize()}-la {temp}°C veyil irukku (feels like {apparent_temp}°C), rain chance only {max_rain_prob}%. "
            f"Dhaaralama hank yarn-a kaya vaikalaam!" if safe_for_outdoor else
            f"⚠️ Maapla, {location.capitalize()}-la {max_rain_prob}% rain chance irukku. Hank yarn-a veliya kaya vaikaatheenga!"
        )
    }


def generate_human_sensory_weather_speech(w: Dict[str, Any]) -> str:
    """
    Synthesizes a realistic, living human-spoken weather observation in Kongu Tanglish.
    Speaks like a real brother/co-founder who just stepped out onto the terrace.
    Strictly aligns with real-time temperature and actual time of day.
    """
    loc = w.get("location", "Karur")
    temp = round(w.get("temperature_c", 26.0), 1)
    apparent = round(w.get("apparent_temperature_c", temp), 1)
    humidity = w.get("relative_humidity_pct", 65)
    cloud = w.get("cloud_cover_pct", 30)
    rain_p = w.get("next_6h_rain_probability_pct", 10)
    gusts = round(w.get("wind_gusts_kmh", 12.0), 1)

    now_ist = datetime.now(IST_TZ)
    hour = now_ist.hour

    is_early_morning = 5 <= hour < 8
    is_morning = 8 <= hour < 11
    is_midday = 11 <= hour < 16
    is_evening = 16 <= hour < 19
    is_night = hour >= 19 or hour < 5

    time_context = (
        "Early morning wakeup (6-8 AM), fresh cool air" if is_early_morning else
        "Mid-morning (8-11 AM), daylight building" if is_morning else
        "Midday afternoon peak sun (11 AM - 4 PM)" if is_midday else
        "Evening dusk (4-7 PM), pleasant wind" if is_evening else
        "Night time, cool and quiet"
    )

    # 1. Primary: Dynamic LLM Generation for organic human speech
    try:
        import os
        from groq import Groq
        from pathlib import Path
        j_dir = Path(__file__).resolve().parent.parent
        if str(j_dir) not in sys.path:
            sys.path.insert(0, str(j_dir))
        import config
        api_key = os.getenv("GROQ_API_KEY") or getattr(config, "GROQ_API_KEY", "")
        if api_key:
            client = Groq(api_key=api_key)
            prompt = (
                f"You are Mukil's close brother, friend, and executive partner living in {loc}, Tamil Nadu.\n"
                f"You just stepped onto the terrace and felt the atmosphere.\n"
                f"Time of Day: {time_context} (Hour: {hour}:00 IST)\n"
                f"Real Live Metrics:\n"
                f"- City: {loc}\n"
                f"- Actual Temperature: {temp}°C, Feels-like {apparent}°C on skin\n"
                f"- Sky: {cloud}% cloud cover, Rain chance: {rain_p}%\n"
                f"- Air: {humidity}% humidity, Wind gusts: {gusts} km/h\n"
                f"Write a 2-3 sentence natural spoken Tanglish message to Mukil.\n"
                f"CRITICAL RULES:\n"
                f"- Speak ACCURATELY to the temperature: {temp}°C is pleasant/mild morning weather, NOT scorching heat! NEVER claim scorching heat unless temp >= 33°C in midday.\n"
                f"- DO NOT just read numbers like a robot.\n"
                f"- Mention how the sky and wind feel, give brotherly advice, and note if SGC hank yarn can dry outside.\n"
                f"- Use natural friendly Kongu/Tamil brotherly slang ('Mapla', 'Boss', 'velila paathen')."
            )
            r = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=600
            )
            msg = r.choices[0].message.content.strip() if r.choices and r.choices[0].message else ""
            if msg:
                return msg
    except Exception as e:
        logger.warning(f"LLM sensory speech fallback: {e}")

    # 2. Resilient Time-Aware Sensory Fallback
    if rain_p > 35:
        return (
            f"Mapla, velila terrace-la poi paathen, karumegham koodi irukku! Kaathum jillunu adikkudhu, "
            f"mazhai vara mari oru puzhukkam theriyudhu. SGC hank yarn-a velila potrundha odane shed-kulla maatha sollunga, "
            f"nananjita dyeing lot waste aagidum. Velila poradha irundha raincoat eduthuko mapla!"
        )

    if is_early_morning or (is_morning and temp <= 29):
        return (
            f"Mapla, velila terrace-la poi paathen, kaalaile kaathu nalla idhama chill-nu veesudhu! "
            f"Karur-la ipo {temp}°C thaan, feels-like {apparent}°C semma pleasant-ah irukku. "
            f"Veyil innum perusa suttu adikila, daylight nalla irukkuradhala SGC hank yarn-a dhaaralama velila kaya podalaam. "
            f"Nalla tea or coffee kudichitu fresh-ah day-a start pannu mapla!"
        )
    elif is_midday and temp >= 32:
        return (
            f"Mapla, velila paathen, uchiveyil nalla thalayila suttu adikira veyil! {temp}°C thaan, aana kaathula puzhudhi yerudhu, "
            f"feels-like {apparent}°C thalavali vara madhiri irukku. SGC hank yarn-a velila potrundha indha veyilukku sarakunu "
            f"super-ah kaanjirum! Aana nee velila bike-la poradha irundha cap or sunglass pottuko, nalla elaneer illa thanni kudi mapla!"
        )
    elif is_evening:
        return (
            f"Mapla, velila paathen, veyil adangi maalai kaathu nalla idhama veesudhu! {temp}°C irukku, "
            f"feels-like {apparent}°C. Hank yarn kaanjirundha eduthu shed-la adukka sollunga, "
            f"evening un tasks mudikka idhu romba comfortable climate mapla!"
        )
    elif is_night:
        return (
            f"Mapla, velila nalla amaidhiyaana jillu kaathu veesudhu, {temp}°C thaan irukku. "
            f"Day tasks mudichitu nalla rest edu mapla, namma naalaiku early-ah kalakkalaam!"
        )
    else:
        return (
            f"Mapla, velila weather semma pleasant-ah irukku! {temp}°C thaan, veyilum perusa illa, "
            f"nalla cool breeze veesudhu. Hank yarn drying nalla nadakkum, un tasks mudikka super climate mapla!"
        )


if __name__ == "__main__":
    res = get_live_weather_radar("karur")
    print(json.dumps(res, indent=2))
