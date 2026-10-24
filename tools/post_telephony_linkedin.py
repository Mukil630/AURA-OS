"""
Autonomous LinkedIn Publisher for AURA-OS AI Telephony Engine Milestone.
"""
import os
import sys
import json
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

IMAGE_PATH = r"C:\Users\mukil\Desktop\AURA_OS_AI_Telephony_LinkedIn.jpg"

POST_TEXT = """🚀 Built an Autonomous 24/7 AI Voice Calling & Mobile Telephony Companion for Personal Executive Ops & Industrial Factory Management! 📞⚡

Most voice assistants like Siri or Alexa are passive, tied to local devices, and struggle with real-world Indian business workflows:
❌ They cannot actively place outbound calls or ring your phone when an urgent event occurs
❌ Severe pronunciation failure when speaking Indian languages (reading Tamil in Romanized English causes comical distortion)
❌ Zero integration with physical enterprise operations (factory ERP, billing ledgers, or live computer control)

To solve this, I designed and deployed an Autonomous Full-Duplex AI Telephony Engine for our AURA-OS / JARVIS system:

Here is the engineering breakdown of how it works (illustrated in the architecture infographic below):

1️⃣ 🌐 24/7 Cloud Telephony Ingress (Render WebSockets & Global 5G):
• The engine maintains an ultra-lightweight, persistent WebSocket uplink between our Render Cloud server (`wss://aura-os-jarvis.onrender.com/api/v1/call/ws`) and my Android device.
• 100% Wireless across any network: Whether on 5G mobile data, college Wi-Fi, or traveling, it requires ZERO local Wi-Fi pairing and ZERO USB cables.
• Triggers incoming call signals remotely via Telegram bot (`/call`), cron jobs, or urgent server alerts—waking the phone's locked screen and dropping our custom Billa 2007 theme beat.

2️⃣ 🗣️ Bi-Lingual Speech Architecture (Flawless Native Tamil + Crisp English):
• Ultra-low latency Speech-to-Text via Groq Whisper (<300ms).
• Powered by Gemini 3.8 Flash Brain with structured ReAct tool routing.
• Dynamic Unicode Language Dispatcher: When replying in Tamil, the engine generates pure Tamil Unicode script (தமிழ் எழுத்துக்கள்) and routes directly to Google Tamil TTS (`ta-IN`), achieving 100% natural native pronunciation without robotic stutter; technical data routes to Indian English (`en-IN`).

3️⃣ 🏭 Real-Time Verbal Tools for Industrial ERP & PC Operations:
• "Jarvis, Sri Ganapathi Colours overdue status enna?" ➔ Instantly queries our live SQLite & Google Drive ledger, aggregates pending balances across 21 spinning mill accounts, and speaks the financial report.
• "Jarvis, PC vitals check pannu" ➔ Real-time telemetry on CPU, GPU thermals, and placement radar Shortlists.

4️⃣ 📱 Minimal Stark Arc Reactor HUD:
• Built with Jetpack Compose: An audio-reactive, luminous cyan Arc Reactor visualizer with dynamic waveform ripple and clean circular Answer/Decline controls.

🛠️ Tech Stack:
• Mobile Client: Kotlin, Jetpack Compose, OkHttp WebSockets, Android Google TTS Engine
• Backend Engine: FastAPI, Python 3.10, WebSockets, Render Cloud
• AI & Speech: Groq Whisper STT (<300ms), Google Gemini 3.8 Flash, Edge Neural Voice
• Industrial Integration: Sri Ganapathi Colours (SGC) ERP Ledger, 250GB Distributed Drive Mesh

When generative AI moves beyond simple chatbots into autonomous full-duplex telephony with physical device control, personal computing becomes truly magical! 💡

🔗 GitHub Repository: https://github.com/hrunstopofficial-spec/AURA-OS

#ArtificialIntelligence #AI #VoiceAI #AndroidDev #JetpackCompose #FastAPI #Python #Telephony #FullStack #Automation #Innovation #BuildInPublic"""

def publish():
    access_token = config.LINKEDIN_ACCESS_TOKEN
    person_urn = config.LINKEDIN_PERSON_URN or "urn:li:person:9agB0hdGqJ"
    
    if not access_token:
        print("[!] No LINKEDIN_ACCESS_TOKEN found in config.py / .env")
        return False

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
    
    try:
        req = urllib.request.Request(reg_url, data=json.dumps(reg_payload).encode("utf-8"), headers=reg_headers)
        with urllib.request.urlopen(req) as resp:
            reg_data = json.loads(resp.read().decode("utf-8"))
        
        asset = reg_data["value"]["asset"]
        upload_url = reg_data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
        print(f"[+] Asset registered successfully: {asset}")
        
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
            print(f"[+] Image upload status: HTTP {resp.status}")
        
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
                            "description": { "text": "AURA-OS Autonomous Full-Duplex AI Telephony Engine" },
                            "media": asset,
                            "title": { "text": "AURA-OS Autonomous Voice Telephony" }
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
            post_id = post_data.get("id", "Unknown")
            print(f"🎉 [SUCCESS] LinkedIn Post Published Live! Post ID: {post_id}")
            return True
            
    except urllib.error.HTTPError as he:
        print(f"[!] HTTP Error {he.code}: {he.read().decode('utf-8')}")
        return False
    except Exception as e:
        print(f"[!] Exception during LinkedIn publish: {e}")
        return False

if __name__ == "__main__":
    publish()
