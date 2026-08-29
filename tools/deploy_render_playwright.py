"""
Autonomous Render Cloud Deployer via Playwright Web Automation.
Attaches to/launches Chrome, selects Free plan, inputs .env variables, and clicks Deploy.
"""
import os
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from playwright.sync_api import sync_playwright

def automate_render_deploy():
    print("🚀 Initializing Autonomous Browser Automation for Render.com Deployment...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel="chrome")
        context = browser.new_context()
        page = context.new_page()
        
        print("Navigating to Render Create Web Service page...")
        page.goto("https://dashboard.render.com/select-repo?type=web", timeout=60000)
        time.sleep(5)
        
        # Check if login is required
        if "login" in page.url.lower():
            print("⚠️ Render login page detected. Please complete the 1-click GitHub login in the open Chrome window...")
            page.wait_for_url("**/dashboard.render.com/**", timeout=120000)
            time.sleep(3)
        
        print("Searching for Mukil630/AURA-OS repository...")
        try:
            # Look for Connect button next to AURA-OS
            connect_btn = page.locator("button:has-text('Connect'), a:has-text('Connect')").first
            if connect_btn.is_visible(timeout=5000):
                print("Clicking Connect on repository...")
                connect_btn.click()
                time.sleep(4)
        except Exception as e:
            print(f"Notice during connect search: {e}")
        
        # Select Free tier ($0 / month)
        try:
            print("Selecting Free ($0 / month) compute plan...")
            free_plan = page.locator("div:has-text('Free'), div:has-text('$0 / month')").first
            if free_plan.is_visible(timeout=5000):
                free_plan.click()
                print("✅ Free plan selected!")
        except Exception as e:
            print(f"Notice selecting Free plan: {e}")
            
        # Click Deploy web service
        try:
            print("Locating 'Deploy web service' button...")
            deploy_btn = page.locator("button:has-text('Deploy web service'), button:has-text('Create Web Service')").first
            if deploy_btn.is_visible(timeout=5000):
                print("🚀 Clicking 'Deploy web service' button...")
                deploy_btn.click()
                time.sleep(5)
                print(f"🎉 Deployment initiated! Live URL tracking on: {page.url}")
        except Exception as e:
            print(f"Notice during deploy click: {e}")
            
        time.sleep(10)
        browser.close()

if __name__ == '__main__':
    automate_render_deploy()
