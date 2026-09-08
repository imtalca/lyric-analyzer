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
MAX_OUTPUT_TOKENS = 2000

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
        description="Analysis of line breaks, pacing, subordination, and how syntax shifts create tension."
    )
    metaphor_map: str = Field(
        description="Tracking core motifs and identifying how physical imagery transforms into emotional states."
    )
    rhyme_scheme: str = Field(
        description="The strict end-rhyme scheme notation for each stanza (e.g., Verse 1: AABB, Chorus: ABAB) based strictly on the provided Phonetic Data. Explain briefly how this specific form drives the momentum."
    )
    phonetic_texture: str = Field(
        description="Highlights of assonance, alliteration, and how vowel sounds affect the heaviness of lines."
    )
    narrative_arc: str = Field(
        description="A concise synthesis of the emotional pivot or conceptual realization in the song."
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
                "content": "You are an expert computational linguist. Analyze the provided lyrics deeply. Use the provided Phonetic Data to accurately identify end-rhyme schemes (e.g., AABB, ABAB), slant rhymes, and internal assonance."
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