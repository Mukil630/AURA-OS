import os
import sys
import time
import requests
import asyncio
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
load_dotenv(r"C:\Users\mukil\jarvis-core\.env")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TARGET_DIR = r"C:\Users\mukil\jarvis-core\storage\swatches"
os.makedirs(TARGET_DIR, exist_ok=True)
SAVE_PATH = os.path.join(TARGET_DIR, "latest_swatch.jpg")

from tools.sgc_color_finder import solve_swatch_full_solution, format_color_solution_telegram
from tools.tts_generator import generate_voice_audio

sys.stdout.reconfigure(encoding="utf-8")
print("[*] SGC Intelligent Swatch & Color Photo Listener ACTIVE...", flush=True)

# Flush pending updates
init = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset=-1", timeout=10).json()
last_id = 0
if init.get("result"):
    last_id = init["result"][-1]["update_id"]

start = time.time()
while time.time() - start < 3600:  # 1 hour listening window
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={last_id + 1}&timeout=10"
        resp = requests.get(url, timeout=15).json()
        if not resp.get("ok"):
            time.sleep(1)
            continue

        for u in resp.get("result", []):
            last_id = u["update_id"]
            msg = u.get("message", {})
            chat_id = msg.get("chat", {}).get("id")

            photo = msg.get("photo")
            doc = msg.get("document")
            text = msg.get("text")
            caption = msg.get("caption")

            file_id = None
            if photo:
                file_id = photo[-1]["file_id"]
            elif doc and doc.get("mime_type", "").startswith("image/"):
                file_id = doc["file_id"]

            if file_id:
                print(f"[+] Photo received from {chat_id}, downloading...", flush=True)
                f_info = requests.get(f"https://api.telegram.org/bot{TOKEN}/getFile?file_id={file_id}", timeout=10).json()
                if f_info.get("ok"):
                    f_path = f_info["result"]["file_path"]
                    d_url = f"https://api.telegram.org/file/bot{TOKEN}/{f_path}"
                    img_data = requests.get(d_url, timeout=30).content
                    with open(SAVE_PATH, "wb") as f:
                        f.write(img_data)
                    print(f"[SUCCESS] Swatch saved to {SAVE_PATH}", flush=True)

                    requests.post(
                        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                        json={"chat_id": chat_id, "text": "🔬 *Analyzing Fabric Swatch...*\nFiltering glare & shadows, calculating CIEDE2000 & Inverse Kubelka-Munk formulation...", "parse_mode": "Markdown"},
                        timeout=10
                    )

                    # Solve color & recipe
                    fabric_kg = 250.0
                    if caption and ("kg" in caption.lower()):
                        import re
                        m = re.search(r'(\d+(?:\.\d+)?)\s*kg', caption.lower())
                        if m:
                            fabric_kg = float(m.group(1))

                    res = solve_swatch_full_solution(SAVE_PATH, fabric_kg=fabric_kg)
                    report = format_color_solution_telegram(res)

                    # Send text report
                    requests.post(
                        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                        json={"chat_id": chat_id, "text": report, "parse_mode": "Markdown"},
                        timeout=15
                    )
                    print("[+] Sent color analysis report to Telegram!", flush=True)

                    # Generate and send Voice Note
                    p = res["best_pantone_match"]
                    cost = res["industrial_batch_recipe"]["financials"]["cost_per_kg_fabric_inr"]
                    voice_summary = (
                        f"Maapla, unga swatch photo-va analyze panniten! Indha color Pantone {p['name']} ({p['code']}) kooda match aagudhu. "
                        f"250 kg fabric lot-ku chemical recipe calculation ready, cost around {cost} rupees per kg. Full report anuppitten!"
                    )
                    try:
                        voice_path = asyncio.run(generate_voice_audio(voice_summary))
                        if os.path.exists(voice_path):
                            with open(voice_path, "rb") as vf:
                                requests.post(
                                    f"https://api.telegram.org/bot{TOKEN}/sendVoice",
                                    data={"chat_id": chat_id, "caption": "🎙️ SGC Swatch Analysis Voice Note"},
                                    files={"voice": vf},
                                    timeout=20
                                )
                            os.remove(voice_path)
                            print("[+] Sent voice note to Telegram!", flush=True)
                    except Exception as ve:
                        print(f"[!] Voice generation error: {ve}", flush=True)

            elif text:
                print(f"[+] Text received: '{text}' from {chat_id}", flush=True)
                if text.startswith("#"):
                    res = solve_swatch_full_solution(text.strip(), fabric_kg=250.0)
                    report = format_color_solution_telegram(res)
                    requests.post(
                        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                        json={"chat_id": chat_id, "text": report, "parse_mode": "Markdown"},
                        timeout=15
                    )

    except Exception as e:
        print(f"[!] Network or API Error: {e}. Retrying in 3 seconds...", flush=True)
        time.sleep(3)

print("[*] Listener loop ended.", flush=True)
