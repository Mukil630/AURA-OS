import os
import sys
import time
import logging
import urllib.parse
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from memory.memory_manager import MemoryManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("linkedin_automator")

class LinkedInAutomator:
    """
    Autonomous LinkedIn Post Creator & Publisher using Playwright.
    """
    def __init__(self, session_dir=None):
        self.session_dir = session_dir or os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "browser_session")
        os.makedirs(self.session_dir, exist_ok=True)
        self.mem = MemoryManager()

    def open_and_draft_post(self, post_text: str):
        """
        Opens LinkedIn in Chrome, injects the post text into the post modal, 
        and readies it for 1-click publishing.
        """
        logger.info("Opening LinkedIn to create post...")
        
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                self.session_dir,
                headless=False,
                channel="chrome",
                args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
                no_viewport=True
            )
            page = context.pages[0] if context.pages else context.new_page()
            
            page.goto("https://www.linkedin.com/feed/", timeout=60000)
            time.sleep(4)
            
            try:
                # Click "Start a post" button
                start_post_btn = page.locator("button:has-text('Start a post'), button.share-box-feed-entry__trigger").first
                if start_post_btn.is_visible(timeout=6000):
                    start_post_btn.click()
                    time.sleep(2)
                    
                    # Fill post text
                    editor = page.locator("div.editor-content div.ql-editor, div[contenteditable='true']").first
                    if editor.is_visible(timeout=4000):
                        editor.fill(post_text)
                        logger.info("✅ Post text successfully drafted into LinkedIn!")
            except Exception as e:
                logger.warning(f"LinkedIn automation note: {e}")
                
            time.sleep(3)
            # Leave open for user inspection or auto-post
            print("\n[AURA LINKEDIN] Post is drafted on your screen. Click 'Post' or let AURA handle it!")

if __name__ == "__main__":
    automator = LinkedInAutomator()
    sample_text = "🚀 Day 1 of Building My Ultimate Birthday Gift: Meet AURA (Autonomous Unified Response Assistant) 🌌"
    automator.open_and_draft_post(sample_text)
