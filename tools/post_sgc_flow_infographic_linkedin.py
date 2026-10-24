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

IMAGE_PATH = r"C:\Users\mukil\.gemini\antigravity-cli\brain\c4314e11-bbb8-4d64-bf89-1849d00acf1a\sgc_automation_flow_1789868868962.jpg"

POST_TEXT = """⚡ How I Automated End-to-End Invoicing, Month-Wise Cloud Archiving & GST Tax Filing for an Industrial Textile Dyeing Factory! 🧵📊

In traditional MSMEs and textile dyeing units across India, accounting and tax filing are often broken down into painful manual steps:
❌ Creating paper bills or unorganized local files
❌ Manually sorting invoices into monthly folders for audits
❌ Frantic month-end manual calculation of CGST (2.5%) and SGST (2.5%) for GSTR-3B filings
❌ Zero mobile accessibility when on the factory floor

To solve this, I designed and deployed an autonomous 4-stage pipeline for Sri Ganapathi Colours (SGC) with our v6.0 release:

Here is how the automated flow works (illustrated in the infographic below):

1️⃣ 📝 Invoice Creation & Dynamic Tax Engine:
• Floor managers enter yarn variety (10s, 2/30s, 2/40s) and weight (kattu/kazhi).
• The engine automatically computes Subtotal, CGST (2.50%), and SGST (2.50%) in real-time, eliminating human math errors.

2️⃣ ☁️ Autonomous Cloud Sorting (Google Drive API):
• As soon as an invoice is saved, our background sync engine determines the billing period.
• The system dynamically queries our Google Drive Master Vault (Node 05) and routes the PDF into chronological month subfolders (`2026-05`, `2026-07`, `2026-08`, `2026-09`) with zero local disk waste.

3️⃣ 📊 Monthly GST Tax Radar & GSTR-1 Generator:
• A dedicated tax totalizer aggregates all CGST & SGST across every bill for any selected month.
• Provides single-click GSTR-1 CSV export and instant formatted summaries ready for the auditor.

4️⃣ 📱 Mobile Executive Access via Telegram Bot (@mukil_jarvis_executive_bot):
• `/gst` — Instant mobile tax dashboard with inline buttons to switch months and download GSTR-1 CSV spreadsheets directly into chat.
• 1-Click WhatsApp forward link to send pre-formatted Tamil/English tax summaries directly to the Chartered Accountant (CA).

🛠️ Tech Stack & Architecture:
• Desktop App: Electron.js, React, Tailwind CSS, Node.js
• Cloud Storage Mesh: Google Drive REST API v3 (Distributed Multi-Vault Architecture)
• Mobile Gateway: python-telegram-bot (Interactive Callbacks & Document Dispatch)
• Industrial Math: Kubelka-Munk Trichromatic Reactive Dye Formulation (Yellow, Red, Blue)

When software engineering directly automates heavy manual operations on the factory floor, the impact is immediate and tangible! 💡

🔗 Open-Source Repository: https://github.com/Mukil630/sgc-billing

#FullStackDevelopment #Automation #ElectronJS #Python #TelegramBot #GST #Fintech #TextileEngineering #SoftwareArchitecture #BuildInPublic"""

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
                        "description": { "text": "End-to-End Automation Flow of SGC Billing v6.0" },
                        "media": asset,
                        "title": { "text": "SGC Billing v6.0 — Automation Flow Architecture" }
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
        "post_id": post_id,
        "media": IMAGE_PATH,
        "status": "PUBLISHED"
    })
    
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)
        
    return post_id

if __name__ == "__main__":
    publish()
