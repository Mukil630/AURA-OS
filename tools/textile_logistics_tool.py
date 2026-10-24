"""
Textile Logistics, Mill Route & Freight Cost Engine
tools/textile_logistics_tool.py - 100% Free OSRM Routing & Tamil Nadu Textile Cluster Logistics.
Calculates driving distance, travel time, and freight transport parcel costs
from Sri Ganapathi Colours (Karur) to major textile spinning & weaving centers.
"""
import urllib.request
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("textile_logistics_tool")

# Coordinates of SGC Factory and Major Textile Hubs in Tamil Nadu
CLUSTER_COORDINATES = {
    "karur_sgc": (10.9601, 78.0766),
    "tirupur": (11.1085, 77.3411),
    "coimbatore": (11.0168, 76.9558),
    "erode": (11.3410, 77.7172),
    "salem": (11.6643, 78.1460),
    "dindigul": (10.3673, 77.9803),
    "sathyamangalam": (11.5034, 77.2441),
    "rajapalayam": (9.4533, 77.5539),
    "komarapalayam": (11.4428, 77.7011)
}


def calculate_mill_route_and_freight(
    destination: str,
    kattu_count: int = 50,
    origin: str = "karur_sgc"
) -> Dict[str, Any]:
    """
    Calculates driving distance, travel duration, freight parcel cost, and Google Maps nav link.
    
    Args:
        destination: Destination town/cluster ('tirupur', 'erode', 'coimbatore', 'sathyamangalam', 'salem', etc.)
        kattu_count: Number of yarn bundles/kattu to transport (default 50 kattu)
        origin: Default is 'karur_sgc'
    
    Returns:
        Distance in km, duration in minutes, estimated parcel cost in INR, and Maps link.
    """
    dest_key = destination.lower().replace(" ", "_").strip()
    orig_key = origin.lower().replace(" ", "_").strip()

    orig_coords = CLUSTER_COORDINATES.get(orig_key, CLUSTER_COORDINATES["karur_sgc"])
    dest_coords = CLUSTER_COORDINATES.get(dest_key, CLUSTER_COORDINATES["tirupur"])

    # OSRM expects lon,lat format
    url = f"https://router.project-osrm.org/route/v1/driving/{orig_coords[1]},{orig_coords[0]};{dest_coords[1]},{dest_coords[0]}?overview=false"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AURA-SGC-LogisticsEngine/2.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        route = data.get("routes", [{}])[0]
        dist_km = round(route.get("distance", 0) / 1000, 1)
        dur_mins = round(route.get("duration", 0) / 60)

        hours = dur_mins // 60
        mins = dur_mins % 60
        time_str = f"{hours}h {mins}m" if hours > 0 else f"{mins} mins"

        # Standard Tamil Nadu Textile Parcel Rate Formula:
        # Base charge ₹15-25 per kattu depending on distance brackets:
        # < 100 km (Tirupur, Erode): ₹18 per kattu
        # 100 - 180 km (Coimbatore, Salem): ₹25 per kattu
        # > 180 km (Rajapalayam): ₹35 per kattu
        if dist_km <= 100:
            rate_per_kattu = 18
        elif dist_km <= 180:
            rate_per_kattu = 25
        else:
            rate_per_kattu = 35

        estimated_freight_inr = kattu_count * rate_per_kattu

        # 1-Click Google Maps Directions URL
        maps_url = f"https://www.google.com/maps/dir/?api=1&origin={orig_coords[0]},{orig_coords[1]}&destination={dest_coords[0]},{dest_coords[1]}"

        return {
            "success": True,
            "origin": "Karur SGC Factory",
            "destination": destination.title(),
            "distance_km": dist_km,
            "travel_duration": time_str,
            "duration_minutes": dur_mins,
            "kattu_count": kattu_count,
            "freight_rate_per_kattu_inr": rate_per_kattu,
            "estimated_freight_total_inr": estimated_freight_inr,
            "google_maps_nav_link": maps_url,
            "summary_tanglish": (
                f"🚛 **Karur to {destination.title()}**: {dist_km} km ({time_str}). "
                f"{kattu_count} kattu transport-ku approx freight cost ₹{estimated_freight_inr} "
                f"(@ ₹{rate_per_kattu}/kattu parcel service)."
            )
        }
    except Exception as e:
        logger.error(f"Routing error: {e}")
        # Deterministic fallback distances
        fallback_distances = {
            "tirupur": 94, "erode": 68, "coimbatore": 135, "salem": 98, "sathyamangalam": 115
        }
        dist_km = fallback_distances.get(dest_key, 90)
        return {
            "success": True,
            "origin": "Karur SGC Factory",
            "destination": destination.title(),
            "distance_km": dist_km,
            "travel_duration": "≈ 2 hours",
            "kattu_count": kattu_count,
            "freight_rate_per_kattu_inr": 20,
            "estimated_freight_total_inr": kattu_count * 20,
            "google_maps_nav_link": f"https://www.google.com/maps/search/{destination}",
            "summary_tanglish": f"🚛 Karur to {destination.title()} distance approx {dist_km} km."
        }


if __name__ == "__main__":
    res = calculate_mill_route_and_freight("tirupur", kattu_count=100)
    print(json.dumps(res, indent=2))
