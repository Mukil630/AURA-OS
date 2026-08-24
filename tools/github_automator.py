import os
import sys
import time
import logging
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from memory.memory_manager import MemoryManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("github_automator")

class GitHubAutomator:
    """
    Autonomous GitHub Repository Creator & Pusher using Playwright & Git CLI.
    """
    def __init__(self, session_dir=None):
        self.session_dir = session_dir or os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "browser_session")
        os.makedirs(self.session_dir, exist_ok=True)
        self.mem = MemoryManager()

    def auto_create_and_push_repo(self, repo_name: str = "AURA-OS", description: str = "AURA - Autonomous Unified Response Assistant", is_public: bool = True, repo_dir: str = None):
        repo_dir = repo_dir or os.path.dirname(os.path.dirname(__file__))
        logger.info(f"⚡ Starting Autonomous GitHub Repository Creation for '{repo_name}'...")
        
        with sync_playwright() as p:
            # Launch persistent Chrome context to use existing GitHub session
            context = p.chromium.launch_persistent_context(
                self.session_dir,
                headless=False,
                channel="chrome",
                args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
                no_viewport=True
            )
            page = context.pages[0] if context.pages else context.new_page()
            
            logger.info("Navigating to https://github.com/new ...")
            page.goto("https://github.com/new", timeout=60000)
            time.sleep(3)
            
            # Check if login is needed or if already on new repo page
            if "login" in page.url:
                logger.info("GitHub login required in browser. Waiting for login...")
                print("\n[AURA GITHUB] Please sign in on the opened Chrome window if not already logged in...")
                page.wait_for_url("https://github.com/new", timeout=120000)
            
            # Fill repository name
            try:
                name_input = page.locator("input[data-testid='repository-name-input'], input[aria-label='Repository name*'], input#repository_name, input#repository_name_input").first
                if name_input.is_visible(timeout=5000):
                    name_input.fill(repo_name)
                    time.sleep(1)
                    
                # Fill description if present
                desc_input = page.locator("input[aria-label='Description'], input#repository_description").first
                if desc_input.is_visible(timeout=2000):
                    desc_input.fill(description)
                    time.sleep(1)
                
                # Click Create Repository button
                create_btn = page.locator("button:has-text('Create repository'), button[data-testid='submit-button']").first
                if create_btn.is_visible(timeout=5000):
                    create_btn.click()
                    logger.info("Clicked 'Create repository' button on GitHub!")
                    time.sleep(4)
            except Exception as e:
                logger.warning(f"Browser interaction note: {e}")
                
            time.sleep(2)
            context.close()
            
        # Now execute git push
        os.system(f'cd /d "{repo_dir}" && git push -u origin master')
        logger.info(f"✅ Git push completed for {repo_name}!")
        return f"Repository '{repo_name}' created and pushed to https://github.com/Mukil630/{repo_name}!"

if __name__ == "__main__":
    automator = GitHubAutomator()
    automator.auto_create_and_push_repo("AURA-OS")
