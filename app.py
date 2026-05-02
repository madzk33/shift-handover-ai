"""Shift Handover AI — Streamlit application entry point."""

import os
import tempfile
from datetime import date

import streamlit as st
from dotenv import load_dotenv

from handover_engine import generate_handover, transcribe_audio
from schema import Handover, Severity
from slack_mock import format_as_markdown, format_for_slack
from storage import get_handover_by_id, get_recent_handovers, init_db, save_handover

load_dotenv()

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Shift Handover AI",
    page_icon="📋",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Initialise database on first run
# ---------------------------------------------------------------------------
init_db()

# ---------------------------------------------------------------------------
# Check for API keys early
# ---------------------------------------------------------------------------
GROQ_KEY_SET = bool(os.getenv("GROQ_API_KEY"))
OPENAI_KEY_SET = bool(os.getenv("OPENAI_API_KEY"))

# ---------------------------------------------------------------------------
# Sidebar — shift metadata
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("📋 Shift Details")
    shift_date = st.date_input("Shift date", value=date.today())
    shift_type = st.selectbox("Shift type", ["Day", "Evening", "Night"])
    operative = st.text_input("Operative name", placeholder="e.g. Sarah K.")
    line_or_area = st.text_input("Line / Area", placeholder="e.g. Line 3, Packing, QC Lab")

    st.divider()
    st.caption("Shift Handover AI v1.0")
    if not GROQ_KEY_SET:
        st.warning("⚠️ GROQ_API_KEY not set — generation will fail.")
    if not OPENAI_KEY_SET:
        st.info("ℹ️ OPENAI_API_KEY not set — voice upload disabled.")

# ---------------------------------------------------------------------------
# Severity badge helper
# ---------------------------------------------------------------------------
SEVERITY_COLOUR = {
    Severity.high: "🔴",
    Severity.medium: "🟡",
    Severity.low: "🟢",
}


def _severity_badge(severity: Severity) -> str:
    return f"{SEVERITY_COLOUR[severity]} **{severity.value.upper()}**"


# ---------------------------------------------------------------------------
# Display a structured handover in the UI
# ---------------------------------------------------------------------------
def display_handover(handover: Handover) -> None:
    """Render a structured handover using Streamlit components."""
    st.subheader("📄 Structured Handover")
    st.markdown(f"**Summary:** {handover.summary}")

    # Metrics row
    col1, col2, col3 = st.columns(3)
    col1.metric("Issues", len(handover.issues_raised))
    col2.metric("Pending Items", len(handover.pending_items))
    col3.metric("Equipment Reports", len(handover.equipment_status))

    # Issues
    if handover.issues_raised:
        with st.expander(f"🚨 Issues Raised ({len(handover.issues_raised)})", expanded=True):
            for issue in handover.issues_raised:
                st.markdown(
                    f"{_severity_badge(issue.severity)} — {issue.description}\n\n"
                    f"↳ **Action:** {issue.action_needed}"
                )
                st.divider()

    # Pending items
    if handover.pending_items:
        with st.expander(f"📌 Pending Items ({len(handover.pending_items)})", expanded=True):
            for item in handover.pending_items:
                st.markdown(
                    f"• **{item.item}**\n\n"
                    f"  Owner: {item.owner_next_shift} · Deadline: {item.deadline}"
                )
                st.divider()

    # Equipment
    if handover.equipment_status:
        with st.expander(f"🔧 Equipment Status ({len(handover.equipment_status)})", expanded=False):
            for eq in handover.equipment_status:
                status_label = eq.status.value.upper()
                st.markdown(f"**{eq.equipment}** — {status_label}: {eq.notes}")

    # Stock
    if handover.stock_or_ingredient_notes:
        with st.expander("📦 Stock / Ingredient Notes", expanded=False):
            for note in handover.stock_or_ingredient_notes:
                st.markdown(f"- {note}")

    # Safety
    if handover.safety_or_compliance_flags:
        with st.expander("⚠️ Safety / Compliance Flags", expanded=True):
            for flag in handover.safety_or_compliance_flags:
                st.warning(flag)

    # Priorities
    if handover.next_shift_priorities:
        with st.expander("🎯 Next Shift Priorities", expanded=True):
            for i, priority in enumerate(handover.next_shift_priorities, 1):
                st.markdown(f"**{i}.** {priority}")


# ---------------------------------------------------------------------------
# Main area — tabs
# ---------------------------------------------------------------------------
st.title("📋 Shift Handover AI")
st.caption("Turn rough end-of-shift notes into structured handovers — automatically.")

tab_new, tab_history = st.tabs(["✍️ New Handover", "📚 History"])

