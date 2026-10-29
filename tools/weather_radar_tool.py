"""
Karur & Textile Hub Live Weather & Outdoor Hank-Drying Radar
tools/weather_radar_tool.py - 100% Free Open-Meteo REST API integration.
Fetches real-time temperature, humidity, precipitation probability, and wind speed.
Evaluates industrial outdoor sun-drying feasibility for SGC yarn dyeing operations.
"""
import urllib.request
import json
import logging
from typing import Dict, Any

logger = logging.getLogger("weather_radar_tool")

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


def get_live_weather_radar(location: str = "karur", manual_override: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Fetches real-time weather metrics and assesses outdoor hank yarn drying feasibility.
    Supports dynamic city selection across Tamil Nadu and manual override simulation.
    
    Args:
        location: City ('karur', 'coimbatore', 'tirupur', 'erode', 'salem', 'trichy', 'chennai', 'bangalore', etc.)
        manual_override: Optional dict to simulate custom temp/rain for testing.
    
    Returns:
        Structured weather data and SGC yarn sun-drying operational recommendation.
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

    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&"
        f"current=temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m&"
        f"hourly=precipitation_probability"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AURA-SGC-TextileEngine/2.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        curr = data.get("current", {})
        temp = curr.get("temperature_2m", 32.0)
        humidity = curr.get("relative_humidity_2m", 50)
        precip = curr.get("precipitation", 0.0)
        wind = curr.get("wind_speed_10m", 10.0)

        # Get max rain probability in next 6 hours
        hourly_probs = data.get("hourly", {}).get("precipitation_probability", [0])[:6]
        max_rain_prob = max(hourly_probs) if hourly_probs else 0

        # Apply manual simulation overrides if active
        if manual_override:
            if manual_override.get("temperature_c") is not None:
                temp = float(manual_override["temperature_c"])
            if manual_override.get("humidity_pct") is not None:
                humidity = int(manual_override["humidity_pct"])
            if manual_override.get("rain_prob_pct") is not None:
                max_rain_prob = int(manual_override["rain_prob_pct"])

        # Assess Hank Drying Suitability
        if precip > 0 or max_rain_prob > 35:
            drying_status = "⚠️ NOT SAFE - Rain risk high. Keep yarn inside drying shed."
            safe_for_outdoor = False
        elif temp >= 30 and humidity < 65 and max_rain_prob <= 15:
            drying_status = "☀️ EXCELLENT - High heat, low humidity. Optimal for rapid, even sun-drying."
            safe_for_outdoor = True
        elif temp >= 26 and max_rain_prob <= 25:
            drying_status = "⛅ MODERATE - Suitable for drying, monitor sky for sudden clouds."
            safe_for_outdoor = True
        else:
            drying_status = "☁️ SLOW - High humidity or cool breeze. Drying will take longer."
            safe_for_outdoor = True

        return {
            "success": True,
            "location": location.capitalize(),
            "temperature_c": temp,
            "relative_humidity_pct": humidity,
            "current_precipitation_mm": precip,
            "next_6h_rain_probability_pct": max_rain_prob,
            "wind_speed_kmh": wind,
            "safe_for_outdoor_drying": safe_for_outdoor,
            "drying_operational_status": drying_status,
            "recommendation_tanglish": (
                f"☀️ Maapla, {location.capitalize()}-la {temp}°C veyil irukku, rain chance only {max_rain_prob}%. "
                f"Dhaaralama hank yarn-a kaya vaikalaam!" if safe_for_outdoor else
                f"⚠️ Maapla, {location.capitalize()}-la {max_rain_prob}% rain chance irukku. Hank yarn-a veliya kaya vaikaatheenga!"
            )
        }
    except Exception as e:
        logger.error(f"Weather API error: {e}")
        return {
            "success": False,
            "error": str(e),
            "location": location.capitalize(),
            "fallback_note": "Could not reach Open-Meteo API. Check local weather radar."
        }


if __name__ == "__main__":
    res = get_live_weather_radar("karur")
    print(json.dumps(res, indent=2))
