"""
AURA OS 250GB Distributed Drive Mesh Tool
10 Dedicated Nodes x 25GB = 250GB Unified Cloud Mesh
"""
import json
from pathlib import Path

MESH_PATH = Path("C:/Users/mukil/jarvis-core/storage/memory/distributed_drive_mesh.json")

def get_drive_mesh_status() -> str:
    """
    Returns the live status, node allocations, and folder links for Mukil's
    250GB Distributed Google Drive Mesh (10 dedicated nodes).
    """
    if not MESH_PATH.exists():
        return "Error: Drive Mesh configuration file not found at jarvis-core/storage/memory/distributed_drive_mesh.json"
    
    try:
        with open(MESH_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        nodes = data.get("nodes", {})
        total_capacity = data.get("mesh_capacity_gb", 250)
        
        output = [
            f"🌐 **Mukil's 250GB Distributed Drive Mesh ({len(nodes)} Dedicated Nodes)**",
            f"• Total Pooled Mesh Storage: {total_capacity} GB",
            ""
        ]
        
        for node_id, info in nodes.items():
            name = info.get("name", "Node")
            purpose = info.get("purpose", "")
            folder_id = info.get("folder_id", "")
            output.append(f"• **{node_id.upper()} ({name})**: `{folder_id}`\n  Purpose: {purpose}")
            
        return "\n".join(output)
    except Exception as e:
        return f"Error reading Drive Mesh registry: {str(e)}"


def get_master_resume_link() -> str:
    """
    Returns Mukil's official ATS Master Resume Drive link and active placement folder.
    """
    return (
        "📄 **Mukil's Master ATS Resume Link (Official):**\n"
        "• URL: https://drive.google.com/file/d/1TpyzV7OGEf-YQfGLUpusAI5cDDvF1kAJ/view?usp=drive_link\n"
        "• Drive Node: Node 03 (Placement ATS Resumes & Portfolios - `1rl5EhQCcTiyyrVXp57l4P-4Bd76Q7YM2`)\n"
        "• ATS Score Benchmark: 95% - 98%"
    )
