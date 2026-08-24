import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
JARVIS_VOICE_SECRET_TOKEN = os.getenv('JARVIS_VOICE_SECRET_TOKEN', 'mukil-jarvis-vault-key-9080030538')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')

DRIVE_VAULT_URL = os.getenv('DRIVE_VAULT_URL', 'https://drive.google.com/drive/folders/1nGZG5-eIcxmkgQxBtZ7tjGTUoWWNY4m1?usp=sharing')
DRIVE_FOLDER_ID = os.getenv('DRIVE_FOLDER_ID', '1nGZG5-eIcxmkgQxBtZ7tjGTUoWWNY4m1')

# SGC Billing & Invoicing Dual Drive Folders
DRIVE_BILLING_FOLDER_1_URL = 'https://drive.google.com/drive/folders/155EqYOwPJ2Fc9QfqVSrZu5VnYzZgRcyZ?usp=drive_link'
DRIVE_BILLING_FOLDER_1_ID = os.getenv('DRIVE_BILLING_FOLDER_1_ID', '155EqYOwPJ2Fc9QfqVSrZu5VnYzZgRcyZ')

DRIVE_BILLING_FOLDER_2_URL = 'https://drive.google.com/drive/folders/1a9VJAP_Nypn_mjUEYCNvMpkGN5H9Kwf4?usp=sharing'
DRIVE_BILLING_FOLDER_2_ID = os.getenv('DRIVE_BILLING_FOLDER_2_ID', '1a9VJAP_Nypn_mjUEYCNvMpkGN5H9Kwf4')

DRIVE_BILLING_FOLDERS = [
    DRIVE_BILLING_FOLDER_1_ID,
    DRIVE_BILLING_FOLDER_2_ID
]
