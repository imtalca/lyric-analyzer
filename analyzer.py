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


def extract_words(line: str) -> list[str]:
    """Lowercased word tokens from a line.

    `string.punctuation` is ASCII-only, so lyrics using an em dash (—), en dash
    (–), curly quotes, or an ellipsis (…) — all common in pasted lyrics — left
    that character stuck to the adjacent word (e.g. "blood—"), which then failed
    every dictionary lookup and got misreported as an unknown rhyme/stress.
    Matching letter runs directly sidesteps the punctuation table entirely.
    """
    words = re.findall(r"[A-Za-z']+", line)
    return [w.strip("'").lower() for w in words if w.strip("'")]


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


def line_tokens(words: list[str]) -> list[tuple[str, bool]]:
    """Per-syllable (stress_char, flexible) tokens for a line.

    Real scansion doesn't just concatenate each word's citation-form stress and
    check the result against a template — performance is allowed to flex certain
    syllables to fit the meter. Metrical theory (the Halle-Keyser "stress maximum"
    idea, simplified) only treats a polysyllabic word's *primary*-stressed syllable
    and its own unstressed syllables as fixed; a secondary-stressed syllable or any
    monosyllable can go either way. E.g. "Come Liberty, thou cheerful sound" reads
    as perfect iambic tetrameter once "-ty" and "thou" are allowed to sit on a beat
    even though they aren't a word's primary stress in isolation.
    """
    tokens = []
    for wl in words:
        stresses = pronouncing.stresses_for_word(wl)
        if not stresses:
            tokens.extend([("?", True)] * estimate_syllables(wl))
            continue
        digits = stresses[0]
        if len(digits) == 1:
            default = "w" if wl in FUNCTION_WORDS else "S"
            tokens.append((default, True))
        else:
            for d in digits:
                if d == "1":
                    tokens.append(("S", False))
                elif d == "0":
                    tokens.append(("w", False))
                else:  # secondary stress: leans strong, but negotiable
                    tokens.append(("S", True))
    return tokens


