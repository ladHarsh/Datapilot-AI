import streamlit as st
import time
import re
from typing import Callable, Dict, List, Optional, Tuple
from utils.icons import get_icon


def _join_schema_words(transcript: str, tokens: Dict[str, Tuple[str, str]]) -> str:
    """
    Join space-separated spoken words that match a schema column name.
    e.g. "title year" -> "title_year" when 'title_year' is a column.
    Works on 2-word and 3-word phrases.
    """
    if not tokens:
        return transcript
    words = transcript.split()
    result = []
    i = 0
    while i < len(words):
        # Try 3-word join first, then 2-word
        joined = False
        for n in (3, 2):
            if i + n <= len(words):
                candidate_space  = " ".join(words[i:i+n])
                candidate_under  = "_".join(words[i:i+n])
                candidate_concat = "".join(words[i:i+n])
                for cand in (candidate_under, candidate_concat):
                    if cand.lower() in tokens:
                        display, _ = tokens[cand.lower()]
                        result.append(display)
                        i += n
                        joined = True
                        break
                if joined:
                    break
        if not joined:
            result.append(words[i])
            i += 1
    return " ".join(result)

def _listen_and_transcribe() -> str:
    """Natively listens to the live microphone and returns transcript."""
    import speech_recognition as sr
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        # Fast adjustment for ambient noise to optimize response time
        recognizer.adjust_for_ambient_noise(source, duration=0.3)
        # 6 seconds timeout is optimal for quick conversational queries
        audio = recognizer.listen(source, timeout=6, phrase_time_limit=10)
    return recognizer.recognize_google(audio)

def _apply_voice_text(text: str, corrections: Optional[List[Dict]] = None) -> None:
    st.session_state["current_query"] = text.strip()
    st.session_state.pop("query_input_widget", None)
    st.session_state["voice_state"] = "idle"
    st.session_state["ac_partial"] = ""
    st.session_state["ac_results"] = []
    if corrections:
        st.session_state["voice_corrections"] = corrections
    st.rerun()

def render_voice_input(
    tokens: Optional[Dict[str, Tuple[str, str]]] = None,
    voice_fuzzy_fn: Optional[Callable] = None,
):
    """
    Premium AI voice input component.

    Parameters
    ----------
    tokens : dict, optional
        Schema token index {lower_name: (display_name, type_label)}
        from query_input._get_display_tokens().
    voice_fuzzy_fn : callable, optional
        Function (text, tokens) -> (corrected_text, corrections_list)
        for auto-correcting spoken words against schema.
    """

    if "voice_state" not in st.session_state:
        st.session_state["voice_state"] = "idle"

    state = st.session_state["voice_state"]

    # ── IDLE ──────────────────────────────────────────── #
    if state == "idle":
        if st.button("Ask with Voice", key="voice_start_btn", use_container_width=True):
            st.session_state["voice_state"] = "listening"
            st.rerun()

    # ── LISTENING ─────────────────────────────────────── #
    elif state == "listening":
        # 1. Render listening card with live pulsing dot
        st.markdown(f"""
        <div class='voice-system-card'>
            <div class='voice-card-top'>
                <span class='voice-status-title voice-listening-label'>
                    <span class='voice-live-dot'></span>
                    Listening
                </span>
            </div>
            <div class='voice-caption'>Speak your query clearly now...</div>
            <div class='voice-wave-container'>
                <div class='voice-wave-bar'></div>
                <div class='voice-wave-bar'></div>
                <div class='voice-wave-bar'></div>
                <div class='voice-wave-bar'></div>
                <div class='voice-wave-bar'></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 2. Render beautifully styled Stop button inside the card top-right corner
        st.markdown("<div class='voice-stop-container'>", unsafe_allow_html=True)
        if st.button("Stop", key="voice_stop_btn"):
            st.session_state["voice_state"] = "idle"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        # 3. Capture audio safely (listening state doesn't block the next state)
        try:
            transcript = _listen_and_transcribe()
            if transcript.strip():
                corrected_text = transcript
                corrections = []

                # Step 1: Join space-separated words that match schema column names
                # e.g. "title year" -> "title_year"
                if tokens:
                    corrected_text = _join_schema_words(corrected_text, tokens)

                # Step 2: Apply schema-aware fuzzy correction
                if voice_fuzzy_fn and tokens:
                    corrected_text, corrections = voice_fuzzy_fn(corrected_text, tokens)

                _apply_voice_text(corrected_text, corrections if corrections else None)
            else:
                st.session_state["voice_state"] = "idle"
                st.warning("No speech detected. Please try again — speak clearly and close to your microphone.")
                st.rerun()
        except Exception as exc:
            st.session_state["voice_state"] = "idle"
            err = str(exc).lower()
            if "unknown" in err or "understand" in err or "recognition" in err:
                st.warning("🎙 Couldn't understand the audio. Try speaking clearly, closer to your microphone, in a quiet environment.")
            elif "microphone" in err or "pyaudio" in err or "input" in err:
                st.error("🎙 No microphone detected. Please connect a microphone and try again.")
            elif "timeout" in err or "waited" in err:
                st.warning("🎙 Listening timed out — no speech was detected in time. Please try again.")
            elif "network" in err or "connection" in err:
                st.warning("🎙 Network issue during speech recognition. Check your internet and try again.")
            else:
                st.error(f"🎙 Voice query failed: {exc}")
            st.rerun()
