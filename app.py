import os
import time

import streamlit as st

from analyzer import analyze_lyrics, MAX_LYRICS_CHARS

# 1. Page Config (Set to 'wide' for a modern dashboard look)
st.set_page_config(page_title="AI Lyric Analyzer", page_icon="🎵", layout="wide")

# Per-session abuse guardrails (public app -> anyone can spend your OpenAI credits).
RATE_LIMIT_MAX = 8          # analyses allowed per rolling window
RATE_LIMIT_WINDOW = 600     # window length in seconds (10 min)


def check_password() -> bool:
    """Gate the app behind a shared passphrase stored in Streamlit secrets.

    If APP_PASSWORD is not configured the app stays open, but we surface a
    warning so it isn't left unprotected by accident.
    """
    expected = None
    try:
        expected = st.secrets.get("APP_PASSWORD")
    except Exception:
        expected = None
    if not expected:
        expected = os.getenv("APP_PASSWORD")  # local .env fallback

    if not expected:
        st.sidebar.warning("App is not password protected. Set APP_PASSWORD in secrets.")
        return True

    if st.session_state.get("authed"):
        return True

    with st.form("auth"):
        pw = st.text_input("Password", type="password")
        if st.form_submit_button("Enter") and pw:
            if pw == expected:
                st.session_state["authed"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    return False


def rate_limited() -> bool:
    """True if this session has exceeded the rolling request budget."""
    now = time.time()
    calls = [t for t in st.session_state.get("calls", []) if now - t < RATE_LIMIT_WINDOW]
    st.session_state["calls"] = calls
    return len(calls) >= RATE_LIMIT_MAX


def record_call() -> None:
    st.session_state.setdefault("calls", []).append(time.time())


if not check_password():
    st.stop()

# 2. Inject Custom CSS to hide default Streamlit branding and polish the UI
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            /* Gradient backdrop for the whole app */
            .stApp {
                background: linear-gradient(135deg, #1f1147 0%, #4a2a8c 35%, #a1327a 70%, #e2683a 100%);
                background-attachment: fixed;
            }
            /* Panels get a translucent dark card so text stays readable over the gradient */
            [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"],
            .stTextArea textarea, .stTabs {
                background-color: rgba(15, 10, 35, 0.35);
                border-radius: 12px;
            }
            .stTabs [data-baseweb="tab-list"] {
                background-color: rgba(15, 10, 35, 0.35);
                border-radius: 8px;
                padding: 4px;
            }
            h1, h2, h3, p, label, .stMarkdown {
                color: #f5f0ff;
            }
            /* Make the button look sleeker */
            .stButton>button {
                border-radius: 8px;
                font-weight: bold;
            }
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# 3. App Header
st.title("AI Lyric Analyzer")
st.markdown("A linguistic engine that extracts phonetic structures, rhyme schemes, and deep semantic metaphors from your lyrics.")
st.divider()

# 4. Create a Two-Column Layout
col1, col2 = st.columns([1, 1.5]) # The right column will be slightly wider

with col1:
    st.subheader("1. Input Data")
    lyrics_input = st.text_area(
        "Paste your lyrics here:",
        height=350,
        max_chars=MAX_LYRICS_CHARS,
        placeholder="User's lyrics...",
    )

    # Make the button span the full width of the column
    analyze_button = st.button("Run Deep Analysis", use_container_width=True)

with col2:
    st.subheader("2. Linguistic Engine Output")

    if analyze_button:
        if not lyrics_input.strip():
            st.warning("Please paste some lyrics first!")
        elif rate_limited():
            st.error(
                f"Rate limit reached ({RATE_LIMIT_MAX} analyses per "
                f"{RATE_LIMIT_WINDOW // 60} minutes). Please wait and try again."
            )
        else:
            try:
                with st.spinner("Extracting phonemes and analyzing syntax..."):
                    analysis = analyze_lyrics(lyrics_input)
                record_call()
            except ValueError as e:
                st.warning(str(e))
                st.stop()
            except Exception:
                st.error("Analysis failed. Please try again in a moment.")
                st.stop()

            # 5. Use Interactive Tabs, one per level of linguistic analysis
            tab_form, tab_phon, tab_syntax, tab_sem, tab_prag, tab_synth = st.tabs([
                "Form",
                "Phonetics",
                "Syntax",
                "Semantics",
                "Pragmatics",
                "Synthesis"
            ])

            with tab_form:
                st.write(analysis["rhyme_scheme"])
            with tab_phon:
                st.write(analysis["phonetic_texture"])
            with tab_syntax:
                st.write(analysis["syntactic_breakdown"])
            with tab_sem:
                st.write(analysis["metaphor_map"])
            with tab_prag:
                st.write(analysis["pragmatic_analysis"])
            with tab_synth:
                st.write(analysis["narrative_arc"])
    else:
        # Default state before the user clicks the button
        st.info("Awaiting input... Paste your lyrics on the left and initialize the engine.")
