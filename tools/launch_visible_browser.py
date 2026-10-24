from playwright.sync_api import sync_playwright
import time
import sys

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

print("🚀 LAUNCHING REAL VISIBLE CHROMIUM ON MUKIL'S MONITOR...", flush=True)

p = sync_playwright().start()
browser = p.chromium.launch(
    headless=False,
    args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
)
context = browser.new_context(no_viewport=True)
page = context.new_page()

print("🌐 Navigating to Google...", flush=True)
page.goto("https://www.google.com")
time.sleep(2)

print("✍️ Typing search query in real-time...", flush=True)
search_box = page.locator("textarea[name='q'], input[name='q']")
if search_box.count() > 0:
    search_box.first.click()
    search_box.first.type("Sri Ganapathi Colours Mukil JARVIS AI", delay=80)
    time.sleep(1)
    search_box.first.press("Enter")

print("👀 Browser is visible on screen! Keeping open for 10 seconds...", flush=True)
time.sleep(10)

browser.close()
p.stop()
print("🎉 Visible browser test finished successfully!", flush=True)
