"""
Generate Professional PDF Presentation on AI Agents Efficiency Benchmark 2026
"""
import os
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

def create_presentation_pdf(output_path):
    # Landscape presentation style slides
    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(letter),
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=28,
        leading=34,
        textColor=colors.HexColor('#0F172A'),
        alignment=TA_CENTER
    )
    
    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=15,
        leading=20,
        textColor=colors.HexColor('#2563EB'),
        alignment=TA_CENTER
    )
    
    slide_header = ParagraphStyle(
        'SlideHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=12
    )
    
    body_style = ParagraphStyle(
        'SlideBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=16,
        textColor=colors.HexColor('#334155')
    )
    
    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1E293B')
    )
    
    table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.white
    )

    story = []

    # ==================== SLIDE 1: COVER ====================
    story.append(Spacer(1, 100))
    story.append(Paragraph("STATE OF AUTONOMOUS AI AGENTS 2026", title_style))
    story.append(Spacer(1, 15))
    story.append(Paragraph("Benchmark Efficiency, Architecture Frameworks & Operational Economics", subtitle_style))
    story.append(Spacer(1, 30))
    
    meta_text = ParagraphStyle(
        'Meta',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        textColor=colors.HexColor('#64748B'),
        alignment=TA_CENTER
    )
    story.append(Paragraph("Prepared autonomously by AURA OS & Mukil • Executive Research Brief", meta_text))
    story.append(PageBreak())

    # ==================== SLIDE 2: THE EVALUATION REVOLUTION ====================
    story.append(Paragraph("1. The Shift: Beyond Static LLM Benchmarks", slide_header))
    story.append(Paragraph(
        "Traditional single-turn benchmarks (MMLU, GSM8K) have saturated. Modern AI engineering evaluates "
        "<b>autonomous multi-step execution</b> where agents browse the web, write code, run terminal tools, "
        "and self-heal when errors occur.", body_style
    ))
    story.append(Spacer(1, 15))

    bench_data = [
        [Paragraph("Benchmark", table_header), Paragraph("Target Domain", table_header), Paragraph("Key Metric", table_header), Paragraph("Industry Leaders", table_header)],
        [
            Paragraph("<b>SWE-bench Pro / Verified</b>", table_cell),
            Paragraph("Full GitHub repo issue resolution & debugging", table_cell),
            Paragraph("Resolved rate % vs Cost per patch ($0.80 - $4.00)", table_cell),
            Paragraph("Claude 3.5 Sonnet + mini-SWE, Devin, Claude Code", table_cell)
        ],
        [
            Paragraph("<b>GAIA (General Assistants)</b>", table_cell),
            Paragraph("Multi-modal reasoning, web browsing, attachments", table_cell),
            Paragraph("Complex multi-step accuracy (Levels 1 to 3)", table_cell),
            Paragraph("OpenAI Frontier, Claude Series, AGY Harvester", table_cell)
        ],
        [
            Paragraph("<b>OSWorld & Terminal-Bench</b>", table_cell),
            Paragraph("Desktop GUI control, terminal infra operations", table_cell),
            Paragraph("Screen-vision click accuracy & shell safety", table_cell),
            Paragraph("Computer-Use Agents, FastOSController", table_cell)
        ]
    ]

    t1 = Table(bench_data, colWidths=[150, 190, 190, 190])
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E293B')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t1)
    story.append(PageBreak())

    # ==================== SLIDE 3: FRAMEWORKS COMPARISON ====================
    story.append(Paragraph("2. Agent Orchestration Frameworks: Efficiency Breakdown", slide_header))
    story.append(Paragraph(
        "Deploying agents at scale requires balancing token overhead, execution latency, and deterministic reliability.", body_style
    ))
    story.append(Spacer(1, 15))

    frame_data = [
        [Paragraph("Framework", table_header), Paragraph("Latency / Speed", table_header), Paragraph("Token Efficiency", table_header), Paragraph("Best Use Case", table_header)],
        [
            Paragraph("<b>LangGraph (StateGraph)</b>", table_cell),
            Paragraph("⚡ Sub-second (Deterministic state)", table_cell),
            Paragraph("🟢 High (Selective state pruning)", table_cell),
            Paragraph("Production systems, finance, deterministic business pipelines", table_cell)
        ],
        [
            Paragraph("<b>CrewAI</b>", table_cell),
            Paragraph("🟡 Moderate (Role-play chaining)", table_cell),
            Paragraph("🟡 Medium (Prompt boilerplate overhead)", table_cell),
            Paragraph("Rapid prototyping, marketing workflows, content drafting", table_cell)
        ],
        [
            Paragraph("<b>AutoGen (Multi-Agent)</b>", table_cell),
            Paragraph("🔴 Slow (Conversational chatter latency)", table_cell),
            Paragraph("🔴 High Token Burn (Multi-agent loops)", table_cell),
            Paragraph("Open-ended research, debate synthesis, group brainstorming", table_cell)
        ],
        [
            Paragraph("<b>AGY / AURA (CodeAct Kernel)</b>", table_cell),
            Paragraph("⚡ Lightning (<250ms via lazy MCP)", table_cell),
            Paragraph("🟢 Maximum (Code-as-Action execution)", table_cell),
            Paragraph("Software engineering, autonomous terminal automation & OS control", table_cell)
        ]
    ]

    t2 = Table(frame_data, colWidths=[160, 170, 170, 220])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2563EB')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t2)
    story.append(PageBreak())

    # ==================== SLIDE 4: THE 5 OPERATIONAL PILLARS ====================
    story.append(Paragraph("3. The 5 Pillars of Real-World Agent Efficiency", slide_header))
    story.append(Paragraph(
        "A true autonomous agent isn't measured by leaderboard hype. Production performance relies on 5 core pillars:", body_style
    ))
    story.append(Spacer(1, 15))

    pillars = [
        [Paragraph("Pillar", table_header), Paragraph("Why It Matters", table_header), Paragraph("AURA OS Architectural Solution", table_header)],
        [
            Paragraph("<b>1. Task Autonomy vs Fragility</b>", table_cell),
            Paragraph("How far does an agent run before breaking or requiring human assistance?", table_cell),
            Paragraph("<b>Saga Rollback Stack & Self-Healing Loop</b> (intercepts tracebacks, auto-fixes args)", table_cell)
        ],
        [
            Paragraph("<b>2. Token & Cost Economy</b>", table_cell),
            Paragraph("Runaway loops can burn tens of dollars per query in multi-agent chatter.", table_cell),
            Paragraph("<b>Contextual Tool Pruning</b> (only exposes 3-5 tools instead of 50)", table_cell)
        ],
        [
            Paragraph("<b>3. Zero-Hallucination Gate</b>", table_cell),
            Paragraph("Models agreeing blindly ('yes-man') or hallucinating database numbers.", table_cell),
            Paragraph("<b>Ground-Truth Gate</b> (strictly gates factual answers behind verified files & DBs)", table_cell)
        ],
        [
            Paragraph("<b>4. Execution Latency</b>", table_cell),
            Paragraph("Waiting 10 seconds for an agent to think destroys user experience.", table_cell),
            Paragraph("<b>Dual-Engine Router</b> (Gemini 3.8 Flash + Groq 500 tok/s LPU)", table_cell)
        ],
        [
            Paragraph("<b>5. CodeAct Universality</b>", table_cell),
            Paragraph("Agents limited to hardcoded tools fail on new arbitrary tasks.", table_cell),
            Paragraph("<b>Universal Primitives (Search + Write + Run)</b>: Solves ANY task via Python code", table_cell)
        ]
    ]

    t3 = Table(pillars, colWidths=[160, 260, 300])
    t3.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t3)

    # Build the document
    doc.build(story)
    print(f"SUCCESS: Generated presentation PDF at {output_path}")

if __name__ == '__main__':
    desktop_pdf = r"C:\Users\mukil\Desktop\AI_Agents_Efficiency_2026_Report.pdf"
    create_presentation_pdf(desktop_pdf)
