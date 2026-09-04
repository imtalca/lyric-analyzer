import os
import instructor
from pydantic import BaseModel, Field
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

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

client = instructor.from_openai(OpenAI())

import string
import pronouncing

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
        # pronouncing.phones_for_word() returns a list of phonetic spellings
        phones = pronouncing.phones_for_word(word)
        phoneme_str = phones[0] if phones else "Unknown"
        phonetic_context += f"- {word}: {phoneme_str}\n"
        
    return phonetic_context

def analyze_lyrics(lyrics: str) -> LyricAnalysis:
    print("Extracting phonetic structures...")
    
    # 1. Run your programmatic Python function first
    phonetic_data = extract_phonetic_data(lyrics)
    
    print("Analyzing lyrics... (this takes about 5-10 seconds)\n")
    
    # 2. Inject BOTH the lyrics and the phonetic data into the prompt
    response = client.chat.completions.create(
        model="gpt-4o-mini", 
        response_model=LyricAnalysis,
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