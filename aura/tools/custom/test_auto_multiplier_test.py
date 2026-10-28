
import sys
from pathlib import Path
sys.path.insert(0, r"C:\Users\mukil\aura-os")
sys.path.insert(0, r"C:\Users\mukil\aura-os\aura\tools\custom")

from auto_multiplier_test import auto_multiplier_test

res = auto_multiplier_test(5)
assert "Result: 50" in res

print("VERIFICATION_PASS_OK")
