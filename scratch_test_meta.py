import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\Users\mukil\aura-os")
from aura.tools.registry import registry
from aura.tools.meta_tools import create_and_register_new_tool

tool_src = """def calculate_yarn_warp_weight(ends: int, length_meters: float, count_ne: float) -> str:
    \"\"\"Calculates yarn warp weight in kilograms given ends, length and English count (Ne).\"\"\"
    length_yards = length_meters * 1.09361
    weight_lbs = (ends * length_yards) / (840 * count_ne)
    weight_kg = weight_lbs * 0.45359237
    return f"Warp Weight: {weight_kg:.2f} kg"
"""

unit_test = """res = calculate_yarn_warp_weight(3000, 1000, 40)
assert 'kg' in res
"""

res = create_and_register_new_tool(
    tool_name="calculate_yarn_warp_weight",
    code=tool_src,
    test_code=unit_test,
    description="Calculates warp yarn weight in kg for weaving"
)
print("Result:", res)
print("Tool in registry?", "calculate_yarn_warp_weight" in registry._tools)
if "calculate_yarn_warp_weight" in registry._tools:
    print("Execution test:", registry.execute("calculate_yarn_warp_weight", {"ends": 3000, "length_meters": 1000, "count_ne": 40}))
