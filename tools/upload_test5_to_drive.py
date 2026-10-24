import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tools.sync_to_drive import get_drive_service, upload_file_to_vault

service = get_drive_service()
if not service:
    print("Drive service not available.")
    sys.exit(1)

# Node 08: Learning Materials, Java DSA & Apti: 18L9Q6MC1fiT_LIPg0FKpLlQ0OR052yyJ
# Master Folder: 1nGZG5-eIcxmkgQxBtZ7tjGTUoWWNY4m1
FOLDER_ID = "1nGZG5-eIcxmkgQxBtZ7tjGTUoWWNY4m1"

files = [
    r"C:\Users\mukil\Desktop\Economics_Test_5_Part1_Q1_to_Q30.pdf",
    r"C:\Users\mukil\Desktop\Economics_Test_5_All_Q1_to_Q75.pdf"
]

results = {}
for f in files:
    if os.path.exists(f):
        res = upload_file_to_vault(service, f, FOLDER_ID)
        if res:
            results[os.path.basename(f)] = res.get('webViewLink')
            print(f"Uploaded {os.path.basename(f)}: {res.get('webViewLink')}")

print("\n--- Summary ---")
for k, v in results.items():
    print(f"{k}: {v}")
