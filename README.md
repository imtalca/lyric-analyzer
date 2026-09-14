# AI Lyric Analyzer 🎵

> A computational linguistics engine that bridges deterministic NLP with structured LLM reasoning to extract phonetic structures, rhyme schemes, and deep semantic metaphors from lyrics.

![Streamlit App](https://img.shields.io/badge/Streamlit-App-ff4b4b?style=flat-square&logo=streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python&logoColor=white)
![Instructor](https://img.shields.io/badge/Instructor-Pydantic-orange?style=flat-square)

## Live Demo
Experience the live application here: **[AI Lyric Analyzer Live App](https://lyric-analyzer-ysxpl53yrholdrzkbarzcr.streamlit.app/)**

---

## About the Project
Most automated lyric tools rely on basic sentiment counting or word clouds, missing the structural architecture that makes writing compelling. **AI Lyric Analyzer** treats lyrics with the rigorous, multi-layered attention of a literary critic. 

By combining traditional phonetic parsing with structured Large Language Model outputs, this tool acts as an objective mirror to illuminate subconscious patterns, rhyme schemes, and syntactic tension in original compositions across multiple languages (including English and Russian).

---

## Architecture & Technical Stack

The application relies on a hybrid pipeline architecture:
1. **Deterministic Phonetic Parsing (`pronouncing` + Python):** Before touching an LLM, the backend isolates end-words, strips punctuation, and maps them directly to the CMU Pronouncing Dictionary to extract raw ARPAbet phonemes.
2. **Structured Data Validation (`Pydantic` + `Instructor`):** Enforces strict JSON data serialization, preventing conversational bloat and forcing the model into specific analytical pillars.
3. **Interactive Dashboard (`Streamlit`):** A responsive, multi-column dashboard featuring a custom gradient theme and tabbed navigation.

### Tech Stack:
* **Core Language:** Python
* **NLP & Linguistics:** `pronouncing`, `string` tokenization, phonetic ARPAbet mapping
* **AI & Validation:** OpenAI API (`gpt-4o-mini`), `instructor`, `Pydantic`
* **Frontend Dashboard:** Streamlit
* **Environment & Security:** `python-dotenv`, Git, Streamlit Cloud

---

## Analytical Pillars
The engine evaluates text across six distinct linguistic axes, spanning phonetics, semantics, and pragmatics:
* **Form & Rhyme Scheme:** Strict end-rhyme notations (e.g., AABB, ABAB) backed by phonetic dictionary data, including slant rhymes and their phonetic distance.
* **Sonic & Phonetic Texture:** Assonance, consonance, alliteration, vowel weight, stress/meter, and sound symbolism.
* **Syntactic Breakdown:** Line breaks vs. clause boundaries, coordination/subordination, ellipsis, and how syntax shifts pacing and tension.
* **Metaphor Map (Semantics):** Semantic fields, lexical connotation, and how concrete imagery maps onto abstract emotional states.
* **Pragmatics:** Speech acts, implicature, deixis, and how register and the speaker/addressee relationship shift across the song.
* **Narrative Arc:** Synthesizing the core emotional pivot or realization of the song, tying the other five pillars together.

---

## Local Installation & Setup

If you want to run or test this project locally on your machine:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/imtalca/lyric-analyzer.git
   cd lyric-analyzer
   ```

2. **Create a virtual environment and install dependencies:**
   ```bash
   python -m venv venv
   venv\Scripts\activate   # Windows
   # source venv/bin/activate   # macOS/Linux
   pip install -r requirements.txt
   ```

3. **Configure your OpenAI API key:**
   Create a `.env` file in the project root:
   ```
   OPENAI_API_KEY=your_key_here
   ```
   > **Don't have a key?** If you're testing this project and don't want to set up your own OpenAI API key, contact me at contact@talcamusic.com and I can share one or run an analysis for you.

4. **Run the app:**
   ```bash
   streamlit run app.py
   ```
