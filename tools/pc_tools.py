import os
import subprocess
import json
from datetime import datetime

def run_powershell(command: str) -> str:
    """Executes a PowerShell command on the Windows PC and returns the output."""
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=30
        )
        out = res.stdout.strip()
        err = res.stderr.strip()
        if out and err:
            return f"{out}\nErrors:\n{err}"
        return out or err or "Command executed successfully with no output."
    except Exception as e:
        return f"Execution error: {str(e)}"

def open_browser_url(url: str) -> str:
    """Opens any website URL in the browser on Mukil's PC."""
    try:
        if not url.startswith("http"):
            url = "https://" + url
        subprocess.run(["powershell", "-NoProfile", "-Command", f'Start-Process "{url}"'], capture_output=True, text=True)
        return f"Successfully opened {url} in your PC browser!"
    except Exception as e:
        return f"Failed to open browser: {str(e)}"

def create_folder(folder_path: str) -> str:
    """Creates a new folder at the given path on the PC."""
    try:
        os.makedirs(folder_path, exist_ok=True)
        return f"Folder successfully created at: {folder_path}"
    except Exception as e:
        return f"Failed to create folder: {str(e)}"

def write_text_file(file_path: str, content: str) -> str:
    """Creates or overwrites a text file with content on the PC."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"File written successfully to: {file_path} ({len(content)} chars)"
    except Exception as e:
        return f"Failed to write file: {str(e)}"

def read_text_file(file_path: str) -> str:
    """Reads the content of a text file from the PC."""
    try:
        if not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(4000)
            return content if content else "File is empty."
    except Exception as e:
        return f"Failed to read file: {str(e)}"

def list_files(directory_path: str) -> str:
    """Lists files and folders in a given directory path on the PC."""
    try:
        if not os.path.exists(directory_path):
            return f"Directory not found: {directory_path}"
        items = os.listdir(directory_path)[:25]
        return "\n".join(items) if items else "Directory is empty."
    except Exception as e:
        return f"Failed to list directory: {str(e)}"

def send_whatsapp_message(contact_name: str, message: str) -> str:
    """Automates opening WhatsApp desktop, searching for contact, and sending message."""
    try:
        import time
        import pyautogui
        pyautogui.FAILSAFE = False
        
        # Step 1: Open WhatsApp Desktop
        os.system("start whatsapp:")
        time.sleep(3.5)
        
        # Step 2: Search contact
        pyautogui.hotkey("ctrl", "f")
        time.sleep(1.2)
        pyautogui.write(contact_name, interval=0.1)
        time.sleep(2.0)
        
        # Step 3: Open chat
        pyautogui.press("enter")
        time.sleep(1.2)
        
        # Step 4: Type message and send
        pyautogui.write(message, interval=0.1)
        time.sleep(0.8)
        pyautogui.press("enter")
        
        return f"WhatsApp message '{message}' successfully sent to '{contact_name}'!"
    except Exception as e:
        return f"Failed to send WhatsApp message: {str(e)}"

def set_screen_brightness(level: int) -> str:
    """Sets screen brightness level from 0 to 100%."""
    try:
        import screen_brightness_control as sbc
        level = max(0, min(100, int(level)))
        sbc.set_brightness(level)
        return f"Screen brightness successfully set to {level}%!"
    except Exception as e:
        try:
            cmd = f"(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {level})"
            subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True)
            return f"Screen brightness set to {level}% via WMI."
        except Exception as err:
            return f"Failed to set brightness: {str(e)} | {str(err)}"

def get_screen_brightness() -> str:
    """Gets the current screen brightness level."""
    try:
        import screen_brightness_control as sbc
        current = sbc.get_brightness()
        return f"Current screen brightness is {current}%."
    except Exception as e:
        return f"Failed to get brightness: {str(e)}"

def set_system_volume(level: int) -> str:
    """Sets PC system master volume from 0 to 100%."""
    try:
        from pycaw.pycaw import AudioUtilities
        speakers = AudioUtilities.GetSpeakers()
        volume = speakers.EndpointVolume
        level = max(0, min(100, int(level)))
        volume.SetMasterVolumeLevelScalar(level / 100.0, None)
        return f"System master volume set to {level}%!"
    except Exception as e:
        return f"Failed to set volume: {str(e)}"

def take_pc_screenshot(save_path: str = None) -> str:
    """Takes a screenshot of the PC screen and returns the saved file path."""
    try:
        import tempfile
        import pyautogui
        pyautogui.FAILSAFE = False
        if not save_path:
            save_path = os.path.join(tempfile.gettempdir(), f"screenshot_{int(datetime.now().timestamp())}.png")
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        img = pyautogui.screenshot()
        img.save(save_path)
        return f"Screenshot saved successfully at: {save_path}"
    except Exception as e:
        return f"Failed to take screenshot: {str(e)}"

def lock_workstation() -> str:
    """Locks the Windows PC immediately."""
    try:
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        return "PC locked successfully!"
    except Exception as e:
        return f"Failed to lock PC: {str(e)}"

def apply_indeed_jobs(keywords: str = "Software Engineer", location: str = "Remote", max_applications: int = 3) -> str:
    """Automates searching and applying for job openings on Indeed India."""
    try:
        from agents.placement_agent import PlacementAgent
        agent = PlacementAgent()
        return agent.apply_on_indeed(keywords=keywords, location=location, max_applications=max_applications, headless=False)
    except Exception as e:
        return f"Failed to run Indeed job applier: {str(e)}"

def play_youtube_song(query: str) -> str:
    """Searches and opens a song or video on YouTube in Google Chrome."""
    try:
        import urllib.parse
        import subprocess
        
        query_clean = query.lower().strip()
        if "believer" in query_clean:
            url = "https://www.youtube.com/watch?v=7wtfhZwyrcc"
        else:
            encoded = urllib.parse.quote(query)
            url = f"https://www.youtube.com/results?search_query={encoded}"
        
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if os.path.exists(chrome_path):
            subprocess.Popen([chrome_path, url])
        else:
            subprocess.run(["powershell", "-Command", f'Start-Process "{url}"'], capture_output=True, text=True)
            
        return f"Google Chrome opened YouTube and started playing '{query}'!"
    except Exception as e:
        return f"Failed to play song on YouTube: {str(e)}"

def browser_search(query: str) -> str:
    """Uses the autonomous browser agent to search Google and extract top links and summaries."""
    try:
        from tools.browser_agent import AutonomousBrowserAgent
        agent = AutonomousBrowserAgent()
        return agent.search_web(query=query, max_results=4, headless=False)
    except Exception as e:
        return f"Browser search error: {str(e)}"

def browser_open_and_screenshot(url: str) -> str:
    """Navigates to a webpage in Chrome, captures a screenshot, and saves it."""
    try:
        from tools.browser_agent import AutonomousBrowserAgent
        agent = AutonomousBrowserAgent()
        return agent.browse_and_screenshot(url=url, headless=False)
    except Exception as e:
        return f"Browser screenshot error: {str(e)}"

def browser_read_page(url: str) -> str:
    """Visits any website and extracts its readable text content."""
    try:
        from tools.browser_agent import AutonomousBrowserAgent
        agent = AutonomousBrowserAgent()
        return agent.extract_page_summary(url=url, headless=False)
    except Exception as e:
        return f"Browser read error: {str(e)}"

def browser_auto_fill_form(url: str) -> str:
    """Navigates to a website/form and auto-fills input fields with Mukil's profile details."""
    try:
        from tools.browser_agent import AutonomousBrowserAgent
        agent = AutonomousBrowserAgent()
        return agent.auto_fill_web_form(url=url, headless=False)
    except Exception as e:
        return f"Browser form filler error: {str(e)}"

def auto_apply_job(company: str, role: str = "AI Engineer", url: str = None) -> str:
    """Autonomous Placement Auto-Apply: Fills form, attaches Mukil's PDF resume, captures live screenshot, and returns summary."""
    try:
        from tools.career_auto_apply import CareerAutoApplyEngine
        engine = CareerAutoApplyEngine()
        res = engine.execute_auto_apply(company=company, role=role, portal_url=url, headless=True)
        return res.get("summary", f"Application submitted for {company}!") + f"\nScreenshot saved successfully at: {res.get('screenshot_path')}"
    except Exception as e:
        return f"Auto-apply error for {company}: {str(e)}"







