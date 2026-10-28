def calculate_yarn_warp_weight(ends: int, length_meters: float, count_ne: float) -> str:
    """Calculates yarn warp weight in kilograms given ends, length and English count (Ne)."""
    length_yards = length_meters * 1.09361
    weight_lbs = (ends * length_yards) / (840 * count_ne)
    weight_kg = weight_lbs * 0.45359237
    return f"Warp Weight: {weight_kg:.2f} kg"
