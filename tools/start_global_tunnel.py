"""
Instant Cloudflare Global HTTPS Tunnel for AURA-OS JARVIS.
Generates an instant 100% free public HTTPS URL that connects Phone from anywhere in the world to PC.
"""
import os
import sys
import re
import time
import subprocess
import json

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLOUDFLARED = os.path.join(BASE_DIR, "tools", "cloudflared.exe")

def launch_tunnel():
    print("⚡ Starting Cloudflare Instant Secure Tunnel for http://localhost:8000 ...")
    if not os.path.exists(CLOUDFLARED):
        print(f"Error: cloudflared not found at {CLOUDFLARED}")
        return

    proc = subprocess.Popen(
        [CLOUDFLARED, "tunnel", "--url", "http://localhost:8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace"
    )

    tunnel_url = None
    start_time = time.time()
    
    print("⏳ Establishing secure global tunnel connection...")
    while time.time() - start_time < 30:
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.1)
            continue
        
        match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
        if match:
            tunnel_url = match.group(0)
            print("\n" + "="*70)
            print(f"  🌌 AURA-OS GLOBAL CLOUD TUNNEL LIVE:")
            print(f"  👉 PUBLIC URL: {tunnel_url}")
            print(f"  👉 MOBILE HUB: {tunnel_url}/")
            print(f"  👉 LOGIN DEMO: {tunnel_url}/login")
            print("="*70 + "\n")
            
            # Save to memory context
            ctx_path = os.path.join(BASE_DIR, "storage", "memory", "context.json")
            if os.path.exists(ctx_path):
                try:
                    with open(ctx_path, 'r', encoding='utf-8') as f:
                        ctx = json.load(f)
                    ctx["global_tunnel_url"] = tunnel_url
                    with open(ctx_path, 'w', encoding='utf-8') as f:
                        json.dump(ctx, f, indent=2)
                except Exception:
                    pass
            break
            
    if not tunnel_url:
        print("Could not parse tunnel URL. Keeping process alive...")

    # Keep process alive
    proc.wait()

if __name__ == '__main__':
    launch_tunnel()