# ---------------------------------------------------------------------------
# Tab 1: New Handover
# ---------------------------------------------------------------------------
with tab_new:
    input_method = st.radio(
        "How do you want to provide your notes?",
        ["Type notes", "Upload voice memo"],
        horizontal=True,
    )

    raw_text: str | None = None
    source = "typed"

    if input_method == "Type notes":
        raw_text = st.text_area(
            "Paste or type your end-of-shift notes",
            height=200,
            placeholder=(
                "e.g. line 3 ran ok mostly. had issue with the sealer around 11am, "
                "fixed by 11:45 but lost about 200 units. mike from maintenance came down. "
                "flagged for proper service next week..."
            ),
        )
    else:
        if not OPENAI_KEY_SET:
            st.error("🔑 Voice upload requires OPENAI_API_KEY. Add it to your `.env` file.")
        else:
            uploaded_file = st.file_uploader(
                "Upload a voice memo",
                type=["mp3", "wav", "m4a"],
                help="Record a voice memo on your phone and upload it here.",
            )
            if uploaded_file is not None:
                with st.spinner("Transcribing audio…"):
                    # Write to temp file for the OpenAI API
                    suffix = os.path.splitext(uploaded_file.name)[1]
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(uploaded_file.read())
                        tmp_path = tmp.name
                    try:
                        raw_text = transcribe_audio(tmp_path)
                        source = "voice"
                        st.success("✅ Transcription complete")
                        st.text_area("Transcript", value=raw_text, height=150, disabled=True)
                    except Exception as e:
                        st.error(f"Transcription failed: {e}")
                    finally:
                        os.unlink(tmp_path)

    # Generate button
    can_generate = bool(raw_text and raw_text.strip() and operative and line_or_area)

    if not can_generate:
        st.info("Fill in the shift details in the sidebar and provide your notes above to generate a handover.")

    if st.button("🚀 Generate Handover", disabled=not can_generate, type="primary"):
        if not GROQ_KEY_SET:
            st.error("🔑 GROQ_API_KEY is not set. Add it to your `.env` file to use this feature.")
        else:
            metadata = {
                "shift_date": shift_date.isoformat(),
                "shift_type": shift_type,
                "operative": operative,
                "line_or_area": line_or_area,
            }

            with st.spinner("Structuring your handover with AI…"):
                try:
                    handover = generate_handover(raw_text, metadata)
                except (ValueError, RuntimeError) as e:
                    st.error(f"Generation failed: {e}")
                    st.stop()

            # Save to DB
            try:
                handover_id = save_handover(handover, raw_text, source)
                st.success(f"✅ Handover #{handover_id} saved successfully.")
            except Exception as e:
                st.warning(f"Handover generated but failed to save: {e}")

            # Display structured output
            display_handover(handover)

            # Download report buttons
            st.divider()
            st.subheader("⬇️ Download Report")
            md_text = format_as_markdown(handover)
            json_text = handover.model_dump_json(indent=2)

            dl_col1, dl_col2 = st.columns(2)
            with dl_col1:
                st.download_button(
                    label="📝 Download Markdown Report",
                    data=md_text,
                    file_name=f"handover_{handover.shift_date}_{handover.shift_type.lower()}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            with dl_col2:
                st.download_button(
                    label="📦 Download JSON",
                    data=json_text,
                    file_name=f"handover_{handover.shift_date}_{handover.shift_type.lower()}.json",
                    mime="application/json",
                    use_container_width=True,
                )

            # Output format tabs
            st.divider()
            fmt_slack, fmt_md = st.tabs(["💬 Slack Format", "📝 Markdown Preview"])

            with fmt_slack:
                slack_text = format_for_slack(handover)
                st.code(slack_text, language=None)

            with fmt_md:
                st.markdown(md_text)

# ---------------------------------------------------------------------------
# Tab 2: History
# ---------------------------------------------------------------------------
with tab_history:
    recent = get_recent_handovers(limit=20)

    if not recent:
        st.info("No handovers recorded yet. Generate one in the New Handover tab!")
    else:
        st.subheader(f"Recent Handovers ({len(recent)})")

        for record in recent:
            structured = record["structured"]
            header = (
                f"**{structured.get('shift_date', '?')}** · "
                f"{structured.get('shift_type', '?')} Shift · "
                f"{structured.get('operative', '?')} · "
                f"{structured.get('line_or_area', '?')}"
            )

            with st.expander(header, expanded=False):
                # Re-hydrate as Handover for display
                try:
                    h = Handover(**structured)
                    display_handover(h)

                    # Download report buttons
                    st.divider()
                    md = format_as_markdown(h)
                    json_data = h.model_dump_json(indent=2)

                    dl_c1, dl_c2 = st.columns(2)
                    with dl_c1:
                        st.download_button(
                            label="📝 Download Markdown Report",
                            data=md,
                            file_name=f"handover_{h.shift_date}_{h.shift_type.lower()}.md",
                            mime="text/markdown",
                            key=f"dl_md_{record['id']}",
                            use_container_width=True,
                        )
                    with dl_c2:
                        st.download_button(
                            label="📦 Download JSON",
                            data=json_data,
                            file_name=f"handover_{h.shift_date}_{h.shift_type.lower()}.json",
                            mime="application/json",
                            key=f"dl_json_{record['id']}",
                            use_container_width=True,
                        )

                    st.divider()
                    fmt_s, fmt_m = st.tabs(
                        [f"💬 Slack #{record['id']}", f"📝 Markdown #{record['id']}"]
                    )
                    with fmt_s:
                        st.code(format_for_slack(h), language=None)
                    with fmt_m:
                        st.markdown(md)
                except Exception as e:
                    st.error(f"Failed to render handover #{record['id']}: {e}")
                    st.json(structured)
