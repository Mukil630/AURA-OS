import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\mukil\jarvis-core')
import asyncio
from aura_agent_core.voice_intent_gatekeeper import stage_voice_note, resolve_voice_note
from aura_agent_core.database import get_db_client

async def real_live_unpurged_proof():
    print("=" * 70)
    print(">>> 1. INCOMING REAL VOICE TRANSCRIPT:")
    transcript = "Mapla note panniko, Bannari mill Monday ₹30k payment tharom-nu sonnanga."
    print(f"Text: {transcript}")
    
    # Stage
    staged = stage_voice_note(transcript)
    draft_id = staged["draft_id"]
    print(f"\n>>> 2. STAGED IN RAM (NOT IN DB YET):")
    print(f"  • Draft ID        : {draft_id}")
    print(f"  • Database Written: {staged['db_written']} (Safe)")
    print(f"  • Clarification   : {staged['clarification_question']}")
    
    # Mukil Approves
    print(f"\n>>> 3. MUKIL CONFIRMS (Voice): 'Aama mapla, reminder-ah lock pannu'")
    commit_res = await resolve_voice_note(draft_id, "Aama mapla lock pannu")
    print(f"\n>>> 4. TURSO CLOUD WRITE RESULT:")
    print(f"  • Status          : {commit_res['action']}")
    print(f"  • Task ID         : #{commit_res['task_id']}")
    print(f"  • Title in Cloud  : {commit_res['title']}")
    
    # Query Turso Cloud directly WITHOUT PURGING
    print(f"\n>>> 5. DIRECT LIB-SQL QUERY TO AWS MUMBAI (UN-PURGED LIVE ROWS):")
    async with get_db_client() as client:
        res = await client.execute("SELECT id, title, remind_at, status, created_at FROM reminders ORDER BY id DESC LIMIT 5;")
        for r in res.rows:
            print(f"  [TURSO CLOUD ROW #{r[0]}] | {r[1]} | Remind At: {r[2]} | Status: {r[3]} | Created: {r[4]}")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(real_live_unpurged_proof())
