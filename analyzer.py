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
MAX_OUTPUT_TOKENS = 2800

# CMU/ARPAbet -> IPA, so end users see standard phonetic notation instead of ARPAbet codes.
ARPABET_TO_IPA = {
    "AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ", "AW": "aʊ", "AY": "aɪ",
    "B": "b", "CH": "tʃ", "D": "d", "DH": "ð", "EH": "ɛ", "ER": "ɝ",
    "EY": "eɪ", "F": "f", "G": "ɡ", "HH": "h", "IH": "ɪ", "IY": "i",
    "JH": "dʒ", "K": "k", "L": "l", "M": "m", "N": "n", "NG": "ŋ",
    "OW": "oʊ", "OY": "ɔɪ", "P": "p", "R": "ɹ", "S": "s", "SH": "ʃ",
    "T": "t", "TH": "θ", "UH": "ʊ", "UW": "u", "V": "v", "W": "w",
    "Y": "j", "Z": "z", "ZH": "ʒ",
}

STRESS_MARKS = {"1": "ˈ", "2": "ˌ", "0": ""}


def arpabet_to_ipa(phones: str) -> str:
    """Converts a space-separated ARPAbet string (e.g. 'K R EY1 Z IY0') to IPA (e.g. 'ˈkɹeɪzi').

    Groups phonemes into syllables (maximal onset) so stress marks land on the
    syllable boundary, matching standard IPA convention, rather than mid-syllable.
    """
    tokens = phones.split()
    vowel_idxs = [i for i, t in enumerate(tokens) if t[-1].isdigit()]
    if not vowel_idxs:
        return "".join(ARPABET_TO_IPA.get(t, t) for t in tokens)

    syllables = []
    prev_end = 0
    for vi in vowel_idxs:
        syllables.append({"phones": tokens[prev_end:vi], "stress": tokens[vi][-1]})
        syllables[-1]["phones"].append(tokens[vi][:-1])
        prev_end = vi + 1
    syllables[-1]["phones"].extend(tokens[prev_end:])  # trailing coda consonants

    ipa = ""
    for syl in syllables:
        ipa += STRESS_MARKS.get(syl["stress"], "")
        for p in syl["phones"]:
            if p == "AH" and syl["stress"] == "0":
                ipa += "ə"  # unstressed schwa, rather than the stressed ʌ
            else:
                ipa += ARPABET_TO_IPA.get(p, p)
    return ipa

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
            "In 6-8 sentences: how sentence structure (enjambment vs. end-stopping, "
            "coordination vs. subordination, ellipsis, word order) shapes pacing and tension. "
            "Quote one or two short lines as evidence. Be direct, no filler."
        )
    )
    metaphor_map: str = Field(
        description=(
            "In 6-8 sentences: the core motifs and conceptual metaphors, and how concrete "
            "imagery maps onto abstract emotional states. Quote one or two short lines as evidence. "
            "Be direct, no filler."
        )
    )
    rhyme_scheme: str = Field(
        description=(
            "The strict end-rhyme scheme notation for each stanza (e.g., Verse 1: AABB, Chorus: "
            "ABAB) based strictly on the provided Phonetic Data, noting any slant rhymes. Then in "
            "3-4 sentences, explain how this form drives momentum or expectation. Cite sounds using "
            "the given IPA notation (e.g., /eɪ/), never raw ARPAbet codes."
        )
    )
    phonetic_texture: str = Field(
        description=(
            "In 6-8 sentences: the most notable assonance, consonance, alliteration, and "
            "stress/meter patterns, and the effect they create (weight, softness, tension). Cite "
            "sounds using the given IPA notation (e.g., /eɪ/) or the words themselves, never raw "
            "ARPAbet codes. Be direct, no filler."
        )
    )
    pragmatic_analysis: str = Field(
        description=(
            "In 6-8 sentences: who the speaker is addressing, the dominant speech act "
            "(assertion, question, command, confession), and what's implied but not stated "
            "outright (implicature). Note any shift in register or in the speaker/addressee "
            "relationship. Be direct, no filler."
        )
    )
    narrative_arc: str = Field(
        description=(
            "In 6-8 sentences: the starting situation, the turning point, and the "
            "resolution (or lack thereof), tying back to the patterns above in brief. Be direct, "
            "no filler."
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
            
    # Get the phonemes for those words, converted to IPA
    phonetic_context = "Phonetic Data for End Words (IPA):\n"
    for word in end_words:
        phones = pronouncing.phones_for_word(word)
        ipa = f"/{arpabet_to_ipa(phones[0])}/" if phones else "Unknown"
        phonetic_context += f"- {word}: {ipa}\n"
        
    return phonetic_context

@st.cache_data(show_spinner=False, ttl=3600, max_entries=200)
def analyze_lyrics(lyrics: str) -> dict:
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
                    "and pragmatics. Analyze the provided lyrics precisely: each field should be a "
                    "short, information-dense paragraph of the length requested in its field "
                    "description, not a one-liner. Use the provided "
                    "Phonetic Data to accurately identify end-rhyme schemes (e.g., AABB, ABAB), slant "
                    "rhymes, and internal assonance. Ground every claim in a short quoted word or "
                    "line, and reason at the phonetic (sound), semantic (meaning), and pragmatic "
                    "(context/use/implicature) levels. When citing sounds, always use the IPA "
                    "notation given in the Phonetic Data (e.g., /eɪ/) — never output raw ARPAbet "
                    "codes like 'EY1'."
                )
            },
            {
                "role": "user",
                "content": f"LYRICS:\n{lyrics}\n\n{phonetic_data}"
            }
        ]
    )
    return response.model_dump()

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
    print(analysis["syntactic_breakdown"])

    print("\n--- METAPHOR MAP ---")
    print(analysis["metaphor_map"])

    print("\n--- PHONETIC & SONIC TEXTURE ---")
    print(analysis["phonetic_texture"])

    print("\n--- NARRATIVE ARC ---")
    print(analysis["narrative_arc"])

    print("\n--- RHYME SCHEME & FORM ---")
    print(analysis["rhyme_scheme"])

    print("\n--- PRAGMATIC ANALYSIS ---")
    print(analysis["pragmatic_analysis"])