def scan_line_meter(tokens: list[tuple[str, bool]]) -> tuple[str, str]:
    """Best-fit (resolved_pattern, label) for a line's tokens.

    A fixed (non-flexible) syllable that still clashes with the template counts as
    a substitution (e.g. a trochaic inversion); too many make the line irregular.
    Ties between foot types are broken by how well the literal citation-form
    reading fits, so an all-monosyllable line still gets a sensible label instead
    of an arbitrary one.

    The returned pattern snaps every *flexible* syllable to whatever the winning
    template calls for at that position — e.g. "thou" and the "-ty" of "Liberty"
    display as the beat they're actually read on, not their isolated-word default
    — while genuine substitutions (a fixed syllable that still clashes) stay
    visible as-is, since those are real deviations worth showing.
    """
    if not tokens:
        return "", "N/A"
    n = len(tokens)
    best = None
    for name, foot in FOOT_PATTERNS.items():
        violations = naive_matches = known = 0
        for i, (ch, flexible) in enumerate(tokens):
            if ch == "?":
                continue
            known += 1
            if ch == foot[i % len(foot)]:
                naive_matches += 1
            elif not flexible:
                violations += 1
        naive_score = naive_matches / known if known else 0.0
        key = (-violations, naive_score)
        if best is None or key > best[0]:
            best = (key, name, foot, violations)
    _, name, foot, violations = best
    foot_len = len(foot)

    resolved = "".join(
        "?" if ch == "?" else (foot[i % foot_len] if flexible else ch)
        for i, (ch, flexible) in enumerate(tokens)
    )

    tolerance = max(1, n // 8)
    if violations <= tolerance:
        foot_count = max(round(n / foot_len), 1)
        foot_label = FOOT_COUNT_NAMES.get(foot_count, f"{foot_count}-foot")
        sub_note = f", {violations} substitution{'s' if violations != 1 else ''}" if violations else ""
        label = f"{name} {foot_label}{sub_note}"
    else:
        label = f"Irregular ({n} syllables, {violations} stress clashes)"
    return resolved, label


def scan_meter(lyrics: str) -> list[dict]:
    """Scans every non-empty line's stress pattern and meter label from CMUdict."""
    scanned = []
    for stanza_idx, lines in enumerate(_split_stanzas(lyrics), start=1):
        for line in lines:
            words = extract_words(line)
            if not words:
                continue
            tokens = line_tokens(words)
            pattern, label = scan_line_meter(tokens)
            scanned.append({
                "stanza": stanza_idx, "line": line.strip(),
                "pattern": pattern, "label": label,
            })
    return scanned


def format_meter_for_display(scanned: list[dict]) -> str:
    """One line per stanza (e.g. 'Verse  1: Iambic (8-6-8-6 syllables)'), matching
    the rhyme scheme's per-stanza summary instead of dumping every line's raw scan.
    Verse numbers are right-padded to a common width, same reasoning as
    `format_rhyme_scheme`, so a 2-digit stanza count doesn't shift the columns."""
    stanzas: dict[int, list[dict]] = {}
    for s in scanned:
        stanzas.setdefault(s["stanza"], []).append(s)

    width = len(str(max(stanzas))) if stanzas else 1
    out_lines = []
    for idx in sorted(stanzas):
        entries = stanzas[idx]
        syll_counts = "-".join(str(len(e["pattern"])) for e in entries)
        foot_types = {e["label"].split()[0] for e in entries if not e["label"].startswith("Irregular")}
        label = foot_types.pop() if len(foot_types) == 1 else "Mixed meter"
        out_lines.append(f"Verse {idx:>{width}}: {label} ({syll_counts} syllables)")
    return "\n".join(out_lines)


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
    words = extract_words(line)
    return words[-1] if words else None


# Unstressed derivational prefixes: removing one doesn't change a word's own
# stress/rhyme (e.g. "respire" rhymes on "-SPIRE" exactly like "spire" does),
# so an OOV word can often be resolved via its un-prefixed root instead of a
# blind spelling guess.
_STRIPPABLE_PREFIXES = (
    "re", "un", "dis", "non", "pre", "mis", "over", "under", "out",
    "de", "sub", "inter", "co",
)


def _rhyme_key(word: str) -> tuple[str, str, str]:
    """Returns (stressed_key, base_key, source) from the word's rhyming part.

    source is "dict" for a direct CMUdict hit, "prefix" when resolved via an
    un-prefixed root (e.g. "respire" -> "spire"), or "guess" for a last-resort
    spelling-based fallback (the word's last 3 letters) when neither works —
    only useful for grouping with *other* unrecognized words that happen to
    share that ending, since a real dictionary word's key is phonetic, not
    spelling-based, and won't collide with a spelling guess.
    """
    phones_list = pronouncing.phones_for_word(word)
    if phones_list:
        stressed_key = pronouncing.rhyming_part(phones_list[0])
        return stressed_key, re.sub(r"\d", "", stressed_key), "dict"

    for prefix in _STRIPPABLE_PREFIXES:
        if word.startswith(prefix) and len(word) - len(prefix) >= 3:
            root_phones = pronouncing.phones_for_word(word[len(prefix):])
            if root_phones:
                stressed_key = pronouncing.rhyming_part(root_phones[0])
                return stressed_key, re.sub(r"\d", "", stressed_key), "prefix"

    fallback = word[-3:] if len(word) >= 3 else word
    return fallback, fallback, "guess"


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
    slant rhyme, flagged in `notes`. Words missing from CMUdict are resolved via
    `_rhyme_key`'s prefix-stripping or spelling-guess fallbacks; a spelling guess
    is always flagged 'estimated' (a prefix-derived key isn't, since it's still a
    real dictionary pronunciation, just of the un-prefixed root).
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
        stressed_key, base_key, source = _rhyme_key(word)
        if base_key in key_to_letter:
            letter = key_to_letter[base_key]
            if source != "guess" and stressed_key != key_to_first_stressed[base_key]:
                notes.append((word, "slant"))
        else:
            letter = letters[next_idx % 26]
            next_idx += 1
            key_to_letter[base_key] = letter
            key_to_first_stressed[base_key] = stressed_key
        if source == "guess":
            notes.append((word, "estimated"))
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
    """Renders computed stanza schemes as e.g. 'Verse  1: ABAB (slant: liberty)'.

    Verse numbers are right-padded to a common width so the letter/note columns
    stay aligned once a poem reaches a 2-digit stanza count (otherwise "Verse 9:"
    and "Verse 10:" shift the text after them by one column).
    """
    width = len(str(len(stanzas_info))) if stanzas_info else 1
    out_lines = []
    for s in stanzas_info:
        slants = [w for w, t in s["notes"] if t == "slant"]
        estimated = [w for w, t in s["notes"] if t == "estimated"]
        extras = []
        if slants:
            extras.append("slant: " + ", ".join(slants))
        if estimated:
            extras.append("estimated: " + ", ".join(estimated))
        suffix = f"  ({'; '.join(extras)})" if extras else ""
        out_lines.append(f"Verse {s['index']:>{width}}: {s['scheme']}{suffix}")
    return "\n".join(out_lines)


def extract_phonetic_data(lyrics: str) -> str:
    """Extracts end-words and their phonetic translation for the LLM."""
    lines = lyrics.strip().split('\n')
    end_words = []
    
    # Isolate the last word of every line
    for line in lines:
        words = extract_words(line)
        if words:
            end_words.append(words[-1])
            
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