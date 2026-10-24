import os
import sys
import json
import datetime
import urllib.request
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(r"C:\Users\mukil\jarvis-core")
sys.path.insert(0, str(BASE_DIR))
import config

IMAGE_PATH = r"C:\Users\mukil\.gemini\antigravity-cli\brain\c4314e11-bbb8-4d64-bf89-1849d00acf1a\sgc_billing_showcase_1789867470173.jpg"

POST_TEXT = """🚀 Shipped SGC Billing v6.0: Autonomous Enterprise Billing, Month-Wise Drive Vaults & Mobile Telegram AI Gateway for a Real-World Textile Dyeing Unit! 🧵⚡

Most MSMEs and textile dyeing factories in India still run on:
❌ Fragile manual paper bill books & scattered PDFs
❌ Chaotic month-end scrambling to compute CGST (2.5%) & SGST (2.5%) for GSTR-3B filing
❌ Being tied to a desktop PC just to create delivery invoices & track payments

To solve this end-to-end for Sri Ganapathi Colours (SGC), I designed and built an offline-resilient Desktop Suite + Mobile Telegram AI Control Plane.

Here is what just went live in v6.0:

1️⃣ 📁 Autonomous Month-Wise Google Drive Vault Mesh:
• Invoices are automatically categorized and routed into chronological month subfolders (e.g., `2026-05 (May 2026)`, `2026-07 (July 2026)`, `2026-09 (September 2026)`).
• 100% zero manual file organizing, backed up across 3 distributed vault mirrors.

2️⃣ 🏛️ Monthly GST Tax Radar & Bill-by-Bill Breakdown:
• Auto-aggregates CGST (2.50%), SGST (2.50%), and Total GST (5.00%) across all invoices for the month.
• Dedicated interactive table showing each bill's individual GST amounts with single-click GSTR-1 CSV export and instant WhatsApp dispatch for the CA / Tax Auditor.

3️⃣ 📱 Interactive Telegram AI Mobile Control Plane (@mukil_jarvis_executive_bot):
• `/gst` — Interactive GST Control Center with Inline Buttons to toggle months, download GSTR-1 spreadsheets directly into chat, and forward tax data to CA.
• `/bill` — Generate official GST invoices with CSB Bank details & Dynamic UPI QR codes (GPay/PhonePe) directly from mobile while on the factory floor.
• `/overdue` — Real-time customer balance radar with automated Tamil & English payment reminder templates.

4️⃣ 🏭 Industrial Dyeing Precision:
• Tailored for yarn count volume tracking (10s, 2/30s, 2/40s), kattu/kazhi calculations, and integrated with Kubelka-Munk trichromatic dye recipe formulations (Yellow HE4R, Red HE7B, Blue HERD).

🛠️ Tech Stack:
• Desktop App: Electron.js, React, Node.js
• Cloud & Storage: Google Drive API v3 (Distributed Multi-Vault Mesh)
• Mobile Gateway: python-telegram-bot (Interactive Inline Keyboards & Document Dispatch)
• PDF Engine: Chromium Native Print & Puppeteer with Dynamic UPI QR

Software engineering is 10x more rewarding when it directly solves tangible problems on the factory floor and automates tedious accounting workflows! 💡

🔗 Explore the open-source code on GitHub: https://github.com/Mukil630/sgc-billing

#FullStackDevelopment #ElectronJS #Python #TelegramBot #Automation #GST #TextileEngineering #SoftwareEngineering #AI #Productivity #BuildInPublic"""

def publish():
    access_token = config.LINKEDIN_ACCESS_TOKEN
    person_urn = config.LINKEDIN_PERSON_URN or "urn:li:person:9agB0hdGqJ"
    
    print("[*] Step 1: Registering image upload with LinkedIn...")
    reg_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
    reg_headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json"
    }
    reg_payload = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": person_urn,
            "supportedUploadMechanism": ["SYNCHRONOUS_UPLOAD"]
        }
    }
    
    req = urllib.request.Request(reg_url, data=json.dumps(reg_payload).encode("utf-8"), headers=reg_headers)
    with urllib.request.urlopen(req) as resp:
        reg_data = json.loads(resp.read().decode("utf-8"))
    
    asset = reg_data["value"]["asset"]
    upload_url = reg_data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
    print(f"[+] Asset registered: {asset}")
    
    print("[*] Step 2: Uploading image binary data...")
    with open(IMAGE_PATH, "rb") as f:
        img_bytes = f.read()
    
    upload_req = urllib.request.Request(
        upload_url,
        data=img_bytes,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/octet-stream"
        },
        method="PUT"
    )
    with urllib.request.urlopen(upload_req) as resp:
        print(f"[+] Image upload status: {resp.status}")
    
    print("[*] Step 3: Publishing UGC Post to LinkedIn...")
    ugc_url = "https://api.linkedin.com/v2/ugcPosts"
    ugc_headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json"
    }
    ugc_payload = {
        "author": person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": { "text": POST_TEXT },
                "shareMediaCategory": "IMAGE",
                "media": [
                    {
                        "status": "READY",
                        "description": { "text": "SGC Billing v6.0 Enterprise Suite & Telegram AI Gateway" },
                        "media": asset,
                        "title": { "text": "SGC Billing v6.0 — Enterprise Architecture" }
                    }
                ]
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }
    
    post_req = urllib.request.Request(ugc_url, data=json.dumps(ugc_payload).encode("utf-8"), headers=ugc_headers)
    with urllib.request.urlopen(post_req) as resp:
        post_data = json.loads(resp.read().decode("utf-8"))
    
    post_id = post_data.get("id")
    print(f"[🎉] SUCCESS! Post published to LinkedIn! Post ID: {post_id}")
    
    # Record in history
    history_file = BASE_DIR / "storage" / "memory" / "linkedin_posts.json"
    history = []
    if history_file.exists():
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            pass
    
    history.append({
        "timestamp": datetime.datetime.now().isoformat(),
        "post_content": POST_TEXT,
        "image_attached": IMAGE_PATH,
        "result": { "success": True, "post_id": post_id, "method": "ugcPosts" }
    })
    
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)
    
    return post_id

if __name__ == "__main__":
    publish()
