import requests

def morning_autonomous_wakeup_briefing():
    """
    Fetches Karur live weather via open-meteo, crafts a witty brotherly Kongu slang 
    morning greeting using the MORNING_WAKEUP voice persona style.
    """
    url = "https://api.open-meteo.com/v1/forecast?latitude=10.96&longitude=78.08&current=temperature_2m,weather_code&timezone=auto"
    try:
        res = requests.get(url, timeout=5).json()
        temp = res['current']['temperature_2m']
        weather_desc = "Semaiya irukku" if temp < 32 else "Semma veyil polachikadhu Karur-la"
        
        # Brotherly Kongu Slang Morning Briefing (MORNING_WAKEUP Persona)
        greeting = f"Good morning Boss Mukil! Karur-la ippo temperature {temp} degree celcius irukku. {weather_desc}! Kaalaila eundhu coffee-ya kudi, alapparai-ah start pannu mapla! Day solid-ah pogattum!"
        return {"status": "success", "weather_temp": temp, "briefing": greeting, "persona": "MORNING_WAKEUP"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
