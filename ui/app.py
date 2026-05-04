from __future__ import annotations
import sys
import os
import queue
import threading
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from dotenv import load_dotenv, set_key

load_dotenv()

from core.config import RunConfig, PLATFORM_LIMITS
from core import pipeline

_ASSETS = os.path.join(os.path.dirname(__file__), "assets")
_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")

st.set_page_config(
    page_title="Ripple",
    page_icon=os.path.join(_ASSETS, "ripple.png"),
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styles ───────────────────────────────────────────────────────────────────
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


# ── Agent display names for streaming ────────────────────────────────────────
_AGENT_DISPLAY = {
    "Trend Intelligence Analyst":     ("🔍", "Trends collected"),
    "Audience Behaviour Specialist":  ("🧠", "Emotional drivers mapped"),
    "Platform Content Strategist":    ("📋", "Content angles planned"),
    "Viral Copywriter":               ("✍️",  "Posts written"),
    "Creative Director":              ("🎨", "Content refined"),
    "Content Performance Analyst":    ("📊", "Scoring complete"),
}
_AGENT_ORDER = list(_AGENT_DISPLAY.keys())


# ── Reddit connection helper ──────────────────────────────────────────────────
def _test_reddit(client_id: str, client_secret: str) -> tuple[bool, str]:
    try:
        import praw
        r = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent="Ripple/1.0",
        )
        list(r.subreddit("productivity").hot(limit=1))
        return True, "Connected"
    except Exception as e:
        return False, str(e)[:120]


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image(os.path.join(_ASSETS, "ripple.png"), use_container_width=True)
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

    # ── Reddit setup ─────────────────────────────────────────────────────────
    st.divider()
    reddit_connected = bool(os.getenv("REDDIT_CLIENT_ID") and os.getenv("REDDIT_CLIENT_SECRET"))
    reddit_label = "Reddit  ✓ connected" if reddit_connected else "Reddit  ✗ not connected"

    with st.expander(reddit_label):
        st.caption(
            "Reddit gives richer, more real-time trend data. "
            "Create a free app at reddit.com/prefs/apps (choose 'script' type)."
        )
        r_id = st.text_input("Client ID", value=os.getenv("REDDIT_CLIENT_ID", ""), type="password")
        r_secret = st.text_input("Client Secret", value=os.getenv("REDDIT_CLIENT_SECRET", ""), type="password")

        if st.button("Save and test", use_container_width=True):
            if r_id and r_secret:
                with st.spinner("Testing connection..."):
                    ok, msg = _test_reddit(r_id, r_secret)
                if ok:
                    set_key(_ENV_PATH, "REDDIT_CLIENT_ID", r_id)
                    set_key(_ENV_PATH, "REDDIT_CLIENT_SECRET", r_secret)
                    os.environ["REDDIT_CLIENT_ID"] = r_id
                    os.environ["REDDIT_CLIENT_SECRET"] = r_secret
                    st.success("Reddit connected. Trend data will now include Reddit posts.")
                    st.rerun()
                else:
                    st.error(f"Connection failed: {msg}")
            else:
                st.warning("Enter both Client ID and Client Secret.")

    # ── Performance data ingest ───────────────────────────────────────────────
    st.divider()
    st.markdown("### Upload Performance Data")
    st.caption("Upload engagement metrics to improve future scoring.")
    csv_file = st.file_uploader("CSV file", type=["csv"])
    if csv_file and st.button("Ingest", use_container_width=True):
        with st.spinner("Saving to memory..."):
            from memory.ingest import ingest_csv
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                tmp.write(csv_file.read())
                tmp_path = tmp.name
            stats = ingest_csv(tmp_path)
            os.unlink(tmp_path)
        st.success(f"Saved {stats['updated']} records. Skipped {stats['skipped']}.")

    # ── Past runs ─────────────────────────────────────────────────────────────
    st.divider()
    st.markdown("### Past Runs")
    past_runs = pipeline.list_runs()
    if past_runs:
        for r in past_runs[:8]:
            label = f"{r['niche'][:28]} ({r['run_id']})"
            if st.button(label, key=f"load_{r['run_id']}", use_container_width=True):
                st.session_state["loaded_run_id"] = r["run_id"]
    else:
        st.caption("No runs yet.")


