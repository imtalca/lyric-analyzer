import streamlit as st
from analyzer import analyze_lyrics

# 1. Page Config (Set to 'wide' for a modern dashboard look)
st.set_page_config(page_title="AI Lyric Analyzer", page_icon="🎵", layout="wide")

# 2. Inject Custom CSS to hide default Streamlit branding and polish the UI
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
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
st.markdown("A computational linguistics engine that extracts phonetic structures, rhyme schemes, and deep semantic metaphors from your lyrics.")
st.divider()

# 4. Create a Two-Column Layout
col1, col2 = st.columns([1, 1.5]) # The right column will be slightly wider

with col1:
    st.subheader("1. Input Data")
    lyrics_input = st.text_area("Paste your lyrics here:", height=350, placeholder="User's lyrics...")
    
    # Make the button span the full width of the column
    analyze_button = st.button("Run Deep Analysis", use_container_width=True)

with col2:
    st.subheader("2. Linguistic Engine Output")
    
    if analyze_button:
        if not lyrics_input.strip():
            st.warning("Please paste some lyrics first!")
        else:
            with st.spinner("Extracting phonemes and analyzing syntax..."):
                analysis = analyze_lyrics(lyrics_input)
                
                # 5. Use Interactive Tabs for a clean, compact UI
                tab_form, tab_sonic, tab_syntax, tab_meta, tab_arc = st.tabs([
                    "Form & Scheme", 
                    "Sonic Texture", 
                    "Syntax", 
                    "Metaphors", 
                    "Narrative"
                ])
                
                with tab_form:
                    st.write(analysis.rhyme_scheme)
                with tab_sonic:
                    st.write(analysis.phonetic_texture)
                with tab_syntax:
                    st.write(analysis.syntactic_breakdown)
                with tab_meta:
                    st.write(analysis.metaphor_map)
                with tab_arc:
                    st.write(analysis.narrative_arc)
    else:
        # Default state before the user clicks the button
        st.info("Awaiting input... Paste your lyrics on the left and initialize the engine.")