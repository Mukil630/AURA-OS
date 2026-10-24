import urllib.request
import json
from pathlib import Path

token = '8738700204:AAGfOluaOWUUp5HgZTN0ZXiwxbZrlDEituk'
chat_id = '6233907249'
photo_path = r'C:\Users\mukil\.gemini\antigravity-cli\brain\c4314e11-bbb8-4d64-bf89-1849d00acf1a\sgc_automation_flow_1789868868962.jpg'

caption = (
    "📊 <b>SGC BILLING v6.0 — END-TO-END AUTOMATION FLOW INFOGRAPHIC</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "⚡ <b>Step-by-Step Architecture:</b>\n"
    "1️⃣ <b>Invoice Creation</b>: Real-time CGST (2.5%) & SGST (2.5%) dynamic calculation.\n"
    "2️⃣ <b>Autonomous Cloud Sorting</b>: Google Drive API automatically routes bills into month subfolders (<code>2026-05</code>, <code>2026-07</code>, <code>2026-08</code>, <code>2026-09</code>).\n"
    "3️⃣ <b>Monthly GST Radar</b>: Tax totalizer engine + GSTR-1 CSV generator.\n"
    "4️⃣ <b>Mobile Auditor Access</b>: Telegram Bot <code>/gst</code> command + 1-click WhatsApp CA forward.\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "✅ <i>Mapla, complete visual automation flow infographic unga phone-ku vanthachu!</i> 🔥"
)

boundary = '----WebKitFormBoundaryPhotoFlow7788'
with open(photo_path, 'rb') as f:
    photo_bytes = f.read()

body = bytearray()
body.extend(f'--{boundary}\r\n'.encode('utf-8'))
body.extend(f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'.encode('utf-8'))
body.extend(f'--{boundary}\r\n'.encode('utf-8'))
body.extend(f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'.encode('utf-8'))
body.extend(f'--{boundary}\r\n'.encode('utf-8'))
body.extend(f'Content-Disposition: form-data; name="parse_mode"\r\n\r\nHTML\r\n'.encode('utf-8'))
body.extend(f'--{boundary}\r\n'.encode('utf-8'))
body.extend(f'Content-Disposition: form-data; name="photo"; filename="sgc_automation_flow.jpg"\r\n'.encode('utf-8'))
body.extend(b'Content-Type: image/jpeg\r\n\r\n')
body.extend(photo_bytes)
body.extend(b'\r\n')
body.extend(f'--{boundary}--\r\n'.encode('utf-8'))

req = urllib.request.Request(
    f'https://api.telegram.org/bot{token}/sendPhoto',
    data=bytes(body),
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
    method='POST'
)

with urllib.request.urlopen(req, timeout=30) as resp:
    res = json.loads(resp.read().decode('utf-8'))
    print('Telegram sendPhoto result:', res.get('ok'))
