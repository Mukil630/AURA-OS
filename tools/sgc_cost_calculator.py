"""
SGC Dyeing Cost & Chemical Formulation Calculator
tools/sgc_cost_calculator.py - Real industrial costing engine for Sri Ganapathi Colours (Karur).
Calculates exact chemical recipe grams (Reactive/Vat dyes, Soda Ash, Salt, Caustic Soda),
power/labor overheads, recommended quoting rates, and net profit margins.
"""
import json
import logging
import sys
from typing import Dict, Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logger = logging.getLogger("sgc_cost_calculator")

# Industrial Chemical Pricing in Karur Textile Market (INR / kg)
CHEMICAL_PRICES_INR = {
    "reactive_dye_dark": 480.0,      # e.g., Reactive Black, Navy Blue
    "reactive_dye_medium": 360.0,    # e.g., Royal Blue, Red, Orange
    "reactive_dye_light": 280.0,     # e.g., Sky Blue, Yellow, Pink
    "glauber_salt": 12.0,            # Sodium sulfate / salt
    "soda_ash": 32.0,                # Sodium carbonate (alkali fixing)
    "caustic_soda": 45.0,            # For bleaching & scouring
    "acetic_acid": 60.0,             # Neutralization
    "leveling_agent": 110.0,         # Auxiliary
    "softener": 95.0                 # Cationic softener finish
}


def calculate_dyeing_cost_and_margin(
    count: str = "10s",
    kattu: float = 50.0,
    shade_type: str = "medium",
    process: str = "cheese dyeing",
    target_margin_pct: float = 25.0
) -> Dict[str, Any]:
    """
    Calculates detailed dyeing cost, chemical recipe, and quoting recommendation.
    
    Args:
        count: Yarn count ('10s', '20s', '30s', '40s', '2/10s', '2/40s')
        kattu: Number of bundles/kattu (1 kattu = approx 4.54 kg for 10s/20s)
        shade_type: 'light' (<1% dye), 'medium' (1-3% dye), 'dark' (>3% dye)
        process: 'cheese dyeing', 'cone winding', 'hank dyeing', 'salavai bleaching'
        target_margin_pct: Target profit margin percentage (default 25%)
    
    Returns:
        Chemical grams breakdown, total cost, recommended billing rate, and profit.
    """
    # 1. Standard weight conversion: 1 kattu ≈ 4.54 kg (10 lbs)
    kg_per_kattu = 4.54
    total_weight_kg = round(kattu * kg_per_kattu, 2)

    shade_clean = shade_type.lower().strip()
    proc_clean = process.lower().strip()

    # 2. Recipe Ratios based on shade depth
    if shade_clean == "dark":
        dye_pct = 4.0      # 4% on weight of goods (owg)
        salt_g_per_l = 60.0
        soda_g_per_l = 20.0
        dye_price = CHEMICAL_PRICES_INR["reactive_dye_dark"]
    elif shade_clean == "light":
        dye_pct = 0.8
        salt_g_per_l = 25.0
        soda_g_per_l = 10.0
        dye_price = CHEMICAL_PRICES_INR["reactive_dye_light"]
    else:  # medium
        dye_pct = 2.2
        salt_g_per_l = 45.0
        soda_g_per_l = 15.0
        dye_price = CHEMICAL_PRICES_INR["reactive_dye_medium"]

    # Liquor ratio (MLR) 1:8 for modern cabinet/cheese machines
    liquor_liters = total_weight_kg * 8

    # Chemical Quantities (kg)
    dye_kg = round((total_weight_kg * dye_pct) / 100.0, 3)
    salt_kg = round((liquor_liters * salt_g_per_l) / 1000.0, 2)
    soda_ash_kg = round((liquor_liters * soda_g_per_l) / 1000.0, 2)
    caustic_kg = round(total_weight_kg * 0.02, 2) if "bleach" in proc_clean else 0.0
    leveling_kg = round(total_weight_kg * 0.01, 2)
    softener_kg = round(total_weight_kg * 0.015, 2)

    # 3. Chemical Costs (INR)
    cost_dye = dye_kg * dye_price
    cost_salt = salt_kg * CHEMICAL_PRICES_INR["glauber_salt"]
    cost_soda = soda_ash_kg * CHEMICAL_PRICES_INR["soda_ash"]
    cost_caustic = caustic_kg * CHEMICAL_PRICES_INR["caustic_soda"]
    cost_aux = (leveling_kg * CHEMICAL_PRICES_INR["leveling_agent"]) + (softener_kg * CHEMICAL_PRICES_INR["softener"])
    
    total_chemical_cost = round(cost_dye + cost_salt + cost_soda + cost_caustic + cost_aux, 2)

    # 4. Utilities, Fuel, Water & Labor Overhead (INR/kg standard: ₹18/kg)
    overhead_per_kg = 18.0
    total_overhead_cost = round(total_weight_kg * overhead_per_kg, 2)

    # 5. Total Cost of Production
    total_production_cost = round(total_chemical_cost + total_overhead_cost, 2)
    cost_per_kg = round(total_production_cost / total_weight_kg, 2)
    cost_per_kattu = round(total_production_cost / kattu, 2)

    # 6. Recommended Billing Rate with Target Margin
    recommended_kattu_rate = round(cost_per_kattu * (1 + target_margin_pct / 100.0))
    total_billing_amount = round(recommended_kattu_rate * kattu, 2)
    projected_net_profit = round(total_billing_amount - total_production_cost, 2)

    return {
        "success": True,
        "yarn_count": count,
        "kattu": kattu,
        "total_weight_kg": total_weight_kg,
        "shade_type": shade_clean.capitalize(),
        "process": proc_clean.title(),
        "recipe_breakdown": {
            "dye_grams": round(dye_kg * 1000, 1),
            "salt_kg": salt_kg,
            "soda_ash_kg": soda_ash_kg,
            "caustic_soda_kg": caustic_kg,
            "leveling_agent_kg": leveling_kg,
            "softener_finish_kg": softener_kg
        },
        "cost_summary": {
            "chemical_cost_inr": total_chemical_cost,
            "overhead_energy_labor_inr": total_overhead_cost,
            "total_production_cost_inr": total_production_cost,
            "cost_per_kg_inr": cost_per_kg,
            "cost_per_kattu_inr": cost_per_kattu
        },
        "quotation_recommendation": {
            "recommended_rate_per_kattu_inr": recommended_kattu_rate,
            "recommended_total_bill_inr": total_billing_amount,
            "target_margin_pct": target_margin_pct,
            "projected_net_profit_inr": projected_net_profit
        },
        "summary_tanglish": (
            f"🧪 **SGC Dyeing Cost ({count} {shade_clean.capitalize()} {proc_clean.title()})**:\n"
            f"- Total Weight: {total_weight_kg} kg ({kattu} kattu)\n"
            f"- Chemical Cost: ₹{total_chemical_cost} | Overhead (Power/Labor): ₹{total_overhead_cost}\n"
            f"- **Cost Price**: ₹{cost_per_kattu}/kattu (₹{cost_per_kg}/kg)\n"
            f"- **Quoting Recommendation**: **₹{recommended_kattu_rate}/kattu** (Total Bill: ₹{total_billing_amount})\n"
            f"- 💰 **Projected Profit**: **₹{projected_net_profit}** ({target_margin_pct}% margin)."
        )
    }


if __name__ == "__main__":
    res = calculate_dyeing_cost_and_margin("10s", kattu=50, shade_type="dark")
    print(res["summary_tanglish"])
