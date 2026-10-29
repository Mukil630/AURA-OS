# -*- coding: utf-8 -*-
import sys
from pathlib import Path

# Force UTF-8 stdout
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

JARVIS_DIR = Path(__file__).resolve().parent.parent
if str(JARVIS_DIR) not in sys.path:
    sys.path.insert(0, str(JARVIS_DIR))

from tools.weather_radar_tool import get_live_weather_radar, generate_human_sensory_weather_speech

print("=" * 75)
print("TEST 1: REAL-WORLD LIVE ATMOSPHERE RIGHT NOW IN KARUR")
print("=" * 75)
w1 = get_live_weather_radar("karur")
s1 = generate_human_sensory_weather_speech(w1)
print(f"Metrics: Temp: {w1['temperature_c']}°C (Feels: {w1['apparent_temperature_c']}°C) | Humidity: {w1['relative_humidity_pct']}% | Cloud: {w1['cloud_cover_pct']}% | Rain: {w1['next_6h_rain_probability_pct']}% | Gusts: {w1['wind_gusts_kmh']} km/h")
print("\n🗣️ Spoken Human Observation:\n" + s1)

print("\n" + "=" * 75)
print("TEST 2: SIMULATED SUDDEN HEAVY RAIN CLOUDS (MONSOON/STORM IN KARUR)")
print("=" * 75)
w2 = get_live_weather_radar("karur", manual_override={"temperature_c": 24.5, "rain_prob_pct": 85, "cloud_cover_pct": 95})
s2 = generate_human_sensory_weather_speech(w2)
print(f"Metrics: Temp: {w2['temperature_c']}°C | Rain: {w2['next_6h_rain_probability_pct']}% | Cloud: {w2['cloud_cover_pct']}%")
print("\n🗣️ Spoken Human Observation:\n" + s2)

print("\n" + "=" * 75)
print("TEST 3: REAL-WORLD COIMBATORE CLIMATE RIGHT NOW")
print("=" * 75)
w3 = get_live_weather_radar("coimbatore")
s3 = generate_human_sensory_weather_speech(w3)
print(f"Metrics: Temp: {w3['temperature_c']}°C (Feels: {w3['apparent_temperature_c']}°C) | Rain: {w3['next_6h_rain_probability_pct']}%")
print("\n🗣️ Spoken Human Observation:\n" + s3)

print("\n" + "=" * 75)
print("TEST 4: REAL-WORLD OOTY HILL STATION CLIMATE RIGHT NOW")
print("=" * 75)
w4 = get_live_weather_radar("ooty")
s4 = generate_human_sensory_weather_speech(w4)
print(f"Metrics: Temp: {w4['temperature_c']}°C (Feels: {w4['apparent_temperature_c']}°C) | Rain: {w4['next_6h_rain_probability_pct']}%")
print("\n🗣️ Spoken Human Observation:\n" + s4)
