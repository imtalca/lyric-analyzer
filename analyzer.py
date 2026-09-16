import os
import re
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
            "In 3-4 sentences: using the given Rhyme Scheme Data as ground truth (it was computed "
            "deterministically — do not restate, re-derive, or contradict its letter pattern), "
            "explain how this stanza form drives momentum or expectation, and comment on the "
            "quality of any rhymes flagged 'slant' there. Cite sounds using the given IPA notation "
            "(e.g., /eɪ/), never raw ARPAbet codes."
        )
    )
    meter_analysis: str = Field(
        description=(
            "In 3-4 sentences: using the given Stress/Meter Data as ground truth (it was scanned "
            "from dictionary stress — do not restate, re-derive, or contradict its per-line labels), "
            "identify notable substitutions or deviations from the prevailing meter (e.g., a "
            "trochaic inversion, an extra unstressed syllable) and explain the effect (emphasis, "
            "hesitation, acceleration). Cite specific lines."
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


# Monosyllabic function words report a dictionary stress of "1" in isolation
# (e.g. "for", "this", "am"), but in connected speech they're normally weak
# unless a content word. Force them weak so short words don't drown out the
# real alternation; this is the standard fix lightweight scansion tools use.
FUNCTION_WORDS = frozenset({
    "a", "an", "the",
    "and", "but", "or", "nor", "for", "so", "yet", "if", "as", "than", "that",
    "of", "to", "in", "on", "at", "by", "with", "from", "into", "onto", "upon",
    "over", "under", "through", "between", "about", "against", "among", "during",
    "without", "within", "along", "across", "behind", "beyond", "near", "since",
    "until", "unto", "up", "out", "off", "down",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them",
    "my", "your", "his", "its", "our", "their", "this", "that", "these", "those",
    "who", "whom", "which", "what",
    "am", "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "have", "has", "had",
    "will", "would", "shall", "should", "can", "could", "may", "might", "must",
})

FOOT_PATTERNS = {"Iambic": "wS", "Trochaic": "Sw", "Anapestic": "wwS", "Dactylic": "Sww"}
FOOT_COUNT_NAMES = {
    1: "Monometer", 2: "Dimeter", 3: "Trimeter", 4: "Tetrameter",
    5: "Pentameter", 6: "Hexameter", 7: "Heptameter", 8: "Octameter",
}


def estimate_syllables(word: str) -> int:
    """Vowel-cluster fallback syllable count for words missing from CMUdict."""
    word = word.lower()
    count, prev_vowel = 0, False
    for ch in word:
        is_vowel = ch in "aeiouy"
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    if word.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


def line_stress_pattern(clean_line: str) -> str:
    """Builds a w/S stress string for a line ('?' where CMUdict has no entry)."""
    pattern = ""
    for word in clean_line.split():
        wl = word.lower()
        stresses = pronouncing.stresses_for_word(wl)
        if stresses:
            digits = stresses[0]
            if len(digits) == 1 and wl in FUNCTION_WORDS:
                pattern += "w"
            else:
                pattern += "".join("w" if d == "0" else "S" for d in digits)
        else:
            pattern += "?" * estimate_syllables(wl)
    return pattern


def _foot_match_score(pattern: str, foot: str) -> float:
    """Fraction of known (non-'?') syllables that fit `foot` tiled across the line."""
    known = matched = 0
    for i, ch in enumerate(pattern):
        if ch == "?":
            continue
        known += 1
        if ch == foot[i % len(foot)]:
            matched += 1
    return matched / known if known else 0.0


def classify_meter(pattern: str) -> str:
    """Best-fit foot type + foot count for a w/S stress pattern, or 'Irregular'."""
    if not pattern:
        return "N/A"
    best_name, best_score, best_len = None, 0.0, 2
    for name, foot in FOOT_PATTERNS.items():
        score = _foot_match_score(pattern, foot)
        if score > best_score:
            best_name, best_score, best_len = name, score, len(foot)
    if best_score >= 0.75:
        foot_count = max(round(len(pattern) / best_len), 1)
        foot_label = FOOT_COUNT_NAMES.get(foot_count, f"{foot_count}-foot")
        return f"{best_name} {foot_label}"
    return f"Irregular ({len(pattern)} syllables)"


def scan_meter(lyrics: str) -> list[dict]:
    """Scans every non-empty line's stress pattern and meter label from CMUdict."""
    scanned = []
    for line in lyrics.strip().split("\n"):
        clean_line = line.translate(str.maketrans("", "", string.punctuation)).strip()
        if not clean_line:
            continue
        pattern = line_stress_pattern(clean_line)
        scanned.append({"line": clean_line, "pattern": pattern, "label": classify_meter(pattern)})
    return scanned


def format_meter_for_display(scanned: list[dict]) -> str:
    """Clean bullet list of the scan, for direct display in the UI (no LLM involved)."""
    return "\n".join(f'"{s["line"]}" — {s["pattern"]} ({s["label"]})' for s in scanned)


def format_meter_for_llm(scanned: list[dict]) -> str:
    """Same scan, with an explanatory header, as grounding context for the LLM prompt."""
    out = (
        "Stress/Meter Data (scanned from dictionary stress, not inferred — "
        "w = unstressed, S = stressed, ? = syllable count estimated, word not in "
        "dictionary):\n"
    )
    out += "\n".join(f'- "{s["line"]}" -> {s["pattern"]} ({s["label"]})' for s in scanned)
    return out


def _clean_end_word(line: str) -> str | None:
    clean_line = line.translate(str.maketrans("", "", string.punctuation)).strip()
    return clean_line.split()[-1].lower() if clean_line else None


def _rhyme_key(word: str):
    """Returns (stressed_key, base_key) from the word's rhyming part, or None if unknown."""
    phones_list = pronouncing.phones_for_word(word)
    if not phones_list:
        return None
    stressed_key = pronouncing.rhyming_part(phones_list[0])
    base_key = re.sub(r"\d", "", stressed_key)
    return stressed_key, base_key


def _split_stanzas(lyrics: str) -> list[list[str]]:
    raw_stanzas = re.split(r"\n\s*\n", lyrics.strip())
    return [
        [line for line in raw.split("\n") if line.strip()]
        for raw in raw_stanzas
        if raw.strip()
    ]


def _scheme_for_stanza(lines: list[str]) -> tuple[str, list[tuple[str, str]]]:
    """Assigns rhyme letters (A, B, C...) to a stanza's end words.

    Two lines get the same letter when their rhyming part matches ignoring stress
    level; if the stress level also differs (e.g. 'free' vs. 'liberty') it's a
    slant rhyme, flagged in `notes`. Unmatched (CMUdict-missing) words get their
    own letter and are flagged unknown, so they never silently force a false rhyme.
    """
    letters = string.ascii_uppercase
    key_to_letter: dict[str, str] = {}
    key_to_first_stressed: dict[str, str] = {}
    next_idx = 0
    result = []
    notes = []
    for line in lines:
        word = _clean_end_word(line)
        if word is None:
            continue
        info = _rhyme_key(word)
        if info is None:
            letter = letters[next_idx % 26]
            next_idx += 1
            notes.append((word, "unknown"))
        else:
            stressed_key, base_key = info
            if base_key in key_to_letter:
                letter = key_to_letter[base_key]
                if stressed_key != key_to_first_stressed[base_key]:
                    notes.append((word, "slant"))
            else:
                letter = letters[next_idx % 26]
                next_idx += 1
                key_to_letter[base_key] = letter
                key_to_first_stressed[base_key] = stressed_key
        result.append(letter)
    return "".join(result), notes


def compute_rhyme_scheme(lyrics: str) -> list[dict]:
    """Deterministic per-stanza rhyme scheme (e.g. ABAB), letters restart each stanza."""
    out = []
    for i, lines in enumerate(_split_stanzas(lyrics), start=1):
        scheme, notes = _scheme_for_stanza(lines)
        out.append({"index": i, "scheme": scheme, "notes": notes})
    return out


def format_rhyme_scheme(stanzas_info: list[dict]) -> str:
    """Renders computed stanza schemes as e.g. 'Verse 1: ABAB (slant: liberty)'."""
    out_lines = []
    for s in stanzas_info:
        slants = [w for w, t in s["notes"] if t == "slant"]
        unknowns = [w for w, t in s["notes"] if t == "unknown"]
        extras = []
        if slants:
            extras.append("slant: " + ", ".join(slants))
        if unknowns:
            extras.append("unknown: " + ", ".join(unknowns))
        suffix = f"  ({'; '.join(extras)})" if extras else ""
        out_lines.append(f"Verse {s['index']}: {s['scheme']}{suffix}")
    return "\n".join(out_lines)


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
    meter_scan = scan_meter(lyrics)
    meter_data = format_meter_for_llm(meter_scan)
    rhyme_scheme_data = compute_rhyme_scheme(lyrics)
    rhyme_scheme_notation = format_rhyme_scheme(rhyme_scheme_data)

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
                    "description, not a one-liner. The Rhyme Scheme Data and Stress/Meter Data were "
                    "both computed deterministically (not by you) — treat their letter patterns and "
                    "per-line labels as ground truth and never restate, re-derive, or contradict "
                    "them; only interpret their effect. Ground every claim in a short quoted word or "
                    "line, and reason at the phonetic (sound), semantic (meaning), and pragmatic "
                    "(context/use/implicature) levels. When citing sounds, always use the IPA "
                    "notation given in the Phonetic Data (e.g., /eɪ/) — never output raw ARPAbet "
                    "codes like 'EY1'."
                )
            },
            {
                "role": "user",
                "content": (
                    f"LYRICS:\n{lyrics}\n\n{phonetic_data}\n\n"
                    f"Rhyme Scheme Data (computed deterministically from the Phonetic Data above; "
                    f"letters restart each stanza):\n{rhyme_scheme_notation}\n\n{meter_data}"
                )
            }
        ]
    )
    result = response.model_dump()
    result["rhyme_scheme_notation"] = rhyme_scheme_notation
    result["meter_scan"] = format_meter_for_display(meter_scan)
    return result

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
    print(analysis["rhyme_scheme_notation"])
    print(analysis["rhyme_scheme"])

    print("\n--- METER ---")
    print(analysis["meter_scan"])
    print(analysis["meter_analysis"])

    print("\n--- PRAGMATIC ANALYSIS ---")
    print(analysis["pragmatic_analysis"])