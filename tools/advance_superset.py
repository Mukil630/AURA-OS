from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto('https://app.joinsuperset.com/join/#/', timeout=30000, wait_until='networkidle')
    page.wait_for_timeout(2000)
    page.locator('text=Start Registering').first.click()
    page.wait_for_timeout(2000)
    
    # Click the second radio option
    radios = page.locator('input[type="radio"]').all()
    print("Found radios:", len(radios))
    if len(radios) >= 2:
        radios[1].check(force=True)
        print("Checked radio 1 (SIGN_UP)")
        
    page.wait_for_timeout(1000)
    
    # Click Save and Proceed
    btn = page.locator('button:has-text("Save and Proceed")').first
    if btn.is_visible():
        print("Clicking Save and Proceed...")
        btn.click()
        page.wait_for_timeout(3000)
        
    print("Current URL:", page.url)
    print("Step 2 text snippet:", page.locator('body').inner_text()[:600])
    page.screenshot(path=r"C:\Users\mukil\jarvis-core\storage\screenshots\superset_step2_active.png")
    browser.close()
