from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto('https://careers.zohocorp.com/jobs/Careers', timeout=30000, wait_until='networkidle')
    page.wait_for_timeout(3000)
    
    # Print job titles
    jobs = page.locator('a[href*="/jobs/Careers/"]').all()
    print("Found Zoho jobs:", len(jobs))
    for j in jobs[:15]:
        title = j.inner_text().strip()
        link = j.get_attribute('href')
        if title:
            print(f"- {title} -> {link}")
            
    page.screenshot(path=r"C:\Users\mukil\jarvis-core\storage\screenshots\zoho_real_jobs.png")
    browser.close()