# ── Main area ─────────────────────────────────────────────────────────────────
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


def render_piece(piece, idx) -> None:
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

        st.text_area(
            label=f"piece_{idx}",
            value=piece.full_text(),
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
        if "all gemini models" in result.error.lower() or "daily quota" in result.error.lower():
            st.error("All free-tier Gemini models have hit today's quota limit.")
            st.info(
                "Free tier resets at midnight Pacific time. You can also enable billing on your "
                "Google AI Studio project to remove daily limits — costs are very low (~$0.03/run)."
            )
        else:
            st.error(f"Run failed: {result.error}")
        return

    st.success(f"Run complete in {result.duration_seconds}s — {len(result.pieces)} pieces generated")

    if result.trends_found:
        with st.expander(f"Trends researched ({len(result.trends_found)})"):
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
            for i, p in enumerate(p for p in result.pieces if p.platform == platform):
                render_piece(p, f"{platform}_{i}")

    with st.expander("Export as CSV"):
        rows = [{
            "run_id": result.run_id, "niche": result.niche,
            "platform": p.platform, "angle": p.angle,
            "hook": p.hook, "body": p.body,
            "hashtags": " ".join(p.hashtags),
            "char_count": p.char_count, "score": p.score,
            "recommended": p.recommended, "text": p.full_text(),
        } for p in result.pieces]
        st.download_button(
            "Download CSV",
            data=pd.DataFrame(rows).to_csv(index=False),
            file_name=f"ripple_{result.run_id}.csv",
            mime="text/csv",
        )


def run_with_streaming(config: RunConfig):
    """Run the pipeline in a background thread and stream agent status to the UI."""
    status_q: queue.Queue = queue.Queue()

    def bg():
        def on_update(agent_role: str, _preview: str):
            status_q.put(("update", agent_role))

        result = pipeline.run(config, status_callback=on_update)
        status_q.put(("done", result))

    threading.Thread(target=bg, daemon=True).start()

    completed: list[str] = []

    with st.status("Ripple is working...", expanded=True) as status:
        progress = st.empty()

        while True:
            try:
                kind, payload = status_q.get(timeout=180)
            except queue.Empty:
                status.update(label="Timed out waiting for agents.", state="error")
                return None

            if kind == "done":
                result = payload
                if result.error:
                    status.update(label="Run failed.", state="error")
                else:
                    status.update(
                        label=f"Done in {result.duration_seconds}s — {len(result.pieces)} pieces ready",
                        state="complete",
                        expanded=False,
                    )
                return result

            # kind == "update" — an agent just finished
            agent_role = payload
            emoji, label = _AGENT_DISPLAY.get(agent_role, ("⚙️", "Step complete"))
            completed.append(f"{emoji} **{agent_role}** — {label}")

            # rebuild the progress display
            with progress.container():
                for line in completed:
                    st.markdown(line)

                # show next pending agent
                next_idx = len(completed)
                if next_idx < len(_AGENT_ORDER):
                    next_name = _AGENT_ORDER[next_idx]
                    st.markdown(f"⏳ **{next_name}** — running...")

            status.update(label=f"Agent {len(completed)}/6 complete...")


# ── Trigger run ───────────────────────────────────────────────────────────────
if run_btn:
    if not niche.strip():
        st.error("Please enter a niche before running.")
    elif not platforms:
        st.error("Select at least one platform.")
    elif not os.getenv("GEMINI_API_KEY"):
        st.error("GEMINI_API_KEY not set. Add it to your .env file.")
    else:
        config = RunConfig(
            niche=niche.strip(),
            subreddits=[s.strip() for s in subreddits_raw.split(",") if s.strip()],
            platforms=platforms,
            angles=angles,
            variations=variations,
            top_k_memory=top_k,
        )
        result = run_with_streaming(config)
        if result:
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
    st.info("Enter a niche in the sidebar and hit Generate Content to start.")
