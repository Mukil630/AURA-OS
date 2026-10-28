
import sys
from pathlib import Path
sys.path.insert(0, r"C:\Users\mukil\aura-os")
sys.path.insert(0, r"C:\Users\mukil\aura-os\aura\tools\custom")

from morning_autonomous_wakeup_briefing import morning_autonomous_wakeup_briefing

res = morning_autonomous_wakeup_briefing()
assert res['status'] == 'success'
print("Morning briefing test passed:", res['briefing'])

print("VERIFICATION_PASS_OK")
