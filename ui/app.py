from __future__ import annotations
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from core.config import RunConfig, PLATFORM_LIMITS
from core import pipeline

st.set_page_config(
    page_title="Ripple",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styles ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.score-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-weight: 600;
    font-size: 0.85rem;
}
.score-high { background: #d1fae5; color: #065f46; }
.score-mid  { background: #fef9c3; color: #713f12; }
.score-low  { background: #fee2e2; color: #7f1d1d; }
.platform-tag {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 8px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-right: 4px;
}
.tag-twitter   { background: #dbeafe; color: #1e40af; }
.tag-linkedin  { background: #e0e7ff; color: #3730a3; }
.tag-instagram { background: #fce7f3; color: #9d174d; }
.recommended-badge { color: #f59e0b; font-weight: 700; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://via.placeholder.com/200x60/0ea5e9/ffffff?text=🌊+Ripple", use_container_width=True)
    st.markdown("### New Run")

    niche = st.text_input("Your niche", placeholder="e.g. AI productivity tools for students")
    subreddits_raw = st.text_input("Subreddits (optional)", placeholder="e.g. productivity, SaaS")
    platforms = st.multiselect(
        "Platforms",
        ["twitter", "linkedin", "instagram"],
        default=["twitter", "linkedin"],
    )
    angles = st.slider("Content angles", 1, 8, 3)
    variations = st.slider("Variations per angle", 1, 4, 2)
    top_k = st.slider("Memory lookback (past posts)", 1, 20, 5)

    run_btn = st.button("Generate Content", type="primary", use_container_width=True)

    st.divider()
    st.markdown("### Upload Performance Data")
    st.caption("Upload a CSV with actual engagement metrics to improve future scoring.")
    csv_file = st.file_uploader("CSV file", type=["csv"])
    if csv_file and st.button("Ingest", use_container_width=True):
        with st.spinner("Saving to memory..."):
            import tempfile
            from memory.ingest import ingest_csv
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                tmp.write(csv_file.read())
                tmp_path = tmp.name
            stats = ingest_csv(tmp_path)
            os.unlink(tmp_path)
        st.success(f"Saved {stats['updated']} records. Skipped {stats['skipped']}.")

    st.divider()
    st.markdown("### Past Runs")
    past_runs = pipeline.list_runs()
    if past_runs:
        for r in past_runs[:8]:
            label = f"{r['niche'][:30]} ({r['run_id']})"
            if st.button(label, key=f"load_{r['run_id']}", use_container_width=True):
                st.session_state["loaded_run_id"] = r["run_id"]
    else:
        st.caption("No runs yet.")


# ── Main area ────────────────────────────────────────────────────────────────
st.title("🌊 Ripple")
st.caption("Trend-driven social content, scored and ready to post.")

def score_class(score: float) -> str:
    if score >= 75:
        return "score-high"
    if score >= 50:
        return "score-mid"
    return "score-low"

def platform_tag(platform: str) -> str:
    return f'<span class="platform-tag tag-{platform}">{platform.upper()}</span>'

def render_piece(piece, idx: int) -> None:
    rec = "⭐ RECOMMENDED" if piece.recommended else ""
    score_html = f'<span class="score-badge {score_class(piece.score)}">{piece.score:.0f}/100</span>'

    with st.container():
        col1, col2 = st.columns([8, 2])
        with col1:
            st.markdown(
                f"{platform_tag(piece.platform)} "
                f"**{piece.angle}** "
                f"{'<span class=\"recommended-badge\">' + rec + '</span>' if rec else ''}",
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(score_html, unsafe_allow_html=True)

        full_text = piece.full_text()
        st.text_area(
            label=f"piece_{idx}",
            value=full_text,
            height=160,
            label_visibility="collapsed",
            key=f"ta_{idx}",
        )

        hashtag_str = " ".join(f"#{t}" for t in piece.hashtags)
        char_limit = PLATFORM_LIMITS.get(piece.platform, 280)
        char_color = "red" if piece.char_count > char_limit else "gray"

        st.markdown(
            f"<small style='color:{char_color}'>{piece.char_count}/{char_limit} chars</small>"
            + (f"&nbsp;&nbsp;<small style='color:#6b7280'>{hashtag_str}</small>" if hashtag_str else ""),
            unsafe_allow_html=True,
        )

        if piece.score_breakdown:
            with st.expander("Score breakdown"):
                bd = piece.score_breakdown
                cols = st.columns(len(bd))
                for col, (k, v) in zip(cols, bd.items()):
                    col.metric(k.replace("_", " ").title(), f"{v:.0f}")

        st.divider()


def render_result(result) -> None:
    if result.error:
        st.error(f"Run failed: {result.error}")
        return

    st.success(f"Run complete in {result.duration_seconds}s — {len(result.pieces)} pieces generated")

    if result.trends_found:
        with st.expander(f"Trends found ({len(result.trends_found)})"):
            for t in result.trends_found:
                st.markdown(f"• {t}")

    tabs = ["All"] + list(dict.fromkeys(p.platform for p in result.pieces))
    tab_objs = st.tabs(tabs)

    with tab_objs[0]:
        recommended = [p for p in result.pieces if p.recommended]
        rest = [p for p in result.pieces if not p.recommended]
        if recommended:
            st.markdown("#### Top picks")
            for i, p in enumerate(recommended):
                render_piece(p, i)
        if rest:
            st.markdown("#### All other content")
            for i, p in enumerate(rest, start=len(recommended)):
                render_piece(p, i)

    for tab, platform in zip(tab_objs[1:], tabs[1:]):
        with tab:
            filtered = [p for p in result.pieces if p.platform == platform]
            for i, p in enumerate(filtered):
                render_piece(p, f"{platform}_{i}")

    with st.expander("Export as CSV"):
        rows = []
        for p in result.pieces:
            rows.append({
                "run_id": result.run_id,
                "niche": result.niche,
                "platform": p.platform,
                "angle": p.angle,
                "hook": p.hook,
                "body": p.body,
                "hashtags": " ".join(p.hashtags),
                "char_count": p.char_count,
                "score": p.score,
                "recommended": p.recommended,
                "text": p.full_text(),
            })
        df = pd.DataFrame(rows)
        st.download_button(
            "Download CSV",
            data=df.to_csv(index=False),
            file_name=f"ripple_{result.run_id}.csv",
            mime="text/csv",
        )


# ── Trigger run ──────────────────────────────────────────────────────────────
if run_btn:
    if not niche.strip():
        st.error("Please enter a niche before running.")
    elif not platforms:
        st.error("Select at least one platform.")
    elif not os.getenv("GEMINI_API_KEY"):
        st.error("GEMINI_API_KEY not set. Add it to your .env file.")
    else:
        subreddits = [s.strip() for s in subreddits_raw.split(",") if s.strip()]
        config = RunConfig(
            niche=niche.strip(),
            subreddits=subreddits,
            platforms=platforms,
            angles=angles,
            variations=variations,
            top_k_memory=top_k,
        )
        with st.spinner("Running agents... this takes 60-120 seconds."):
            result = pipeline.run(config)
        st.session_state["last_result"] = result
        render_result(result)

elif "loaded_run_id" in st.session_state:
    run_id = st.session_state.pop("loaded_run_id")
    result = pipeline.load_result(run_id)
    if result:
        render_result(result)
    else:
        st.warning("Could not load that run.")

elif "last_result" in st.session_state:
    render_result(st.session_state["last_result"])

else:
    st.info("Configure your niche in the sidebar and hit Generate Content to start.")
