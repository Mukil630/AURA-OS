"""Industrial Washing & Salavai Hub Agent for AURA-OS Swarm.
app/agents/swarm/washing_hub_agent.py - Manages Rotary Washers, Hydro-Extractors,
Bio-Polishing Enzyme & Silicon Finish Recipes, Garment Lot Tracking, and Washing Invoices.
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta, timezone

from app.agents.swarm.base_swarm_agent import BaseSwarmAgent, SwarmTaskMessage

logger = logging.getLogger("WashingHubAgent")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
WASHING_LOTS_FILE = os.path.join(BASE_DIR, "storage", "memory", "washing_hub_lots.json")
IST = timezone(timedelta(hours=5, minutes=30))


class WashingHubAgent(BaseSwarmAgent):
    """
    Autonomous Production & Quality Partner for Industrial Garment & Fabric Washing.
    Specializes in Bio-Polish, Enzyme Wash, Silicon Finishing, and Bleaching (Salavai).
    """

    def __init__(self):
        super().__init__(
            agent_name="WashingHubAgent",
            role_description="Industrial washing machine supervisor, bio-polish/enzyme recipe formulator, and garment lot manager"
        )
        self._ensure_storage()

    def _ensure_storage(self):
        os.makedirs(os.path.dirname(WASHING_LOTS_FILE), exist_ok=True)
        if not os.path.exists(WASHING_LOTS_FILE):
            default_data = {
                "unit_name": "Sri Ganapathi Industrial Washing & Salavai Hub",
                "last_updated": datetime.now(IST).isoformat(),
                "machines": [
                    {"id": "M1", "type": "Rotary Belly Washer (100 Kg)", "status": "AVAILABLE", "current_lot": None},
                    {"id": "M2", "type": "Rotary Belly Washer (50 Kg)", "status": "AVAILABLE", "current_lot": None},
                    {"id": "M3", "type": "Hydro-Extractor (Centrifugal)", "status": "AVAILABLE", "current_lot": None},
                    {"id": "M4", "type": "Steam Tumble Dryer (50 Kg)", "status": "AVAILABLE", "current_lot": None}
                ],
                "lots": []
            }
            with open(WASHING_LOTS_FILE, "w", encoding="utf-8") as f:
                json.dump(default_data, f, indent=2)

    def load_lots(self) -> Dict[str, Any]:
        try:
            with open(WASHING_LOTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load washing lots: {e}")
            return {"lots": [], "machines": []}

    def save_lots(self, data: Dict[str, Any]):
        data["last_updated"] = datetime.now(IST).isoformat()
        try:
            with open(WASHING_LOTS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save washing lots: {e}")

    def formulate_washing_recipe(self, wash_type: str, fabric_weight_kg: float) -> Dict[str, Any]:
        """
        Formulates exact chemical quantities and process cycle parameters.
        Types: 'bio_polish' (Acid Enzyme), 'silicon_finish', 'salavai_bleach', 'normal_soft_wash'.
        """
        wt = float(fabric_weight_kg)
        liquor_ratio = 10  # 1:10 M:L ratio (100 kg fabric = 1000 Litres water)
        water_litres = wt * liquor_ratio

        w_lower = wash_type.lower()

        if "bio" in w_lower or "enzyme" in w_lower:
            recipe_name = "Bio-Polishing (Acid Cellulase Enzyme Wash)"
            chemicals = [
                {"name": "Acid Cellulase Enzyme", "percentage_owf": 1.2, "quantity_kg": round((wt * 1.2) / 100, 2)},
                {"name": "Acetic Acid (for pH 4.5 - 5.5)", "percentage_owf": 0.8, "quantity_kg": round((wt * 0.8) / 100, 2)},
                {"name": "Non-Ionic Wetting Agent", "percentage_owf": 0.5, "quantity_kg": round((wt * 0.5) / 100, 2)},
                {"name": "Soda Ash (Enzyme Deactivation Kill)", "percentage_owf": 1.0, "quantity_kg": round((wt * 1.0) / 100, 2)}
            ]
            cycle_steps = [
                "1. Load garments & fill water (1:10 ratio). Add Acetic acid to adjust pH to 4.5 - 5.0.",
                "2. Raise temperature to 55°C. Add Acid Enzyme.",
                "3. Run machine rotation for 45 - 60 minutes for clean surface pilling removal.",
                "4. Add Soda Ash (pH > 9.0) and raise temp to 80°C for 10 mins to kill enzyme activity.",
                "5. Drain and cold rinse thoroughly."
            ]

        elif "silicon" in w_lower or "soft" in w_lower:
            recipe_name = "Silicon Soft-Touch Finish (Silky Handfeel)"
            chemicals = [
                {"name": "Micro-Emulsion Silicon Softener", "percentage_owf": 2.5, "quantity_kg": round((wt * 2.5) / 100, 2)},
                {"name": "Cationic Softener Base", "percentage_owf": 1.0, "quantity_kg": round((wt * 1.0) / 100, 2)},
                {"name": "Acetic Acid (pH 5.5)", "percentage_owf": 0.3, "quantity_kg": round((wt * 0.3) / 100, 2)}
            ]
            cycle_steps = [
                "1. Fill clean water at 40°C. Add Acetic acid (pH 5.5).",
                "2. Pre-dilute Silicon Softener with warm water and pour into running washer.",
                "3. Run for 20 minutes for uniform penetration.",
                "4. Unload directly to Hydro-Extractor (Do NOT rinse).",
                "5. Steam Tumble Dry at 70°C for thermo-fixation."
            ]

        elif "bleach" in w_lower or "salavai" in w_lower:
            recipe_name = "Salavai (Full Bleaching for White Dhotis/Towels)"
            chemicals = [
                {"name": "Hydrogen Peroxide (H2O2 35%)", "percentage_owf": 4.0, "quantity_kg": round((wt * 4.0) / 100, 2)},
                {"name": "Caustic Soda Flakes (NaOH)", "percentage_owf": 2.0, "quantity_kg": round((wt * 2.0) / 100, 2)},
                {"name": "Peroxide Stabilizer", "percentage_owf": 0.5, "quantity_kg": round((wt * 0.5) / 100, 2)},
                {"name": "Optical Brightening Agent (OBA 2B)", "percentage_owf": 0.3, "quantity_kg": round((wt * 0.3) / 100, 2)}
            ]
            cycle_steps = [
                "1. Scouring & Bleaching bath at 90°C - 95°C for 60 mins.",
                "2. Hot wash at 80°C followed by cold neutralization with Acetic acid.",
                "3. Optical brightening tint application at 50°C for 20 mins.",
                "4. Hydro-extract and dry."
            ]

        else:
            recipe_name = "Normal Detergent Wash & Softener"
            chemicals = [
                {"name": "Industrial Detergent", "percentage_owf": 1.0, "quantity_kg": round((wt * 1.0) / 100, 2)},
                {"name": "Softener", "percentage_owf": 1.5, "quantity_kg": round((wt * 1.5) / 100, 2)}
            ]
            cycle_steps = [
                "1. Detergent wash at 60°C for 25 mins.",
                "2. Cold rinse, then soften at 40°C for 15 mins."
            ]

        return {
            "recipe_name": recipe_name,
            "fabric_weight_kg": wt,
            "water_required_litres": water_litres,
            "chemicals": chemicals,
            "process_steps": cycle_steps
        }

    async def process_task(self, message: SwarmTaskMessage) -> SwarmTaskMessage:
        logger.info(f"🧼 [WashingHub] Processing action: {message.action}")
        action = message.action.upper()
        payload = message.payload or {}

        try:
            # 1. Formulate Recipe
            if action in ["FORMULATE_RECIPE", "RECIPE", "BIO_POLISH", "SILICON"]:
                wash_type = payload.get("wash_type") or payload.get("type", "bio_polish")
                weight = float(payload.get("weight_kg", payload.get("weight", 50.0)))
                rec = self.formulate_washing_recipe(wash_type, weight)

                chem_lines = "\n".join([f"• **{c['name']}**: `{c['quantity_kg']} Kg` ({c['percentage_owf']}% owf)" for c in rec["chemicals"]])
                step_lines = "\n".join(rec["process_steps"])

                summary = (
                    f"🧪 **Industrial Washing Recipe: {rec['recipe_name']}**\n"
                    f"⚖️ **Batch Weight:** `{rec['fabric_weight_kg']} Kg` | 💧 **Water Required:** `{rec['water_required_litres']} Litres`\n\n"
                    f"📦 **Chemical Dispensing List:**\n{chem_lines}\n\n"
                    f"⚙️ **Machine Cycle Steps:**\n{step_lines}"
                )
                message.status = "COMPLETED"
                message.result = {"recipe": rec, "summary": summary}
                return message

            # 2. Register New Washing Inward Lot
            elif action in ["ADD_LOT", "INWARD_LOT", "REGISTER_ORDER"]:
                customer = payload.get("customer", "Local Garments")
                weight_kg = float(payload.get("weight_kg", 0.0))
                pieces = int(payload.get("pieces", 0))
                wash_type = payload.get("wash_type", "Bio-Polish + Silicon Finish")
                rate_per_kg = float(payload.get("rate_per_kg", 35.0))
                delivery_date = payload.get("delivery_date") or (date.today() + timedelta(days=2)).strftime("%Y-%m-%d")

                data = self.load_lots()
                lot_id = f"WASH-{datetime.now(IST).strftime('%m%d')}-{len(data.get('lots', [])) + 1:02d}"

                new_lot = {
                    "lot_id": lot_id,
                    "customer": customer,
                    "weight_kg": weight_kg,
                    "pieces": pieces,
                    "wash_type": wash_type,
                    "rate_per_kg": rate_per_kg,
                    "estimated_total": round(weight_kg * rate_per_kg, 2),
                    "received_date": datetime.now(IST).strftime("%Y-%m-%d"),
                    "target_delivery": delivery_date,
                    "stage": "RECEIVED",  # RECEIVED -> IN_WASHER -> HYDRO -> DRYING -> READY
                    "created_at": datetime.now(IST).isoformat()
                }

                data.setdefault("lots", []).append(new_lot)
                self.save_lots(data)

                summary = (
                    f"✅ **Washing Lot Registered: #{lot_id}**\n\n"
                    f"🏢 **Customer:** {customer}\n"
                    f"⚖️ **Weight:** `{weight_kg} Kg` ({pieces} pcs) | **Type:** {wash_type}\n"
                    f"💵 **Rate:** ₹{rate_per_kg}/Kg (Est: `₹{new_lot['estimated_total']:,.2f}` + 5% GST)\n"
                    f"📅 **Target Delivery:** `{delivery_date}`\n"
                    f"Machine loading queue-la add panniten Boss!"
                )
                message.status = "COMPLETED"
                message.result = {"lot": new_lot, "summary": summary}
                return message

            # 3. Machine & Production Status
            else:
                data = self.load_lots()
                lots = data.get("lots", [])
                active_lots = [l for l in lots if l.get("stage") != "DISPATCHED"]
                lot_lines = [
                    f"• `#{l['lot_id']}` | **{l['customer']}** | {l['weight_kg']} Kg | [{l['stage']}] -> Delivery: `{l['target_delivery']}`"
                    for l in active_lots[-5:]
                ]

                summary = (
                    f"🏭 **Sri Ganapathi Industrial Washing Hub Status:**\n\n"
                    f"Active Orders in Floor: **{len(active_lots)} Lots**\n"
                    + ("\n".join(lot_lines) if lot_lines else "No active lots currently on floor.")
                )
                message.status = "COMPLETED"
                message.result = {"active_lots": active_lots, "summary": summary}
                return message

        except Exception as e:
            logger.error(f"WashingHubAgent error: {e}", exc_info=True)
            message.status = "FAILED"
            message.error = str(e)
            return message
