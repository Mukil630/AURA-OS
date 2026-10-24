from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto('https://app.joinsuperset.com/join/#/', timeout=30000, wait_until='networkidle')
    page.wait_for_timeout(3000)
    page.locator('text=Start Registering').first.click()
    page.wait_for_timeout(3000)
    page.locator('text=I am here to apply for a job').first.click()
    page.wait_for_timeout(3000)
    
    print("Page URL:", page.url)
    inputs = page.locator('input').all()
    for i, inp in enumerate(inputs):
        try:
            p_holder = inp.get_attribute("placeholder")
            t_type = inp.get_attribute("type")
            name = inp.get_attribute("name")
            val = inp.input_value()
            vis = inp.is_visible()
            print(f"[{i}] type={t_type}, name={name}, placeholder={p_holder}, visible={vis}, val={val}")
        except Exception as e:
            pass
            
    print("\nVisible Buttons:")
    buttons = page.locator('button, a.btn').all()
    for b in buttons:
        if b.is_visible():
            print(f"Button: '{b.inner_text().strip()}'")
            
    page.screenshot(path=r"C:\Users\mukil\jarvis-core\storage\screenshots\superset_job_form_details.png")
    browser.close()
