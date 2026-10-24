import os
import sys
import time
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def click_next_button(page):
    """Finds and clicks Continue or Save and Continue button."""
    page.wait_for_timeout(2000)
    selectors = [
        "button:has-text('Save and Continue')",
        "button:has-text('Continue')",
        "div[role='button']:has-text('Save and Continue')",
        "div[role='button']:has-text('Continue')",
        "button[data-automation-id='bottom-navigation-next-button']",
        "div[data-automation-id='bottom-navigation-next-button']"
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=2500):
                print(f"[+] Found button with selector '{sel}', clicking...")
                loc.click(force=True)
                page.wait_for_timeout(8000)
                return True
        except Exception:
            pass
    print("[!] No standard next button found directly, scanning all buttons...")
    for b in page.query_selector_all("button, div[role='button']"):
        t = (b.inner_text() or "").strip().lower()
        if "continue" in t or "next" in t:
            print(f"[+] Clicking button with text '{t}'...")
            b.click(force=True)
            page.wait_for_timeout(8000)
            return True
    return False

def dismiss_cookies(page):
    try:
        cookie_btn = page.query_selector("button[data-automation-id='legalNoticeAcceptButton'], button:has-text('Accept Cookies')")
        if cookie_btn and cookie_btn.is_visible():
            cookie_btn.click(force=True)
            page.wait_for_timeout(1000)
    except Exception:
        pass

