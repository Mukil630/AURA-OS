
import sys
from pathlib import Path
sys.path.insert(0, r"C:\Users\mukil\aura-os")
sys.path.insert(0, r"C:\Users\mukil\aura-os\aura\tools\custom")

from calculate_gst_split import calculate_gst_split

res = calculate_gst_split(1050.0, 5.0)
assert "CGST: ₹25.00" in res

print("VERIFICATION_PASS_OK")
