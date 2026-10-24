from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto('https://indiacampus.accenture.com/', timeout=30000, wait_until='networkidle')
    page.wait_for_timeout(3000)
    
    print("Accenture Title:", page.title())
    print("Accenture URL:", page.url)
    print("Body text snippet:\n", page.locator('body').inner_text()[:1000])
    
    links = page.locator('a, button').all()
    for l in links:
        t = l.inner_text().strip()
        h = l.get_attribute('href')
        if t and any(k in t.lower() for k in ['apply', 'register', 'job', 'hire', 'candidate', 'login']):
            print(f"Action link: '{t}' -> {h}")
            
    page.screenshot(path=r"C:\Users\mukil\jarvis-core\storage\screenshots\accenture_live_portal.png")
    browser.close()
