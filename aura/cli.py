"""
AURA OS Interactive CLI Terminal
Modeled directly on Google Antigravity (AGY) CLI.
Supports interactive REPL loop, streaming tokens, tool indicators, and slash commands.
"""
import sys
import os
import re

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from pathlib import Path

# Fix Windows console UTF-8 output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from colorama import init, Fore, Style
from aura.kernel.agent import AuraAgent
from aura.tools.registry import registry
from aura.tools.voice_tools import speak_voice, list_voice_personas, set_active_persona

init(autoreset=True)

BANNER = f"""{Fore.CYAN}
   █████╗ ██╗   ██╗██████╗  █████╗      ██████╗ ███████╗
  ██╔══██╗██║   ██║██╔══██╗██╔══██╗    ██╔═══██╗██╔════╝
  ███████║██║   ██║██████╔╝███████║    ██║   ██║███████╗
  ██╔══██║██║   ██║██╔══██╗██╔══██║    ██║   ██║╚════██║
  ██║  ██║╚██████╔╝██║  ██║██║  ██║    ╚██████╔╝███████║
  ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝     ╚═════╝ ╚══════╝
{Fore.YELLOW}  >> AURA OS v3 // Supreme Autonomous Partner for Mukil <<
{Fore.GREEN}  >> Sub-Second Latency · Strict Zero-Hallucination · Self-Healing <<
{Style.RESET_ALL}"""

HELP_TEXT = f"""
{Fore.CYAN}AURA CLI Commands:{Style.RESET_ALL}
  {Fore.YELLOW}/help{Style.RESET_ALL}       - Show this help message
  {Fore.YELLOW}/tools{Style.RESET_ALL}      - List all active registered tools
  {Fore.YELLOW}/voice{Style.RESET_ALL}      - Toggle neural voice playback ({Fore.GREEN}/voice on{Style.RESET_ALL} or {Fore.RED}/voice off{Style.RESET_ALL})
  {Fore.YELLOW}/voices{Style.RESET_ALL}     - List all available neural voice personas
  {Fore.YELLOW}/clear{Style.RESET_ALL}      - Clear the terminal screen
  {Fore.YELLOW}/reset{Style.RESET_ALL}      - Reset the conversation context
  {Fore.YELLOW}/exit{Style.RESET_ALL}       - Exit AURA CLI (or Ctrl+C)
"""

def print_tools():
    schemas = registry.get_schemas()
    print(f"\n{Fore.CYAN}Registered Superpowers & Tools ({len(schemas)}):{Style.RESET_ALL}")
    for s in schemas:
        fn = s["function"]
        print(f"  {Fore.GREEN}• {fn['name']}{Style.RESET_ALL} : {fn['description']}")
    print()

