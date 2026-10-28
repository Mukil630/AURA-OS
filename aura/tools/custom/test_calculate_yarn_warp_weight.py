
import sys
from pathlib import Path
sys.path.insert(0, r"C:\Users\mukil\aura-os")
sys.path.insert(0, r"C:\Users\mukil\aura-os\aura\tools\custom")

from calculate_yarn_warp_weight import calculate_yarn_warp_weight

res = calculate_yarn_warp_weight(3000, 1000, 40)
assert 'kg' in res

print("VERIFICATION_PASS_OK")
