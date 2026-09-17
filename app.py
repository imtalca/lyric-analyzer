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
                background: linear-gradient(180deg, #0a0a0a 0%, #0d1f1c 45%, #14746a 75%, #1fc7b6 100%);
                background-attachment: fixed;
            }
            /* Below ~900px, stack the two columns instead of squeezing them
               side-by-side, which is what forced content to overflow/clip. */
            @media (max-width: 900px) {
                [data-testid="stHorizontalBlock"] {
                    flex-direction: column !important;
                }
                [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
                    width: 100% !important;
                    flex: 1 1 100% !important;
                    min-width: 100% !important;
                }
            }
            /* Panels get a translucent dark card so text stays readable over the gradient */
            [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"],
            .stTextArea textarea, .stTabs {
                background-color: rgba(15, 10, 35, 0.35);
                border-radius: 12px;
            }
            /* The card and tab strip had a rounded background but no inner
               padding, so content (e.g. the "Form" tab label) sat flush
               against the rounded corner instead of having breathing room.
               Targeted directly + !important since a plain descendant rule
               here was losing to Streamlit's own styles. */
            [data-testid="stVerticalBlockBorderWrapper"] {
                padding: 16px !important;
            }
            .stTabs [data-baseweb="tab-list"] {
                background-color: rgba(15, 10, 35, 0.35);
                border-radius: 8px;
                padding: 8px 20px !important;
                margin-left: 4px;
                flex-wrap: wrap;
            }
            /* Long unbroken tokens (e.g. a rhyme-scheme string like AABBCCDD) would
               otherwise overflow the card instead of wrapping to the next line. */
            [data-testid="stMarkdownContainer"], .stTabs [data-baseweb="tab-panel"] {
                overflow-wrap: anywhere;
                word-break: break-word;
            }
            h1, h2, h3, p, label, .stMarkdown {
                color: #f5f0ff;
                overflow-wrap: break-word;
                word-break: break-word;
            }
            /* Make sure the main content area actually shrinks to the window
               width instead of keeping a wide-layout minimum that overflows. */
            .main .block-container, [data-testid="stAppViewContainer"] {
                max-width: 100% !important;
                width: 100% !important;
                box-sizing: border-box;
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
                st.markdown("**Rhyme Scheme**")
                st.code(analysis["rhyme_scheme_notation"], language=None)
                st.write(analysis["rhyme_scheme"])
                st.divider()
                st.markdown("**Meter**")
                st.code(analysis["meter_scan"], language=None)
                st.write(analysis["meter_analysis"])
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
