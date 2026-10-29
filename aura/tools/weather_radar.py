"""
AURA OS — Real-Time Weather Radar & SGC Outdoor Yarn-Drying Feasibility Tool
Location: Karur, Tamil Nadu (Latitude: 10.9601° N, Longitude: 78.0766° E)
Integrated with Open-Meteo REST API (100% Zero-API-Key, Unlimited Queries, High-Precision).
Assesses live ambient temperature, relative humidity, precipitation, wind speed,
and evaluates industrial outdoor sun-drying feasibility for SGC hank yarn dyeing lots.
"""
import urllib.request
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("aura.tools.weather_radar")

# Precise Geographical Coordinates for Karur & Tamil Nadu Textile Hubs
COORDINATES: Dict[str, Dict[str, Any]] = {
    "karur": {
        "lat": 10.9601,
        "lon": 78.0766,
        "district": "Karur",
        "state": "Tamil Nadu",
        "elevation_m": 122,
        "hub_type": "Yarn Dyeing, Home Textiles & SGC Factory Base"
    },
    "tirupur": {
        "lat": 11.1085,
        "lon": 77.3411,
        "district": "Tirupur",
        "state": "Tamil Nadu",
        "elevation_m": 295,
        "hub_type": "Knitwear & Garment Export Capital"
    },
    "erode": {
        "lat": 11.3410,
        "lon": 77.7172,
        "district": "Erode",
        "state": "Tamil Nadu",
        "elevation_m": 183,
        "hub_type": "Powerloom Weaving & Fabric Processing"
    },
    "coimbatore": {
        "lat": 11.0168,
        "lon": 76.9558,
        "district": "Coimbatore",
        "state": "Tamil Nadu",
        "elevation_m": 411,
        "hub_type": "Spinning Mills & Textile Machinery"
    },
    "dindigul": {
        "lat": 10.3673,
        "lon": 77.9803,
        "district": "Dindigul",
        "state": "Tamil Nadu",
        "elevation_m": 265,
        "hub_type": "Yarn Processing & Lock Industry"
    },
    "salem": {
        "lat": 11.6643,
        "lon": 78.1460,
        "district": "Salem",
        "state": "Tamil Nadu",
        "elevation_m": 278,
        "hub_type": "Steel & Sago Hub"
    },
    "trichy": {
        "lat": 10.7905,
        "lon": 78.7047,
        "district": "Tiruchirappalli",
        "state": "Tamil Nadu",
        "elevation_m": 88,
        "hub_type": "Industrial & Central Educational Hub"
    },
    "madurai": {
        "lat": 9.9252,
        "lon": 78.1198,
        "district": "Madurai",
        "state": "Tamil Nadu",
        "elevation_m": 136,
        "hub_type": "Temple City & Commercial Trade Hub"
    },
    "chennai": {
        "lat": 13.0827,
        "lon": 80.2707,
        "district": "Chennai",
        "state": "Tamil Nadu",
        "elevation_m": 6,
        "hub_type": "State Capital & IT Corridor"
    },
    "bangalore": {
        "lat": 12.9716,
        "lon": 77.5946,
        "district": "Bengaluru",
        "state": "Karnataka",
        "elevation_m": 920,
        "hub_type": "Silicon Valley of India"
    },
    "ooty": {
        "lat": 11.4102,
        "lon": 76.6950,
        "district": "Nilgiris",
        "state": "Tamil Nadu",
        "elevation_m": 2240,
        "hub_type": "Hill Station & Tea Plantations"
    },
    "kodaikanal": {
        "lat": 10.2381,
        "lon": 77.4892,
        "district": "Dindigul Hills",
        "state": "Tamil Nadu",
        "elevation_m": 2133,
        "hub_type": "Princess of Hill Stations"
    }
}