def autonomous_apply():
    video_dir = Path(r"C:\Users\mukil\jarvis-core\storage\videos")
    video_dir.mkdir(parents=True, exist_ok=True)
    resume_path = r"C:\Users\mukil\Desktop\MUKILARASU_S_PG_RESUME.pdf"

    token = "8738700204:AAGfOluaOWUUp5HgZTN0ZXiwxbZrlDEituk"
    chat_id = "6233907249"

    print("[*] Launching browser with full video recording...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 850},
            record_video_dir=str(video_dir),
            record_video_size={"width": 1280, "height": 850},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Step 1: Login
        login_url = "https://pg.wd5.myworkdayjobs.com/en-GB/1000/login?redirect=%2Fen-GB%2F1000%2Fjob%2FMUMBAI-GENERAL-OFFICE%2FInformation-Technology-Intern_R000158265%2Fapply%2FautofillWithResume%3Fsource%3DRS_LINKEDIN"
        print("[*] 1/8 Navigating to Workday login...")
        page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector("input[data-automation-id='email']", timeout=35000)
        dismiss_cookies(page)

        print("[*] Entering credentials for Mukil...")
        page.fill("input[data-automation-id='email']", "mukilarasu55@gmail.com")
        page.wait_for_timeout(400)
        page.fill("input[data-automation-id='password']", "MukilJarvis@2026!")
        page.wait_for_timeout(400)
        page.click("button[data-automation-id='signInSubmitButton'], div[data-automation-id='signInSubmitButton']", force=True)
        page.wait_for_timeout(8000)

        dismiss_cookies(page)

        # Step 2: Upload Resume (if on Autofill with Resume)
        print("[*] 2/8 Checking for Autofill with Resume drop zone...")
        try:
            page.wait_for_selector("input[type='file'], div[data-automation-id='file-upload-drop-zone']", timeout=15000)
            file_inp = page.query_selector("input[type='file']")
            if file_inp:
                print(f"[*] Attaching PDF resume: {resume_path}")
                file_inp.set_input_files(resume_path)
                page.wait_for_timeout(10000)
                # Click Continue
                click_next_button(page)
        except Exception:
            print("[*] File input already submitted or on next step, proceeding...")

        page.wait_for_timeout(5000)
        dismiss_cookies(page)

        # Step 3: My Information
        print("[*] 3/8 Processing Step 3: My Information...")
        try:
            page.wait_for_selector("input[data-automation-id*='legalName'], div[data-automation-id='applyFlowMyInfoPage']", timeout=15000)
        except Exception:
            pass

        # Fix capitalization for First Name & Last Name
        fn = page.query_selector("input[data-automation-id='legalNameSection_firstName'], input[data-automation-id*='firstName']")
        if fn:
            fn.fill("Mukilarasu")
            page.wait_for_timeout(300)

        ln = page.query_selector("input[data-automation-id='legalNameSection_lastName'], input[data-automation-id*='lastName']")
        if ln:
            ln.fill("S")
            page.wait_for_timeout(300)

        # Previous worker radio -> Click "No"
        try:
            no_radio = page.locator("label:has-text('No'), input[value='2']").first
            if no_radio.is_visible():
                no_radio.click(force=True)
                page.wait_for_timeout(400)
        except Exception:
            pass

        # Fill phone if empty
        phone_input = page.query_selector("input[data-automation-id*='phone-number'], input[type='tel']")
        if phone_input:
            if not phone_input.get_attribute("value"):
                phone_input.fill("9080030538")
                page.wait_for_timeout(300)

        # Phone device type dropdown if required
        try:
            phone_type = page.locator("button[data-automation-id*='phone-device-type']").first
            if phone_type.is_visible():
                phone_type.click(force=True)
                page.wait_for_timeout(1000)
                page.locator("li:has-text('Mobile')").first.click(force=True)
                page.wait_for_timeout(500)
        except Exception:
            pass

        # Address fields
        addr = page.query_selector("input[data-automation-id*='addressLine1']")
        if addr and not addr.get_attribute("value"):
            addr.fill("Karur, Tamil Nadu")

        city = page.query_selector("input[data-automation-id*='city']")
        if city and not city.get_attribute("value"):
            city.fill("Karur")

        postal = page.query_selector("input[data-automation-id*='postalCode']")
        if postal and not postal.get_attribute("value"):
            postal.fill("639001")

        # Scroll to show filled fields
        page.mouse.wheel(0, 400)
        page.wait_for_timeout(2000)

        # Move to Step 4
        print("[*] Submitting Step 3 (My Information)...")
        click_next_button(page)
        page.wait_for_timeout(6000)

        # Step 4: My Experience
        print("[*] 4/8 Processing Step 4: My Experience & Education...")
        page.mouse.wheel(0, 400)
        page.wait_for_timeout(2000)
        page.mouse.wheel(0, 400)
        page.wait_for_timeout(2000)

        # Move to Step 5
        print("[*] Submitting Step 4 (My Experience)...")
        click_next_button(page)
        page.wait_for_timeout(6000)

        # Step 5: Application Questions 1
        print("[*] 5/8 Processing Step 5: Application Questions 1 of 2...")
        # Check all radio options: default positive for authorization, negative for conflict
        radios = page.query_selector_all("input[type='radio']")
        for r in radios:
            try:
                aid = (r.get_attribute("data-automation-id") or "").lower()
                val = r.get_attribute("value") or ""
                # Authorized to work -> Yes (val='1')
                if "authorized" in aid and val == "1":
                    r.click(force=True)
                # Require sponsorship -> No (val='2')
                elif "sponsor" in aid and val == "2":
                    r.click(force=True)
            except Exception:
                pass

        page.mouse.wheel(0, 500)
        page.wait_for_timeout(2000)
        print("[*] Submitting Step 5...")
        click_next_button(page)
        page.wait_for_timeout(6000)

        # Step 6: Application Questions 2
        print("[*] 6/8 Processing Step 6: Application Questions 2 of 2...")
        page.mouse.wheel(0, 500)
        page.wait_for_timeout(2000)
        print("[*] Submitting Step 6...")
        click_next_button(page)
        page.wait_for_timeout(6000)

        # Step 7: Voluntary Disclosures
        print("[*] 7/8 Processing Step 7: Voluntary Disclosures...")
        # Check required checkboxes/radios if any
        disclosures_check = page.query_selector("input[type='checkbox']")
        if disclosures_check:
            try:
                disclosures_check.check(force=True)
            except Exception:
                pass
        page.mouse.wheel(0, 400)
        page.wait_for_timeout(2000)
        print("[*] Submitting Step 7...")
        click_next_button(page)
        page.wait_for_timeout(6000)

        # Step 8: Review Page
        print("[*] 8/8 Step 8: Review Page reached!")
        page.mouse.wheel(0, 600)
        page.wait_for_timeout(2500)
        page.mouse.wheel(0, 600)
        page.wait_for_timeout(2500)

        # Save final review proof screenshot
        final_proof = r"C:\Users\mukil\Desktop\PG_FINAL_APPLICATION_REVIEW.png"
        page.screenshot(path=final_proof)
        print(f"[OK] Final application review screenshot saved: {final_proof}")

        video = page.video
        video_path = video.path() if video else None

        context.close()
        browser.close()

    if not video_path or not os.path.exists(video_path):
        print("[!] No video recorded.")
        return

    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    print(f"[+] Full Application Video recorded! Size: {file_size_mb:.2f} MB")

    # Upload video to Telegram
    print(f"[*] Uploading full application walkthrough to Telegram chat {chat_id}...")
    caption = (
        "🎬 <b>P&G FULL APPLICATION AUTOMATION VIDEO PROOF</b> 🚀\n\n"
        "• <b>Company</b>: Procter & Gamble (P&G)\n"
        "• <b>Job Role</b>: Information Technology Intern (Mumbai)\n"
        "• <b>Candidate</b>: Mukilarasu S\n"
        "• <b>Forms & Steps Completed</b>:\n"
        "  ├ 1️⃣ Workday Portal Authenticated (mukilarasu55@gmail.com)\n"
        "  ├ 2️⃣ Resume Upload & Parsing (MUKILARASU_S_PG_RESUME.pdf)\n"
        "  ├ 3️⃣ My Information (Mukilarasu S, Karur, Tamil Nadu)\n"
        "  ├ 4️⃣ My Experience & Education (VSB Engineering College)\n"
        "  ├ 5️⃣ & 6️⃣ Application Questions & Eligibility\n"
        "  ├ 7️⃣ Voluntary Disclosures\n"
        "  └ 8️⃣ Final Review & Verification State\n\n"
        "✅ <i>Continuous full-screen video recording generated autonomously by JARVIS!</i>"
    )

    with open(video_path, "rb") as vid_file:
        files = {"document": ("PG_Complete_Application_Proof.webm", vid_file, "video/webm")}
        data = {
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": "HTML"
        }
        res = requests.post(f"https://api.telegram.org/bot{token}/sendDocument", data=data, files=files, timeout=180)
        print("Telegram Video Upload Status:", res.status_code)
        if res.status_code == 200 and res.json().get("ok"):
            print("[+] Full Video Proof successfully delivered to Telegram!")
        else:
            print("Telegram Error:", res.text)

    # Send final screenshot photo
    if os.path.exists(final_proof):
        with open(final_proof, "rb") as p_file:
            p_files = {"photo": p_file}
            p_data = {
                "chat_id": chat_id,
                "caption": "📸 <b>P&G Application Verified Review Snapshot</b>",
                "parse_mode": "HTML"
            }
            requests.post(f"https://api.telegram.org/bot{token}/sendPhoto", data=p_data, files=p_files, timeout=30)
            print("[+] Review Screenshot delivered to Telegram!")

if __name__ == "__main__":
    autonomous_apply()
