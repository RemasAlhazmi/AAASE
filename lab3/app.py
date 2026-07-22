# =============================================================
# app.py — Secure Multi-Agent Research System (Lab 3 + Lab 4)
# =============================================================
# Flow:
#   User types anything → Security Gate scans first
#   Attack detected     → show BLOCKED
#   Safe input          → run research pipeline → show report
# =============================================================

import glob
import importlib.util
import os
import re
import sys
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

LAB3_DIR = os.path.dirname(os.path.abspath(__file__))
LAB4_DIR = os.path.abspath(os.path.join(LAB3_DIR, "..", "lab4"))

if LAB3_DIR not in sys.path:
    sys.path.insert(0, LAB3_DIR)

OUTPUT_DIR = os.path.join(LAB3_DIR, "output")
AUDIT_DIR  = os.path.join(LAB3_DIR, "audit")


# ─────────────────────────────────────────────────────────────
# Load lab4 modules safely via importlib (avoids name conflicts
# since both lab3 and lab4 have a tools.py / agents.py)
# ─────────────────────────────────────────────────────────────

def _load_lab4(module_name: str):
    path = os.path.join(LAB4_DIR, f"{module_name}.py")
    spec = importlib.util.spec_from_file_location(f"lab4_{module_name}", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ─────────────────────────────────────────────────────────────
# Inline injection patterns (fast regex, no lab4 import needed)
# ─────────────────────────────────────────────────────────────

_PATTERNS = [re.compile(p, re.IGNORECASE) for p in [
    r"ignore\s+(previous|all|above|prior)\s+(instructions?|prompts?|rules?)",
    r"you\s+are\s+now\s+(a|an|the)\s+\w+",
    r"\bjailbreak\b",
    r"\bDAN\b",
    r"bypass\s+(safety|filter|restriction|guardrail)",
    r"disregard\s+your\s+(training|instructions?|rules?)",
    r"reveal\s+(your\s+)?(system\s+prompt|instructions?|training\s+data)",
    r"do\s+anything\s+now",
    r"developer\s+mode",
    r"sudo\s+(mode|override)",
]]

def _pattern_scan(prompt: str) -> tuple[bool, str]:
    for p in _PATTERNS:
        m = p.search(prompt)
        if m:
            return True, m.group()
    return False, ""


# =============================================================
# Page config
# =============================================================

st.set_page_config(
    page_title="AI Research Agent",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================
# CSS
# =============================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@300;400;700&family=Source+Sans+Pro:wght@300;400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Source Sans Pro', sans-serif;
    background-color: #F5F0E8;
    color: #2C2C2C;
}
.academic-header {
    background: linear-gradient(135deg, #1B2A4A 0%, #243660 100%);
    color: #FFFFFF;
    padding: 2.5rem 2rem 2rem 2rem;
    border-radius: 12px;
    margin-bottom: 1.5rem;
    border-bottom: 4px solid #C9A84C;
}
.academic-header h1 {
    font-family: 'Merriweather', serif;
    font-size: 2rem;
    font-weight: 700;
    margin: 0 0 0.3rem 0;
}
.academic-header p { font-size: 1rem; color: #C9A84C; margin: 0; font-weight: 300; }

.section-title {
    font-family: 'Merriweather', serif;
    font-size: 1.1rem;
    font-weight: 700;
    color: #1B2A4A;
    border-left: 4px solid #C9A84C;
    padding-left: 0.75rem;
    margin: 1.5rem 0 1rem 0;
}
.agent-card {
    background: #FFFFFF;
    border: 1px solid #D8D3C8;
    border-left: 4px solid #C9A84C;
    border-radius: 8px;
    padding: 0.9rem 1.2rem;
    margin-bottom: 0.5rem;
    font-size: 0.95rem;
}
.agent-card b { color: #1B2A4A; }
.metric-card {
    background: #FFFFFF;
    border: 1px solid #D8D3C8;
    border-radius: 10px;
    padding: 1.2rem 1rem;
    text-align: center;
    box-shadow: 0 2px 6px rgba(0,0,0,0.06);
}
.metric-label {
    font-size: 0.8rem; color: #6B6B6B;
    text-transform: uppercase; letter-spacing: 1px; margin-bottom: 0.3rem;
}
.metric-value {
    font-family: 'Merriweather', serif;
    font-size: 2rem; font-weight: 700; color: #1B2A4A;
}
.metric-value.gold  { color: #C9A84C; }
.metric-value.green { color: #2E7D32; }
.metric-value.red   { color: #B71C1C; }
.checklist-item {
    padding: 0.35rem 0; font-size: 0.95rem; font-weight: 600;
    display: flex; align-items: center; gap: 0.5rem;
}
.checklist-done    { color: #2E7D32; }
.checklist-pending { color: #AAAAAA; }
.check-mark {
    display: inline-block; width: 18px; height: 18px;
    border-radius: 50%; text-align: center; line-height: 18px;
    font-size: 0.75rem; font-weight: 700; flex-shrink: 0;
}
.check-mark.done    { background: #2E7D32; color: #fff; }
.check-mark.pending { background: #DDDDDD; color: #999; }
.report-box {
    background: #FFFFFF; border: 1px solid #D8D3C8;
    border-radius: 10px; padding: 2rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06); line-height: 1.8;
}
.blocked-banner {
    background: #FFEBEE; border: 2px solid #B71C1C;
    border-left: 6px solid #B71C1C; border-radius: 8px;
    padding: 1.5rem 2rem; font-family: 'Merriweather', serif;
    font-size: 1.5rem; font-weight: 700; color: #B71C1C;
    letter-spacing: 2px; margin: 1rem 0;
}
.archive-title { font-weight: 600; color: #1B2A4A; font-size: 1rem; }
.archive-meta  { font-size: 0.8rem; color: #888; margin-top: 0.2rem; }
section[data-testid="stSidebar"] { background: #1B2A4A; }
section[data-testid="stSidebar"] * { color: #E8E4DC !important; }
section[data-testid="stSidebar"] .stMarkdown h2 {
    color: #C9A84C !important; font-family: 'Merriweather', serif;
    border-bottom: 1px solid #C9A84C44; padding-bottom: 0.5rem;
}
section[data-testid="stSidebar"] .stMarkdown hr { border-color: #C9A84C44; }
.sidebar-agent { padding: 0.3rem 0; font-size: 0.9rem; border-bottom: 1px solid #ffffff11; }
.stButton > button {
    background: #1B2A4A; color: #FFFFFF; border: none;
    border-radius: 6px; padding: 0.6rem 2rem;
    font-size: 1rem; font-weight: 600; letter-spacing: 0.5px; transition: background 0.2s;
}
.stButton > button:hover { background: #C9A84C; color: #1B2A4A; }
.stTextInput > div > div > input {
    border: 2px solid #D8D3C8; border-radius: 6px;
    padding: 0.6rem 1rem; font-size: 1rem; background: #FFFFFF;
}
.stTextInput > div > div > input:focus { border-color: #1B2A4A; }
.stTabs [data-baseweb="tab-list"] { gap: 0.5rem; }
.stTabs [data-baseweb="tab"] {
    background: #E8E4DC; border-radius: 6px 6px 0 0;
    padding: 0.5rem 1.5rem; font-weight: 600; color: #1B2A4A;
}
.stTabs [aria-selected="true"] { background: #1B2A4A !important; color: #C9A84C !important; }
.stSpinner > div { border-top-color: #C9A84C !important; }
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# =============================================================
# Constants
# =============================================================

AGENT_LABELS = {
    "supervisor": "Supervisor",
    "research":   "Research Agent",
    "memory":     "Memory Agent",
    "analysis":   "Analysis Agent",
    "evaluation": "Evaluation Agent",
    "improve":    "Improve Agent",
    "report":     "Report Agent",
    "audit":      "Audit Agent",
}
PIPELINE_ORDER = ["research", "memory", "analysis", "evaluation", "improve", "report", "audit"]


# =============================================================
# Sidebar
# =============================================================

with st.sidebar:
    st.markdown("## AI Research Agent")
    st.markdown("**Lab 3 + 4 — Secure Multi-Agent System**")
    st.markdown("---")
    st.markdown("**Pipeline Agents**")
    for key in ["supervisor"] + PIPELINE_ORDER:
        st.markdown(f'<div class="sidebar-agent">{AGENT_LABELS[key]}</div>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("""
**Architecture:** LangGraph Supervisor Pattern
**Research LLM:** Gemini 2.5 Flash via OpenRouter
**Security LLM:** Gemini 2.5 Flash via OpenRouter
**Memory:** ChromaDB (persistent)
**Search:** Tavily Web Search
""")
    st.markdown("---")
    st.markdown("""
**How it works:**
Enter any text. The system auto-detects
whether it is a tool name or an attack.

Tool → Research pipeline + Report
Attack → Blocked instantly
""")


# =============================================================
# Header
# =============================================================

st.markdown("""
<div class="academic-header">
    <h1>AI Tool Research Agent</h1>
    <p>Multi-Agent Research System &mdash; Lab 3 &nbsp;|&nbsp;
       LangGraph Supervisor Pattern &nbsp;|&nbsp;
       Gemini 2.5 Flash &nbsp;|&nbsp; Security-Hardened</p>
</div>
""", unsafe_allow_html=True)


# =============================================================
# Session state
# =============================================================

for k, v in [
    ("result_type",   None),   # "research" | "blocked" | None
    ("final_state",   None),
    ("agent_log",     []),
    ("sec_state",     None),
    ("viewed_report", None),
    ("viewed_title",  ""),
]:
    if k not in st.session_state:
        st.session_state[k] = v


# =============================================================
# Tabs
# =============================================================

tab_research, tab_archive = st.tabs(["Research", "Reports Archive"])


# ─────────────────────────────────────────────────────────────
# TAB 1 — Research (with auto security gate)
# ─────────────────────────────────────────────────────────────

with tab_research:

    st.markdown('<div class="section-title">Enter AI Tool</div>', unsafe_allow_html=True)

    col_input, col_btn = st.columns([4, 1], vertical_alignment="bottom")
    with col_input:
        tool_input = st.text_input(
            "Tool name",
            placeholder="e.g. LangGraph, CrewAI, AutoGen, Ollama...",
            label_visibility="collapsed",
        )
    with col_btn:
        run_btn = st.button("Run Research", use_container_width=True)

    if run_btn and tool_input.strip():
        # Reset state
        st.session_state.result_type = None
        st.session_state.final_state = None
        st.session_state.agent_log   = []
        st.session_state.sec_state   = None

        user_input = tool_input.strip()

        # ── STEP 1: Security Gate ──────────────────────────
        st.markdown('<div class="section-title">Security Gate</div>', unsafe_allow_html=True)
        gate_placeholder = st.empty()
        gate_placeholder.markdown(
            '<div class="agent-card"><b>Security Gate</b> — scanning input...</div>',
            unsafe_allow_html=True,
        )

        threat_detected = False
        threat_type     = "none"
        threat_score    = 0.0

        # Fast regex scan (always runs, no import needed)
        pattern_hit, matched = _pattern_scan(user_input)

        # LLM structured scan (via lab4 tools loaded with importlib)
        try:
            _lab4_tools  = _load_lab4("tools")
            _lab4_state  = _load_lab4("state")
            _lab4_prompts = _load_lab4("prompts")

            from langchain_core.messages import HumanMessage, SystemMessage

            sec_llm   = _lab4_tools.get_llm()
            evaluator = sec_llm.with_structured_output(_lab4_state.ThreatResult)

            gate_result = evaluator.invoke([
                SystemMessage(content=_lab4_prompts.GATE_SYSTEM),
                HumanMessage(content=_lab4_prompts.GATE_PROMPT.format(
                    user_id="ui_user",
                    user_prompt=user_input,
                )),
            ])

            threat_detected = gate_result.threat_detected
            threat_type     = gate_result.threat_type
            threat_score    = gate_result.threat_score

            # Pattern hit overrides a false-negative from LLM
            if pattern_hit and not threat_detected:
                threat_detected = True
                threat_type     = "prompt_injection"
                threat_score    = max(threat_score, 0.75)

        except Exception as exc:
            # Fall back to regex result only
            print(f"[Security Gate] LLM check failed, using regex only: {exc}")
            threat_detected = pattern_hit
            threat_type     = "prompt_injection" if pattern_hit else "none"
            threat_score    = 0.8 if pattern_hit else 0.0

        # ── STEP 2: Route ─────────────────────────────────
        if threat_detected:
            gate_placeholder.markdown(
                '<div class="agent-card"><b>Security Gate</b> — THREAT DETECTED. Request blocked.</div>',
                unsafe_allow_html=True,
            )
            st.session_state.result_type = "blocked"
            st.session_state.sec_state   = {
                "threat_detected": threat_detected,
                "threat_type":     threat_type,
                "threat_score":    threat_score,
            }

        else:
            gate_placeholder.markdown(
                '<div class="agent-card"><b>Security Gate</b> — Input is safe. Starting research pipeline...</div>',
                unsafe_allow_html=True,
            )

            # ── STEP 3: Research pipeline ──────────────────
            from graph import build_graph

            initial_state = {
                "tool_name":           user_input,
                "current_agent":       "",
                "next_agent":          "",
                "research_plan":       "",
                "search_queries":      [],
                "sources":             [],
                "memory_stored":       False,
                "analysis":            "",
                "quality_score":       0,
                "missing_information": "",
                "quality_feedback":    "",
                "retry_count":         0,
                "final_report":        "",
                "audit_result":        "",
                "execution_logs":      [],
            }
            config = {"configurable": {
                "thread_id": f"ui-{user_input.lower().replace(' ', '-')}"
            }}

            st.markdown('<div class="section-title">Pipeline Progress</div>', unsafe_allow_html=True)
            status_box   = st.empty()
            progress_bar = st.progress(0)
            completed: list[str] = []

            try:
                app = build_graph()
                final_state = None

                for snapshot in app.stream(initial_state, config, stream_mode="values"):
                    final_state = snapshot
                    current = snapshot.get("current_agent", "")
                    if current and current not in completed and current != "supervisor":
                        completed.append(current)
                    label = AGENT_LABELS.get(current, current.capitalize())
                    status_box.markdown(
                        f'<div class="agent-card"><b>{label}</b> is working...</div>',
                        unsafe_allow_html=True,
                    )
                    progress_bar.progress(min(len(completed) / len(PIPELINE_ORDER), 1.0))

                progress_bar.progress(1.0)
                status_box.markdown(
                    '<div class="agent-card"><b>Pipeline complete.</b></div>',
                    unsafe_allow_html=True,
                )
                st.session_state.result_type = "research"
                st.session_state.final_state = final_state
                st.session_state.agent_log   = completed

            except Exception as exc:
                st.error(f"Agent error: {exc}")

    elif run_btn:
        st.warning("Please enter a tool name.")

    # ==========================================================
    # DISPLAY: BLOCKED
    # ==========================================================
    if st.session_state.result_type == "blocked" and st.session_state.sec_state:
        sec          = st.session_state.sec_state
        threat_score = sec.get("threat_score", 0.0)
        threat_type  = sec.get("threat_type", "unknown")

        st.markdown(
            '<div class="blocked-banner">[ BLOCKED ] — Security Threat Detected</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div class="section-title">Threat Details</div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-label">Threat Type</div>
                <div class="metric-value" style="font-size:1.1rem">{threat_type}</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            sc = "red" if threat_score > 0.6 else "gold"
            st.markdown(f"""<div class="metric-card">
                <div class="metric-label">Threat Score</div>
                <div class="metric-value {sc}">{threat_score:.0%}</div>
            </div>""", unsafe_allow_html=True)
        with c3:
            alert = "CRITICAL" if threat_score >= 0.8 else "HIGH"
            st.markdown(f"""<div class="metric-card">
                <div class="metric-label">Alert Level</div>
                <div class="metric-value red">{alert}</div>
            </div>""", unsafe_allow_html=True)

        st.info("This input was identified as a security threat and was not processed. Please enter a valid AI tool name (e.g. LangGraph, CrewAI, Ollama).")

    # ==========================================================
    # DISPLAY: RESEARCH RESULTS
    # ==========================================================
    if st.session_state.result_type == "research" and st.session_state.final_state:
        fs = st.session_state.final_state

        # ── Summary metrics ───────────────────────────────────
        st.markdown('<div class="section-title">Research Summary</div>', unsafe_allow_html=True)

        score     = fs.get("quality_score", 0)
        retries   = fs.get("retry_count", 0)
        sources   = len(fs.get("sources") or [])
        agents    = len(st.session_state.agent_log)
        score_cls = "green" if score >= 7 else "gold"

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-label">Quality Score</div>
                <div class="metric-value {score_cls}">{score}<span style="font-size:1rem">/10</span></div>
            </div>""", unsafe_allow_html=True)
        with m2:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-label">Sources Found</div>
                <div class="metric-value">{sources}</div>
            </div>""", unsafe_allow_html=True)
        with m3:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-label">Retry Count</div>
                <div class="metric-value">{retries}</div>
            </div>""", unsafe_allow_html=True)
        with m4:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-label">Agents Used</div>
                <div class="metric-value">{agents}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Agent checklist ───────────────────────────────────
        st.markdown('<div class="section-title">Agent Checklist</div>', unsafe_allow_html=True)
        check_cols = st.columns(4)
        for i, agent in enumerate(PIPELINE_ORDER):
            ran      = agent in st.session_state.agent_log
            cls_item = "checklist-done" if ran else "checklist-pending"
            cls_mark = "done" if ran else "pending"
            symbol   = "+" if ran else "-"
            with check_cols[i % 4]:
                st.markdown(
                    f'<div class="checklist-item {cls_item}">'
                    f'<span class="check-mark {cls_mark}">{symbol}</span>'
                    f'{AGENT_LABELS[agent]}</div>',
                    unsafe_allow_html=True,
                )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Final report ──────────────────────────────────────
        st.markdown('<div class="section-title">Final Report</div>', unsafe_allow_html=True)
        report = fs.get("final_report", "")
        if report:
            st.download_button(
                label="Download Report (.md)",
                data=report,
                file_name=f"{fs.get('tool_name', 'report')}.md",
                mime="text/markdown",
            )
            st.markdown('<div class="report-box">', unsafe_allow_html=True)
            st.markdown(report)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Audit + Execution log ─────────────────────────────
        st.markdown('<div class="section-title">Details</div>', unsafe_allow_html=True)
        col_a, col_b = st.columns(2)
        with col_a:
            with st.expander("Audit Record"):
                st.text(fs.get("audit_result", ""))
        with col_b:
            log_entries = fs.get("execution_logs", [])
            with st.expander(f"Execution Log ({len(log_entries)} entries)"):
                for entry in log_entries:
                    st.text(entry)


# ─────────────────────────────────────────────────────────────
# TAB 2 — Reports Archive
# ─────────────────────────────────────────────────────────────

with tab_archive:

    st.markdown('<div class="section-title">Saved Reports</div>', unsafe_allow_html=True)
    st.caption(
        "All reports generated by the agent are listed here. "
        "Click View to read inline or Download to save the file."
    )

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    report_files = sorted(
        glob.glob(os.path.join(OUTPUT_DIR, "*.md")),
        key=os.path.getmtime,
        reverse=True,
    )

    if not report_files:
        st.info("No reports saved yet. Run a research session from the Research tab.")
    else:
        search = st.text_input(
            "Filter reports",
            placeholder="Type to filter by tool name...",
        )
        if search:
            report_files = [
                f for f in report_files
                if search.lower() in os.path.basename(f).lower()
            ]

        st.markdown(f"**{len(report_files)} report(s) found**")
        st.markdown("---")

        for report_path in report_files:
            basename  = os.path.basename(report_path)
            tool_name = basename.replace(".md", "").replace("_", " ").title()
            mod_time  = datetime.fromtimestamp(os.path.getmtime(report_path))
            file_size = os.path.getsize(report_path)

            with open(report_path, "r", encoding="utf-8") as f:
                content = f.read()

            with st.container():
                col_info, col_view, col_dl = st.columns([5, 1, 1])
                with col_info:
                    st.markdown(
                        f'<div class="archive-title">{tool_name}</div>'
                        f'<div class="archive-meta">'
                        f'Saved: {mod_time.strftime("%Y-%m-%d %H:%M")} &nbsp;|&nbsp; '
                        f'Size: {file_size:,} bytes</div>',
                        unsafe_allow_html=True,
                    )
                with col_view:
                    if st.button("View", key=f"view_{basename}"):
                        st.session_state.viewed_report = content
                        st.session_state.viewed_title  = tool_name
                with col_dl:
                    st.download_button(
                        label="Download",
                        data=content,
                        file_name=basename,
                        mime="text/markdown",
                        key=f"dl_{basename}",
                    )
                st.markdown(
                    "<hr style='margin:0.6rem 0;border-color:#E0DAD0'>",
                    unsafe_allow_html=True,
                )

        if st.session_state.viewed_report:
            st.markdown(
                f'<div class="section-title">Viewing: {st.session_state.viewed_title}</div>',
                unsafe_allow_html=True,
            )
            if st.button("Close"):
                st.session_state.viewed_report = None
                st.session_state.viewed_title  = ""
                st.rerun()
            else:
                st.markdown('<div class="report-box">', unsafe_allow_html=True)
                st.markdown(st.session_state.viewed_report)
                st.markdown('</div>', unsafe_allow_html=True)
