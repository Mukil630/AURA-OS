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
COORDINATES = {
    "karur": (10.9601, 78.0766),
    "tirupur": (11.1085, 77.3411),
    "coimbatore": (11.0168, 76.9558),
    "erode": (11.3410, 77.7172),
    "dindigul": (10.3673, 77.9803)
}


def get_live_weather_radar(location: str = "karur") -> Dict[str, Any]:
    """
    Fetches real-time weather metrics and assesses outdoor hank yarn drying feasibility.
    
    Args:
        location: City in Tamil Nadu ('karur', 'tirupur', 'erode', 'coimbatore', 'dindigul')
    
    Returns:
        Structured weather data and SGC yarn sun-drying operational recommendation.
    """
    loc_key = location.lower().strip()
    lat, lon = COORDINATES.get(loc_key, COORDINATES["karur"])

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