def main():
    agent = AuraAgent()
    voice_mode = False
    
    # If arguments are passed on command line, run single-shot mode (like `agy "prompt"`)
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        print(f"{Fore.CYAN}[AURA Processing Task]:{Style.RESET_ALL} {prompt}\n")
        for event_type, content in agent.chat_stream(prompt):
            if event_type == "thought":
                print(f"\n{Fore.MAGENTA}🧠 [Planning & Reasoning]: {content}{Style.RESET_ALL}")
            elif event_type == "tool_call":
                print(f"\n{Fore.YELLOW}⚙️  [Tool Selection & Action]: {content}{Style.RESET_ALL}")
            elif event_type in ["observation", "tool_result"]:
                print(f"{Fore.LIGHTBLACK_EX}👁️  [Observation]: {content}{Style.RESET_ALL}\n")
            elif event_type == "token":
                sys.stdout.write(f"{Fore.WHITE}{content}{Style.RESET_ALL}")
                sys.stdout.flush()
            elif event_type == "error":
                print(f"\n{Fore.RED}❌ {content}{Style.RESET_ALL}")
        print()
        return

    # Otherwise enter interactive loop
    print(BANNER)
    print(f"{Fore.LIGHTBLUE_EX}Type your message in Tanglish or English. Type {Fore.YELLOW}/help{Fore.LIGHTBLUE_EX} for commands.{Style.RESET_ALL}\n")
    
    while True:
        try:
            user_input = input(f"{Fore.GREEN}Mukil > {Style.RESET_ALL}").strip()
            
            if not user_input:
                continue
                
            # Table borders & empty separator filter (ignores lines like ───┼─── or │   │)
            clean_chars = re.sub(r'[\─\-\|\+\┼\s\:\│]', '', user_input)
            if not clean_chars or len(clean_chars) < 2:
                continue

            if user_input in ["/exit", "/quit", "exit", "quit"]:
                print(f"{Fore.CYAN}AURA: Seri mapla, paapom! Take care! 🚀{Style.RESET_ALL}")
                break
                
            if user_input == "/help":
                print(HELP_TEXT)
                continue
                
            if user_input == "/tools":
                print_tools()
                continue
                
            if user_input.startswith("/voice"):
                parts = user_input.split()
                if len(parts) > 1:
                    arg = parts[1].lower()
                    if arg in ["on", "enable", "true"]:
                        voice_mode = True
                        print(f"{Fore.GREEN}🔊 AURA Neural Voice Mode: ENABLED. I'll speak replies with Google Gemini Audio!{Style.RESET_ALL}\n")
                    elif arg in ["off", "disable", "false"]:
                        voice_mode = False
                        print(f"{Fore.YELLOW}🔇 AURA Neural Voice Mode: DISABLED (Silent text mode).{Style.RESET_ALL}\n")
                    else:
                        alias_map = {
                            "stark": "MORNING_WAKEUP",
                            "morning": "MORNING_WAKEUP",
                            "wakeup": "MORNING_WAKEUP",
                            "beast": "WORKOUT_BEAST",
                            "gym": "WORKOUT_BEAST",
                            "workout": "WORKOUT_BEAST",
                            "business": "BUSINESS_FINANCE",
                            "finance": "BUSINESS_FINANCE",
                            "sgc": "BUSINESS_FINANCE",
                            "jarvis": "JARVIS",
                            "cinematic": "JARVIS",
                            "friend": "CARING_FRIEND",
                            "kongu": "CARING_FRIEND",
                            "friday": "FRIDAY",
                            "english": "ENGLISH_PRO"
                        }
                        chosen = alias_map.get(arg, arg.upper())
                        res = set_active_persona(chosen)
                        print(f"{Fore.CYAN}{res}{Style.RESET_ALL}\n")
                else:
                    voice_mode = not voice_mode
                    status = "ENABLED" if voice_mode else "DISABLED"
                    print(f"{Fore.CYAN}🔊 Voice Mode toggled: {status}{Style.RESET_ALL}\n")
                continue

            if user_input == "/voices":
                print(f"\n{list_voice_personas()}\n")
                continue
                
            if user_input == "/clear":
                os.system("cls" if os.name == "nt" else "clear")
                print(BANNER)
                continue
                
            if user_input == "/reset":
                agent.reset()
                print(f"{Fore.YELLOW}AURA: Memory reset aaiduchu mapla. Fresh conversation started!{Style.RESET_ALL}\n")
                continue

            # Stream Agent Response
            print(f"\n{Fore.CYAN}AURA > {Style.RESET_ALL}", end="", flush=True)
            full_response = []
            for event_type, content in agent.chat_stream(user_input):
                if event_type == "thought":
                    print(f"\n{Fore.MAGENTA}🧠 [Planning & Reasoning]: {content}{Style.RESET_ALL}")
                elif event_type == "tool_call":
                    print(f"\n{Fore.YELLOW}⚙️  [Tool Selection & Action]: {content}{Style.RESET_ALL}")
                elif event_type in ["observation", "tool_result"]:
                    print(f"{Fore.LIGHTBLACK_EX}👁️  [Observation]: {content}{Style.RESET_ALL}\n{Fore.CYAN}AURA > {Style.RESET_ALL}", end="", flush=True)
                elif event_type == "token":
                    sys.stdout.write(content)
                    sys.stdout.flush()
                    full_response.append(content)
                elif event_type == "error":
                    print(f"\n{Fore.RED}❌ {content}{Style.RESET_ALL}")
            print("\n")

            if voice_mode and full_response:
                speak_voice("".join(full_response))

        except KeyboardInterrupt:
            print(f"\n{Fore.CYAN}AURA: Exited cleanly. Catch you later mapla! 🚀{Style.RESET_ALL}")
            break
        except Exception as e:
            print(f"\n{Fore.RED}Error: {str(e)}{Style.RESET_ALL}\n")

if __name__ == "__main__":
    main()
