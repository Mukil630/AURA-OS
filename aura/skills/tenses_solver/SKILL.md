---
name: tenses-screen-solver
description: Autonomous Screen Vision & Placement Assessment Solver. Use when Mukil asks to solve questions on Tenses.ai, Versant, Mettl, LeetCode, or online placement exams directly from screen.
---

# Tenses & Placement Test Screen-Vision Solver

## 📌 Mission
Autonomously captures Mukil's PC screen, reads questions/prompts via Gemini Multimodal Vision, generates top-grade answers, and executes human-like keystroke simulation to bypass paste-prevention proctoring.

## 🚀 Execution Directives
- Screen capture via `inspect_screen` or `FastOSController`.
- Direct execution script: `python C:\Users\mukil\tenses_ai_agent.py --solve-now --speed normal`
- Global Daemon Hotkeys:
  * `[F9]`: Screen Snap -> Antigravity Vision Analysis -> Auto-Type into active cursor
  * `[F8]`: Human-like typing of clipboard content (bypasses anti-paste javascript)
  * `[ESC]`: Emergency abort keystrokes
- Human Cadence: 35ms-75ms randomized keystroke delay (~65-75 WPM) with natural sentence punctuation pauses.
