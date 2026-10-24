"""
AURA Progressive Disclosure Skill System
File: aura/kernel/skill_loader.py
Reverse-engineered from Google Antigravity (AGY) Skills Engine:
- Discovers SKILL.md files on disk with YAML frontmatter.
- Keeps base prompt lightweight.
- Dynamically loads and injects only the matching skills when triggered by user prompt.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"


class Skill:
    def __init__(self, name: str, description: str, content: str, path: Path):
        self.name = name
        self.description = description
        self.content = content
        self.path = path


class SkillRegistry:
    def __init__(self, root_dir: Path = SKILLS_ROOT):
        self.root_dir = root_dir
        self.skills: Dict[str, Skill] = {}
        self.discover_skills()

    def discover_skills(self):
        """Scans skills directory for all SKILL.md files."""
        self.skills.clear()
        if not self.root_dir.exists():
            return

        for skill_file in self.root_dir.rglob("SKILL.md"):
            try:
                text = skill_file.read_text(encoding="utf-8")
                # Parse frontmatter
                fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', text, re.DOTALL)
                if fm_match:
                    fm_text, body = fm_match.group(1), fm_match.group(2)
                    name = ""
                    desc = ""
                    for line in fm_text.splitlines():
                        if line.startswith("name:"):
                            name = line.split("name:", 1)[1].strip()
                        elif line.startswith("description:"):
                            desc = line.split("description:", 1)[1].strip()
                    if name:
                        self.skills[name] = Skill(name=name, description=desc, content=body.strip(), path=skill_file)
            except Exception as e:
                pass

    def get_skill_catalog_prompt(self) -> str:
        """Returns a compact catalog of available skills for routing."""
        if not self.skills:
            return ""
        lines = ["Available Specialized Skills (Loaded On-Demand):"]
        for s in self.skills.values():
            lines.append(f"- **{s.name}**: {s.description}")
        return "\n".join(lines)

    def match_skills(self, user_prompt: str) -> List[Skill]:
        """Matches relevant skills based on user prompt tokens."""
        prompt_lower = user_prompt.lower()
        matched = []
        
        # Skill trigger keywords mapping
        triggers = {
            "sgc-billing": ["sgc", "bill", "invoice", "overdue", "dyeing", "shade", "ledger", "mill balance"],
            "washing-unit-operations": ["washing", "unit", "hub", "enzyme", "bio-polish", "silicon", "softener", "inward", "lot"],
            "placement-ats-hunter": ["job", "placement", "resume", "tcs", "infinite", "zoho", "amazon", "accenture", "leetcode", "interview"],
            "screen-vision-pilot": ["screen", "look at", "see my screen", "vision", "solve question", "tenses", "exam question"]
        }

        for skill_name, keywords in triggers.items():
            if skill_name in self.skills:
                if any(kw in prompt_lower for kw in keywords):
                    matched.append(self.skills[skill_name])

        return matched


# Global Skill Registry Singleton
skill_registry = SkillRegistry()
