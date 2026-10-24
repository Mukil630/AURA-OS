from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto('https://app.joinsuperset.com/join/#/', timeout=30000, wait_until='networkidle')
    page.wait_for_timeout(2000)
    page.locator('text=Start Registering').first.click()
    page.wait_for_timeout(2000)
    
    # Dump HTML of the form container
    form_html = page.locator('form, .content, .main-content, #main').first.inner_html()
    print("Form HTML:\n", form_html[:1500])
    browser.close()
