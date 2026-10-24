"""
Model Context Protocol (MCP) Agent Bridge
Translates FastMCP Industrial Operations Server & Ecosystem Tools into
Dynamic LLM Tool Declarations with Strict Cognitive Routing & 2-Step Verification.
"""
import sys
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("mcp_agent_bridge")

# Ensure ecosystem is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ECOSYSTEM_DIR = BASE_DIR / "ecosystem"
for p in [str(BASE_DIR), str(ECOSYSTEM_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Import FastMCP server
try:
    import sgc_mcp_server
    FASTMCP_SERVER = sgc_mcp_server.mcp
except Exception as e:
    logger.error(f"Failed to load sgc_mcp_server: {e}")
    FASTMCP_SERVER = None

# Import ecosystem helper tools
from app.services.tools import (
    get_pc_vitals,
    scrape_spinning_mills,
    search_live_web,
    search_drive_vault,
    get_career_and_placement_intel,
    send_telegram_alert,
    get_sgc_latest_bill,
    get_sgc_first_bill,
    get_sgc_bill_by_number
)

def get_dynamic_mcp_tools() -> List[Dict[str, Any]]:
    """
    Introspects FastMCP server and returns OpenAI-compatible tool definitions.
    Dynamically exposes all 19 SGC Industrial Tools + Ecosystem tools.
    """
    tools = []
    
    # 1. Introspect FastMCP tools
    if FASTMCP_SERVER and hasattr(FASTMCP_SERVER, "_tool_manager"):
        for tool in FASTMCP_SERVER._tool_manager.list_tools():
            # Extract JSON schema
            properties = {}
            required = []
            if hasattr(tool, "parameters") and tool.parameters:
                params = tool.parameters
                if isinstance(params, dict):
                    properties = params.get("properties", {})
                    required = params.get("required", [])
                elif hasattr(params, "schema"):
                    schema = params.schema()
                    properties = schema.get("properties", {})
                    required = schema.get("required", [])

            tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or f"MCP tool: {tool.name}",
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                }
            })

    # 2. Add Essential Voice & Ecosystem Tools
    tools.extend([
        {
            "type": "function",
            "function": {
                "name": "get_sgc_latest_bill",
                "description": "Get details of the most recently created or latest bill/invoice for SGC (bill number, customer, amount, variety).",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "sgc_get_latest_bill",
                "description": "Get details of the latest bill/invoice for SGC.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_sgc_first_bill",
                "description": "Get details and exact date of the very first bill (Bill #1) ever created for SGC.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "sgc_get_first_bill",
                "description": "Get details and exact date of the very first bill (Bill #1) ever created for SGC.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_sgc_bill_by_number",
                "description": "Get details and date of a specific SGC invoice by bill number (e.g. bill 1, 2, 5, 9, 10).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "bill_no": {
                            "type": "integer",
                            "description": "The numeric invoice/bill number, e.g. 1"
                        }
                    },
                    "required": ["bill_no"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "sgc_get_bill_by_number",
                "description": "Get details of a specific SGC invoice by bill number.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "bill_no": {
                            "type": "integer",
                            "description": "The numeric invoice/bill number, e.g. 1"
                        }
                    },
                    "required": ["bill_no"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_pc_vitals",
                "description": "Get real-time CPU load, RAM usage, and battery percentage of Mukil's laptop.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "scrape_spinning_mills",
                "description": "Scrape live authentic Tamil Nadu B2B spinning mill leads and contacts from the web.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "district": {
                            "type": "string",
                            "description": "District in Tamil Nadu, e.g., 'Karur', 'Tirupur', 'Coimbatore'"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of mill leads to return (1 to 5)"
                        }
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "search_live_web",
                "description": "Search the live web for real-time news, weather, stock prices, textile yarn rates, or general facts.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The exact web search query."
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "search_drive_vault",
                "description": "Search files and documents in Mukil's 250GB Distributed Drive Mesh and Bills Vault.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search term (e.g., 'Priya Handlooms PDF', 'ATS Resume', 'Node 05')"
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "send_telegram_alert",
                "description": "Send an urgent high-priority notification to Mukil's phone via Telegram.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "The message text to send to Mukil."
                        }
                    },
                    "required": ["message"]
                }
            }
        }
    ])

    return tools

async def execute_mcp_or_system_tool(tool_name: str, args: Dict[str, Any]) -> str:
    """
    Executes tool either via FastMCP server or ecosystem dispatcher.
    Returns 100% deterministic ground-truth observation string.
    """
    logger.info(f"[Tool Execution] Invoking '{tool_name}' with args {args}")
    
    # 1. Check if FastMCP tool
    if FASTMCP_SERVER and hasattr(FASTMCP_SERVER, "_tool_manager"):
        mcp_tool = FASTMCP_SERVER._tool_manager.get_tool(tool_name)
        if mcp_tool:
            try:
                result = await mcp_tool.run(args)
                out_str = str(result)
                # Keep tool output under 600 chars to prevent Groq TPM rate limiting
                if len(out_str) > 600:
                    out_str = out_str[:600] + "\n...[Summary truncated for voice latency]"
                return out_str
            except Exception as e:
                logger.error(f"[FastMCP Error] Tool '{tool_name}' failed: {e}")
                return f"FastMCP tool error: {str(e)}"

    # 2. Check Ecosystem Tools
    try:
        if tool_name in ["get_sgc_latest_bill", "sgc_get_latest_bill"]:
            return get_sgc_latest_bill()
        elif tool_name in ["get_sgc_first_bill", "sgc_get_first_bill"]:
            return get_sgc_first_bill()
        elif tool_name in ["get_sgc_bill_by_number", "sgc_get_bill_by_number"]:
            b_num = int(args.get("bill_no", 1))
            return get_sgc_bill_by_number(b_num)
        elif tool_name == "get_pc_vitals":
            return get_pc_vitals()
        elif tool_name == "scrape_spinning_mills":
            dist = args.get("district", "Karur")
            max_r = int(args.get("max_results", 3))
            return scrape_spinning_mills(district=dist, max_results=max_r)
        elif tool_name == "search_live_web":
            return search_live_web(args.get("query", ""))
        elif tool_name == "search_drive_vault":
            return search_drive_vault(args.get("query", ""))
        elif tool_name == "send_telegram_alert":
            return send_telegram_alert(args.get("message", ""))
    except Exception as e:
        logger.error(f"[Ecosystem Tool Error] '{tool_name}' failed: {e}")
        return f"Tool execution failed: {str(e)}"

    return f"Tool '{tool_name}' not found in MCP registry."
