from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto('https://app.joinsuperset.com/join/#/', timeout=30000, wait_until='networkidle')
    page.wait_for_timeout(2000)
    page.locator('div[ng-click*="startRegistration"]').first.click()
    page.wait_for_timeout(2000)
    
    # Print all labels and inputs in basicInfoForm
    form = page.locator('form[name="basicInfoForm"]')
    print("Found basicInfoForm?", form.count())
    labels = form.locator('label').all()
    for l in labels:
        print("Label:", l.inner_text().strip())
    inputs = form.locator('input, select, textarea').all()
    for inp in inputs:
        print(f"Input: name={inp.get_attribute('name')}, type={inp.get_attribute('type')}, placeholder={inp.get_attribute('placeholder')}")
    browser.close()
