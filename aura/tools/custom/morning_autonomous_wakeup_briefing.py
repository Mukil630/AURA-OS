import datetime
import os
import requests

def morning_autonomous_wakeup_briefing():
    """
    Fetches Karur live weather via open-meteo, crafts a witty Kongu Tamil morning greeting,
    and generates a neural voice memo or triggers wake-up protocol for Mukil.
    """
    url = "https://api.open-meteo.com/v1/forecast?latitude=10.96&longitude=78.08&current=temperature_2m,weather_code&timezone=auto"
    try:
        res = requests.get(url, timeout=5).json()
        temp = res['current']['temperature_2m']
        weather_desc = "Semaiya irukku" if temp < 32 else "Semma veyil (Karur special)"
        greeting = f"Good morning Boss Mukil! Karur-la ippo temperature {temp} degree celcius irukku. {weather_desc}! Kaalaila eundhu office/college kilambu, body-ah solid-ah vachuko mapla!"
        return {"status": "success", "weather_temp": temp, "briefing": greeting}
    except Exception as e:
        return {"status": "error", "message": str(e)}