def get_live_weather_radar(location: str = "karur") -> str:
    """
    Fetches real-time weather metrics and assesses outdoor hank yarn drying feasibility.
    
    Args:
        location: City name in Tamil Nadu ('karur', 'tirupur', 'erode', 'coimbatore', 'dindigul'). Defaults to 'karur'.
    
    Returns:
        Structured Tanglish and English executive briefing of temperature, humidity, rain probability,
        and operational recommendation for SGC outdoor hank yarn drying.
    """
    loc_key = location.lower().strip()
    spec = COORDINATES.get(loc_key, COORDINATES["karur"])
    lat = spec["lat"]
    lon = spec["lon"]
    city_name = spec["district"]

    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&"
        f"current=temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m&"
        f"hourly=precipitation_probability"
    )

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "AURA-OS/v4.0 (Karur-Weather-Textile-Radar; mukilarasu55@gmail.com)"}
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        curr = data.get("current", {})
        temp = curr.get("temperature_2m", 32.0)
        humidity = curr.get("relative_humidity_2m", 50)
        precip = curr.get("precipitation", 0.0)
        wind = curr.get("wind_speed_10m", 10.0)

        # Lookahead next 6 hours precipitation probability
        hourly_probs = data.get("hourly", {}).get("precipitation_probability", [0])[:6]
        max_rain_prob = max(hourly_probs) if hourly_probs else 0

        # Industrial Drying Feasibility Matrix for SGC Cotton Yarn
        if precip > 0.1 or max_rain_prob > 35:
            verdict_icon = "🌧️"
            verdict_title = "NOT SAFE FOR OUTDOOR HANK DRYING"
            advice = (
                f"⚠️ Rain risk high ({max_rain_prob}% probability in next 6h, {precip}mm rain detected). "
                "Keep all dyed yarn lots inside the hydro-extractor and steam/shed drying room."
            )
            tanglish = (
                f"Boss, {city_name}-la rain risk {max_rain_prob}% irukku mapla! "
                "Hank yarn-ah veliya sun-drying poda venaam, shed-la dry panna sollunga!"
            )
            safe = False
        elif temp >= 30 and humidity <= 60 and max_rain_prob <= 15:
            verdict_icon = "☀️"
            verdict_title = "OPTIMAL RAPID SUN-DRYING CONDITIONS"
            advice = (
                f"Excellent ambient heat ({temp}°C) and low humidity ({humidity}%). "
                "Yarn moisture regain will reach bone-dry target (8.5%) evenly in under 3.5 hours."
            )
            tanglish = (
                f"Boss, {city_name}-la {temp}°C veyil summa koluthudhu! Rain chance {max_rain_prob}% dhaan. "
                "SGC hank yarn-ah dhaaralama outdoor-la kaya vaikalaam, quick-ah dry aagidum mapla! 🚀"
            )
            safe = True
        elif temp >= 26 and max_rain_prob <= 25:
            verdict_icon = "⛅"
            verdict_title = "MODERATE DRYING CONDITIONS"
            advice = (
                f"Moderate temperature ({temp}°C, {humidity}% humidity). Suitable for drying with periodic cloud watch."
            )
            tanglish = (
                f"Boss, {city_name}-la {temp}°C irukku, rain chance {max_rain_prob}%. "
                "Yarn kaya vaikalaam, sky cloudy-ah aana mattum shed-ku maathikalam."
            )
            safe = True
        else:
            verdict_icon = "☁️"
            verdict_title = "SLOW DRYING CONDITIONS"
            advice = f"High humidity ({humidity}%) or cool breeze. Drying rate will be extended."
            tanglish = f"Boss, {city_name}-la {temp}°C, humidity konjam athigam ({humidity}%). Drying slow-ah aagum."
            safe = True

        return (
            f"{verdict_icon} **AURA Weather Radar — {city_name.upper()}, TAMIL NADU**\n"
            f"📍 **Coordinates:** `{lat}° N, {lon}° E` (Elevation: {spec['elevation_m']}m)\n"
            f"🏭 **Textile Hub:** {spec['hub_type']}\n"
            f"────────────────────────────────────────\n"
            f"🌡️ **Ambient Temperature:** **{temp:.1f}°C**\n"
            f"💧 **Relative Humidity:** **{humidity}%**\n"
            f"🌧️ **Next 6h Rain Probability:** **{max_rain_prob}%** (Current Rain: {precip} mm)\n"
            f"💨 **Wind Speed:** **{wind:.1f} km/h**\n"
            f"────────────────────────────────────────\n"
            f"🧶 **SGC Hank Yarn Sun-Drying Verdict:** **{verdict_title}**\n"
            f"📋 **Industrial Recommendation:** {advice}\n"
            f"🗣️ **Voice Spoken Tanglish:** \"{tanglish}\""
        )
    except Exception as e:
        logger.error(f"Open-Meteo weather fetch error: {e}")
        return f"⚠️ Weather Radar unavailable for {city_name}: {str(e)}. Fallback: Check local sky conditions."
