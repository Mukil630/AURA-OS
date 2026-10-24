import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.sync_to_drive import get_drive_service, upload_file_to_vault

def main():
    service = get_drive_service()
    if not service:
        print("ERROR: Google Drive service could not be initialized.")
        return

    apk_path = r"C:\Users\mukil\Desktop\AURA_OS_VoiceAssistant_Update.apk"
    if not os.path.exists(apk_path):
        print(f"ERROR: APK not found at {apk_path}")
        return

    # Master Vault Folder: 1nGZG5-eIcxmkgQxBtZ7tjGTUoWWNY4m1
    folder_id = "1nGZG5-eIcxmkgQxBtZ7tjGTUoWWNY4m1"
    
    print(f"Uploading {apk_path} ({round(os.path.getsize(apk_path)/(1024*1024), 2)} MB) to Google Drive...")
    res = upload_file_to_vault(service, apk_path, folder_id)
    if res:
        file_id = res.get("id")
        web_link = res.get("webViewLink")
        print("\n=== UPLOAD SUCCESSFUL ===")
        print(f"File ID: {file_id}")
        print(f"Web View Link: {web_link}")
        print(f"Direct Download Link: https://drive.google.com/uc?export=download&id={file_id}")
    else:
        print("ERROR: Failed to upload file to Google Drive.")

if __name__ == "__main__":
    main()
