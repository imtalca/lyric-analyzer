import os
import string

import instructor
import pronouncing
from pydantic import BaseModel, Field
from openai import OpenAI
from dotenv import load_dotenv
import streamlit as st  # We import streamlit safely here just in case

load_dotenv()

# Cost guardrails: cap request/response size so a single call can't blow up the bill.
MAX_LYRICS_CHARS = 6000
MAX_OUTPUT_TOKENS = 3200

api_key = None
try:
    if "OPENAI_API_KEY" in st.secrets:
        api_key = st.secrets["OPENAI_API_KEY"]
except Exception:
    pass

if not api_key:
    api_key = os.getenv("OPENAI_API_KEY")

client = instructor.from_openai(OpenAI(api_key=api_key))

class LyricAnalysis(BaseModel):
    syntactic_breakdown: str = Field(
        description=(
            "A detailed, multi-paragraph analysis of sentence structure: line breaks vs. clause "
            "boundaries (enjambment vs. end-stopping), coordination vs. subordination, ellipsis, "
            "word order inversions, and how each shift in syntax speeds up, slows down, or adds "
            "tension to the delivery. Quote specific lines as evidence."
        )
    )
    metaphor_map: str = Field(
        description=(
            "A detailed semantic analysis: trace the core motifs and conceptual metaphors across "
            "the song, map the semantic fields in play (e.g., nature, decay, distance), explain "
            "lexical connotation and polysemy where relevant, and show precisely how concrete/"
            "physical imagery is mapped onto abstract emotional states. Quote specific lines as "
            "evidence."
        )
    )
    rhyme_scheme: str = Field(
        description=(
            "The strict end-rhyme scheme notation for each stanza (e.g., Verse 1: AABB, Chorus: "
            "ABAB) based strictly on the provided Phonetic Data, including any slant/near rhymes "
            "and their phonetic distance (shared vowel vs. shared coda). Explain in detail how "
            "this specific form drives momentum, mirrors the song's structure, and sets up or "
            "subverts listener expectation."
        )
    )
    phonetic_texture: str = Field(
        description=(
            "A detailed phonetic/phonological analysis: assonance, consonance, and alliteration "
            "patterns; vowel height/backness and how it affects the perceived weight or brightness "
            "of a line; stress and meter (where syllables fall on strong vs. weak beats); and any "
            "sound symbolism (e.g., plosives for abruptness, sibilants for hushed tone). Cite the "
            "actual phonemes or words involved."
        )
    )
    pragmatic_analysis: str = Field(
        description=(
            "A detailed pragmatic analysis: who is the implied speaker addressing (self, a lover, "
            "the listener), what speech acts are being performed (assertion, question, command, "
            "confession), what is implicated but not literally said (conversational implicature, "
            "presupposition), and how register, tone, and deixis (I/you/we, here/now) shift across "
            "the song to reposition the relationship between speaker and addressee."
        )
    )
    narrative_arc: str = Field(
        description=(
            "A thorough synthesis of the song's emotional and conceptual arc: the starting "
            "situation, the turning point, and the resolution or lack thereof, drawing explicit "
            "connections back to the syntactic, semantic, phonetic, and pragmatic patterns above."
        )
    )


def extract_phonetic_data(lyrics: str) -> str:
    """Extracts end-words and their phonetic translation for the LLM."""
    lines = lyrics.strip().split('\n')
    end_words = []
    
    # Isolate the last word of every line
    for line in lines:
        clean_line = line.translate(str.maketrans('', '', string.punctuation)).strip()
        if clean_line:
            last_word = clean_line.split()[-1].lower()
            end_words.append(last_word)
            
    # Get the raw phonemes for those words
    phonetic_context = "Phonetic Data for End Words:\n"
    for word in end_words:
        phones = pronouncing.phones_for_word(word)
        phoneme_str = phones[0] if phones else "Unknown"
        phonetic_context += f"- {word}: {phoneme_str}\n"
        
    return phonetic_context

@st.cache_data(show_spinner=False, ttl=3600, max_entries=200)
def analyze_lyrics(lyrics: str) -> LyricAnalysis:
    lyrics = (lyrics or "").strip()
    if not lyrics:
        raise ValueError("No lyrics provided.")
    if len(lyrics) > MAX_LYRICS_CHARS:
        raise ValueError(
            f"Lyrics are too long ({len(lyrics)} chars). Limit is {MAX_LYRICS_CHARS}."
        )

    print("Extracting phonetic structures...")

    phonetic_data = extract_phonetic_data(lyrics)

    print("Analyzing lyrics... (this takes about 5-10 seconds)\n")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_model=LyricAnalysis,
        max_tokens=MAX_OUTPUT_TOKENS,
        max_retries=2,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert computational linguist specializing in phonetics, semantics, "
                    "and pragmatics. Analyze the provided lyrics deeply and in detail, writing "
                    "multiple full sentences per field rather than short summaries. Use the provided "
                    "Phonetic Data to accurately identify end-rhyme schemes (e.g., AABB, ABAB), slant "
                    "rhymes, and internal assonance. Ground every claim in specific quoted words or "
                    "lines from the lyrics, and explicitly reason at the phonetic (sound), semantic "
                    "(meaning), and pragmatic (context/use/implicature) levels of analysis."
                )
            },
            {
                "role": "user",
                "content": f"LYRICS:\n{lyrics}\n\n{phonetic_data}"
            }
        ]
    )
    return response

if __name__ == "__main__":
    test_lyrics = """

Have you read in between the lines? 
(Li-i-i-i-nes)
Have you managed to see the signs? 
(Si-i-i-i-gns)
How’d you manage to sleep at night? 
With peace of mind?



When you and I synthesize
White rose petals come to life 
Now our stems are intertwined 

When you and I synthesize
White rose petals come to life 
Now our stems are intertwined 



I remember when you arrived 
(A-a-ri-ived)
There was home in the way you lied 
(Li-i-i-i-ed)
Why’d you leave when you knew the night 
The night 
Will not abide 



When you and I synthesize
White rose petals come to life 
Now our stems are intertwined 

When you and I synthesize
White rose petals come to life 
Now our stems are intertwined
    """
    
    analysis = analyze_lyrics(test_lyrics)
    
    print("\n--- SYNTACTIC BREAKDOWN ---")
    print(analysis.syntactic_breakdown)
    
    print("\n--- METAPHOR MAP ---")
    print(analysis.metaphor_map)

    print("\n--- PHONETIC & SONIC TEXTURE ---")
    print(analysis.phonetic_texture)
    
    print("\n--- NARRATIVE ARC ---")
    print(analysis.narrative_arc)

    print("\n--- RHYME SCHEME & FORM ---")
    print(analysis.rhyme_scheme)

    print("\n--- PRAGMATIC ANALYSIS ---")
    print(analysis.pragmatic_analysis)