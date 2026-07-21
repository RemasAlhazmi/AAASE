# =============================================================
# app.py — Streamlit UI for the Multi-Agent Research System
# =============================================================

import glob
import os
import sys
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Ensure lab3/ is on the path when Streamlit runs from a different cwd
LAB3_DIR = os.path.dirname(os.path.abspath(__file__))
if LAB3_DIR not in sys.path:
    sys.path.insert(0, LAB3_DIR)

OUTPUT_DIR = os.path.join(LAB3_DIR, "output")
AUDIT_DIR  = os.path.join(LAB3_DIR, "audit")

# =============================================================
# Page config  (must be the FIRST Streamlit call)
# =============================================================

st.set_page_config(
    page_title="AI Research Agent",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================
# Academic CSS
# =============================================================

st.markdown("""
<style>
/* ── Google Font ── */
@import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@300;400;700&family=Source+Sans+Pro:wght@300;400;600&display=swap');

/* ── Global ── */
html, body, [class*="css"] {
    font-family: 'Source Sans Pro', sans-serif;
    background-color: #F5F0E8;
    color: #2C2C2C;
}

/* ── Main header ── */
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
    letter-spacing: 0.5px;
}
.academic-header p {
    font-size: 1rem;
    color: #C9A84C;
    margin: 0;
    font-weight: 300;
}

/* ── Section titles ── */
.section-title {
    font-family: 'Merriweather', serif;
    font-size: 1.1rem;
    font-weight: 700;
    color: #1B2A4A;
    border-left: 4px solid #C9A84C;
    padding-left: 0.75rem;
    margin: 1.5rem 0 1rem 0;
}

/* ── Agent status card ── */
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

/* ── Metric cards ── */
.metric-card {
    background: #FFFFFF;
    border: 1px solid #D8D3C8;
    border-radius: 10px;
    padding: 1.2rem 1rem;
    text-align: center;
    box-shadow: 0 2px 6px rgba(0,0,0,0.06);
}
.metric-label {
    font-size: 0.8rem;
    color: #6B6B6B;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 0.3rem;
}
.metric-value {
    font-family: 'Merriweather', serif;
    font-size: 2rem;
    font-weight: 700;
    color: #1B2A4A;
}
.metric-value.gold  { color: #C9A84C; }
.metric-value.green { color: #2E7D32; }

/* ── Agent checklist item ── */
.checklist-item {
    padding: 0.35rem 0;
    font-size: 0.95rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.checklist-done   { color: #2E7D32; }
.checklist-pending { color: #AAAAAA; }
.check-mark {
    display: inline-block;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    text-align: center;
    line-height: 18px;
    font-size: 0.75rem;
    font-weight: 700;
    flex-shrink: 0;
}
.check-mark.done    { background: #2E7D32; color: #fff; }
.check-mark.pending { background: #DDDDDD; color: #999; }

/* ── Report display ── */
.report-box {
    background: #FFFFFF;
    border: 1px solid #D8D3C8;
    border-radius: 10px;
    padding: 2rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    line-height: 1.8;
}

/* ── Archive row ── */
.archive-title {
    font-weight: 600;
    color: #1B2A4A;
    font-size: 1rem;
}
.archive-meta {
    font-size: 0.8rem;
    color: #888;
    margin-top: 0.2rem;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: #1B2A4A;
}
section[data-testid="stSidebar"] * {
    color: #E8E4DC !important;
}
section[data-testid="stSidebar"] .stMarkdown h2 {
    color: #C9A84C !important;
    font-family: 'Merriweather', serif;
    border-bottom: 1px solid #C9A84C44;
    padding-bottom: 0.5rem;
}
section[data-testid="stSidebar"] .stMarkdown hr {
    border-color: #C9A84C44;
}

/* ── Sidebar agent list ── */
.sidebar-agent {
    padding: 0.3rem 0;
    font-size: 0.9rem;
    border-bottom: 1px solid #ffffff11;
}

/* ── Buttons ── */
.stButton > button {
    background: #1B2A4A;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 0.6rem 2rem;
    font-size: 1rem;
    font-weight: 600;
    letter-spacing: 0.5px;
    transition: background 0.2s;
}
.stButton > button:hover {
    background: #C9A84C;
    color: #1B2A4A;
}

/* ── Input ── */
.stTextInput > div > div > input {
    border: 2px solid #D8D3C8;
    border-radius: 6px;
    padding: 0.6rem 1rem;
    font-size: 1rem;
    background: #FFFFFF;
}
.stTextInput > div > div > input:focus {
    border-color: #1B2A4A;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.5rem;
}
.stTabs [data-baseweb="tab"] {
    background: #E8E4DC;
    border-radius: 6px 6px 0 0;
    padding: 0.5rem 1.5rem;
    font-weight: 600;
    color: #1B2A4A;
}
.stTabs [aria-selected="true"] {
    background: #1B2A4A !important;
    color: #C9A84C !important;
}

/* ── Spinner ── */
.stSpinner > div { border-top-color: #C9A84C !important; }

/* ── Hide Streamlit branding ── */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# =============================================================
# Agent label map (no emojis)
# =============================================================

AGENT_LABELS = {
    "supervisor":  "Supervisor",
    "research":    "Research Agent",
    "memory":      "Memory Agent",
    "analysis":    "Analysis Agent",
    "evaluation":  "Evaluation Agent",
    "improve":     "Improve Agent",
    "report":      "Report Agent",
    "audit":       "Audit Agent",
}

PIPELINE_ORDER = [
    "research", "memory", "analysis",
    "evaluation", "improve", "report", "audit",
]


# =============================================================
# Sidebar
# =============================================================

with st.sidebar:
    st.markdown("## AI Research Agent")
    st.markdown("**Lab 3 — Multi-Agent System**")
    st.markdown("---")

    st.markdown("**Pipeline Agents**")
    for key in ["supervisor"] + PIPELINE_ORDER:
        st.markdown(
            f'<div class="sidebar-agent">{AGENT_LABELS[key]}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("""
**Architecture:** LangGraph Supervisor Pattern
**LLM:** Gemini 2.5 Flash via OpenRouter
**Memory:** ChromaDB (persistent)
**Search:** Tavily Web Search
""")
    st.markdown("---")
    st.markdown("""
**Example tools:**
LangGraph · CrewAI · AutoGen
Ollama · LangChain · Pinecone
ChromaDB · n8n · OpenRouter
""")


# =============================================================
# Header
# =============================================================

st.markdown("""
<div class="academic-header">
    <h1>AI Tool Research Agent</h1>
    <p>Multi-Agent Research System &mdash; Lab 3 &nbsp;|&nbsp;
       LangGraph Supervisor Pattern &nbsp;|&nbsp;
       Gemini 2.5 Flash</p>
</div>
""", unsafe_allow_html=True)


# =============================================================
# Session state
# =============================================================

if "final_state"   not in st.session_state: st.session_state.final_state   = None
if "agent_log"     not in st.session_state: st.session_state.agent_log     = []
if "is_running"    not in st.session_state: st.session_state.is_running    = False
if "viewed_report" not in st.session_state: st.session_state.viewed_report = None
if "viewed_title"  not in st.session_state: st.session_state.viewed_title  = ""


# =============================================================
# Tabs
# =============================================================

tab_research, tab_archive = st.tabs(["Research", "Reports Archive"])


# ─────────────────────────────────────────────────────────────
# TAB 1 — Research
# ─────────────────────────────────────────────────────────────

with tab_research:

    # ── Input row ────────────────────────────────────────────
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

    # ── Run agent ────────────────────────────────────────────
    if run_btn and tool_input.strip():
        st.session_state.final_state = None
        st.session_state.agent_log   = []
        st.session_state.is_running  = True

        from graph import build_graph

        initial_state = {
            "tool_name":           tool_input.strip(),
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
            "thread_id": f"ui-{tool_input.strip().lower().replace(' ', '-')}"
        }}

        # ── Live progress ─────────────────────────────────
        st.markdown(
            '<div class="section-title">Pipeline Progress</div>',
            unsafe_allow_html=True,
        )
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

                pct = len(completed) / len(PIPELINE_ORDER)
                progress_bar.progress(min(pct, 1.0))

            progress_bar.progress(1.0)
            status_box.markdown(
                '<div class="agent-card"><b>Pipeline complete.</b></div>',
                unsafe_allow_html=True,
            )

            st.session_state.final_state = final_state
            st.session_state.agent_log   = completed
            st.session_state.is_running  = False

        except Exception as exc:
            st.error(f"Agent error: {exc}")
            st.session_state.is_running = False

    elif run_btn and not tool_input.strip():
        st.warning("Please enter a tool name.")

    # ── Results ──────────────────────────────────────────────
    if st.session_state.final_state:
        fs = st.session_state.final_state

        # Metrics row
        st.markdown('<div class="section-title">Research Summary</div>', unsafe_allow_html=True)

        m1, m2, m3, m4 = st.columns(4)

        score   = fs.get("quality_score", 0)
        retries = fs.get("retry_count", 0)
        sources = len(fs.get("sources") or [])
        agents  = len(st.session_state.agent_log)

        score_cls = "green" if score >= 7 else "gold"

        with m1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Quality Score</div>
                <div class="metric-value {score_cls}">{score}<span style="font-size:1rem">/10</span></div>
            </div>""", unsafe_allow_html=True)

        with m2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Sources Found</div>
                <div class="metric-value">{sources}</div>
            </div>""", unsafe_allow_html=True)

        with m3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Retry Count</div>
                <div class="metric-value">{retries}</div>
            </div>""", unsafe_allow_html=True)

        with m4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Agents Used</div>
                <div class="metric-value">{agents}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Agent checklist ───────────────────────────────
        st.markdown('<div class="section-title">Agent Checklist</div>', unsafe_allow_html=True)

        check_cols = st.columns(4)
        for i, agent in enumerate(PIPELINE_ORDER):
            ran       = agent in st.session_state.agent_log
            cls_item  = "checklist-done" if ran else "checklist-pending"
            cls_mark  = "done" if ran else "pending"
            symbol    = "+" if ran else "-"
            label     = AGENT_LABELS[agent]
            with check_cols[i % 4]:
                st.markdown(
                    f'<div class="checklist-item {cls_item}">'
                    f'<span class="check-mark {cls_mark}">{symbol}</span>'
                    f'{label}</div>',
                    unsafe_allow_html=True,
                )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Final report ──────────────────────────────────
        st.markdown('<div class="section-title">Final Report</div>', unsafe_allow_html=True)

        report = fs.get("final_report", "")
        if report:
            tool_safe = fs.get("tool_name", "report")
            st.download_button(
                label="Download Report (.md)",
                data=report,
                file_name=f"{tool_safe}.md",
                mime="text/markdown",
            )
            st.markdown('<div class="report-box">', unsafe_allow_html=True)
            st.markdown(report)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Audit + Execution log ─────────────────────────
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
            label_visibility="visible",
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
                        f'Size: {file_size:,} bytes'
                        f'</div>',
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
                        help=f"Download {basename}",
                    )

                st.markdown(
                    "<hr style='margin:0.6rem 0;border-color:#E0DAD0'>",
                    unsafe_allow_html=True,
                )

        # ── Inline report viewer ──────────────────────────
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
