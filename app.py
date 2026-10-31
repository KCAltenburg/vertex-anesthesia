import os
import re
import io
import json
import wave
import base64
import random
import hashlib
import streamlit as st
import streamlit.components.v1 as components
from google import genai
from google.genai import types
from PIL import Image, ImageDraw

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# ----------------------------------------------------
# 1. PAGE CONFIGURATION
# ----------------------------------------------------
st.set_page_config(page_title="Vertex Anesthesia - Class Study Portal", page_icon="🩺", layout="wide")

# ----------------------------------------------------
# 2. ISOLATED SESSION STATE INITIALIZATION
# ----------------------------------------------------
if "file_catalog" not in st.session_state:
    st.session_state.file_catalog = []
if "indexed_pages" not in st.session_state:
    # Rapid local text index: {filename: {page_num_int: page_text_str}}
    st.session_state.indexed_pages = {}
if "custom_qbank_items" not in st.session_state:
    st.session_state.custom_qbank_items = []
if "raw_pdf_bytes" not in st.session_state:
    st.session_state.raw_pdf_bytes = {}
if "generated_test" not in st.session_state:
    st.session_state.generated_test = []
if "selected_answers" not in st.session_state:
    st.session_state.selected_answers = {}
if "question_hints" not in st.session_state:
    st.session_state.question_hints = {}
if "question_tts_cache" not in st.session_state:
    st.session_state.question_tts_cache = {}
if "submitted" not in st.session_state:
    st.session_state.submitted = False
if "cat_state" not in st.session_state:
    st.session_state.cat_state = {
        "active": False,
        "current_level": 4,
        "target_questions": 10,
        "history_levels": [],
        "completed": False
    }
if "flashcard_deck" not in st.session_state:
    st.session_state.flashcard_deck = []
if "fc_queue" not in st.session_state:
    st.session_state.fc_queue = []
if "fc_flipped" not in st.session_state:
    st.session_state.fc_flipped = False
if "objectives_report" not in st.session_state:
    st.session_state.objectives_report = None
if "textbook_summary_report" not in st.session_state:
    st.session_state.textbook_summary_report = None
if "review_sheet_output" not in st.session_state:
    st.session_state.review_sheet_output = None
if "podcast_data" not in st.session_state:
    st.session_state.podcast_data = None
if "podcast_audio" not in st.session_state:
    st.session_state.podcast_audio = None
if "podcast_topic_index" not in st.session_state:
    # List of {topic, subtopics, start_pct, segment_idx, lecture_name, summary}
    st.session_state.podcast_topic_index = []
if "tutor_threads" not in st.session_state:
    st.session_state.tutor_threads = {}
if "section_chats" not in st.session_state:
    # Persistent general microphone/text chat per course section + global 'Interact With My Notes'
    st.session_state.section_chats = {}
if "photo_solver_result" not in st.session_state:
    st.session_state.photo_solver_result = None
if "user_preferences" not in st.session_state:
    st.session_state.user_preferences = {
        "theme": "🟣 Amethyst Purple (Blackboard / Epic Amethyst)",
        "voice": "Kore",
        "persona": "👑 Fierce Drag Queen Diva & Viral Meme Queen",
        "custom_persona_text": ""
    }
if "personal_metrics" not in st.session_state:
    st.session_state.personal_metrics = {
        "history": [],
        "domain_stats": {},
        "folder_stats": {},
        "source_type_stats": {},
        "asked_questions_ledger": [],
        "verbal_interactions_count": 0,
        "remediation_plan": ""
    }

# ----------------------------------------------------
# 3. EPIC CLINICIAN COLOR THEMES ENGINE
# ----------------------------------------------------
EPIC_THEMES = {
    "🟣 Amethyst Purple (Epic Amethyst)": {
        "bg": "#f1f5f9", "text": "#0f172a", "sidebar_bg": "#1e293b", "sidebar_text": "#f8fafc",
        "primary": "#502d7f", "primary_hover": "#3b1f60", "card_bg": "#ffffff", "card_border": "#e2e8f0",
        "accent_box": "#fafafa", "badge_bg": "#ede9fe", "badge_text": "#5b21b6"
    },
    "💜🖤 Amethyst & Black (Dark Amethyst)": {
        "bg": "#09090b", "text": "#f4f4f5", "sidebar_bg": "#120d1a", "sidebar_text": "#e9d5ff",
        "primary": "#7e22ce", "primary_hover": "#6b21a8", "card_bg": "#18181b", "card_border": "#7e22ce",
        "accent_box": "#181028", "badge_bg": "#3b0764", "badge_text": "#e9d5ff"
    },
    "🖤💖 Black & Hot Pink (Cyber Night Shift)": {
        "bg": "#09090b", "text": "#f4f4f5", "sidebar_bg": "#18181b", "sidebar_text": "#f472b6",
        "primary": "#ec4899", "primary_hover": "#db2777", "card_bg": "#18181b", "card_border": "#ec4899",
        "accent_box": "#1f121d", "badge_bg": "#500724", "badge_text": "#f472b6"
    },
    "🌙 Midnight Slate Dark Mode (Night Shift)": {
        "bg": "#0f172a", "text": "#f8fafc", "sidebar_bg": "#020617", "sidebar_text": "#e2e8f0",
        "primary": "#6366f1", "primary_hover": "#4f46e5", "card_bg": "#1e293b", "card_border": "#334155",
        "accent_box": "#1e293b", "badge_bg": "#312e81", "badge_text": "#c7d2fe"
    },
    "🔵 Epic Ocean Blue (ICU Clinical Light)": {
        "bg": "#f0f9ff", "text": "#0c4a6e", "sidebar_bg": "#082f49", "sidebar_text": "#e0f2fe",
        "primary": "#0284c7", "primary_hover": "#0369a1", "card_bg": "#ffffff", "card_border": "#bae6fd",
        "accent_box": "#e0f2fe", "badge_bg": "#e0f2fe", "badge_text": "#0369a1"
    },
    "🟢 Emerald Scrubs (OR Telemetry Green)": {
        "bg": "#f0fdf4", "text": "#064e3b", "sidebar_bg": "#022c22", "sidebar_text": "#dcfce7",
        "primary": "#059669", "primary_hover": "#047857", "card_bg": "#ffffff", "card_border": "#a7f3d0",
        "accent_box": "#ecfdf5", "badge_bg": "#d1fae5", "badge_text": "#065f46"
    },
    "🌗 Auto System Sync (Matches OS Light/Dark)": {
        "bg": "transparent", "text": "inherit", "sidebar_bg": "#1e293b", "sidebar_text": "#f8fafc",
        "primary": "#502d7f", "primary_hover": "#3b1f60", "card_bg": "rgba(128,128,128,0.08)", "card_border": "rgba(128,128,128,0.25)",
        "accent_box": "rgba(80,45,127,0.08)", "badge_bg": "#ede9fe", "badge_text": "#5b21b6"
    }
}

def apply_epic_theme(theme_name: str):
    t = EPIC_THEMES.get(theme_name, EPIC_THEMES["🟣 Amethyst Purple (Blackboard / Epic Amethyst)"])
    st.markdown(f"""
        <style>
            .stApp {{ background-color: {t['bg']}; color: {t['text']}; }}
            [data-testid="stSidebar"] {{ background-color: {t['sidebar_bg']} !important; color: {t['sidebar_text']} !important; }}
            [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, 
            [data-testid="stSidebar"] h3, [data-testid="stSidebar"] p,
            [data-testid="stSidebar"] label, [data-testid="stSidebar"] span {{ color: {t['sidebar_text']} !important; }}
            .stButton>button {{ 
                width: 100%; border-radius: 0.35rem; font-weight: 600; 
                background-color: {t['primary']} !important; color: #ffffff !important;
                border: none; padding: 0.55rem; transition: all 0.2s ease;
            }}
            .stButton>button:hover {{ background-color: {t['primary_hover']} !important; box-shadow: 0 4px 10px rgba(0,0,0,0.2); }}
            .stRadio {{
                background-color: {t['card_bg']}; color: {t['text']}; padding: 1.25rem;
                border-radius: 0.5rem; border: 1px solid {t['card_border']};
                box-shadow: 0 1px 3px 0 rgba(0,0,0,0.08); margin-bottom: 0.85rem;
            }}
            .hotspot-box {{ 
                background-color: {t['accent_box']}; color: {t['text']};
                border-left: 5px solid {t['primary']}; padding: 1.25rem; 
                border-radius: 0 0.5rem 0.5rem 0; margin-bottom: 1.2rem;
            }}
            .honesty-banner {{
                background: linear-gradient(90deg, {t['primary']}22, {t['card_bg']});
                border-left: 4px solid {t['primary']}; padding: 0.75rem 1rem;
                border-radius: 0.35rem; margin-bottom: 0.75rem; font-size: 0.9rem; font-weight: 600;
            }}
            .picmonic-box {{ 
                background-color: #faf5ff; border: 2px dashed #c084fc; padding: 1.25rem; 
                border-radius: 0.5rem; margin-top: 0.75rem; color: #3b0764; 
            }}
            .meme-box {{
                background: linear-gradient(135deg, #fdf2f8 0%, #fae8ff 100%);
                border-left: 5px solid #ec4899; padding: 1.1rem; border-radius: 0.5rem;
                margin-top: 0.75rem; color: #701a75; font-weight: 500;
            }}
            .flashcard-box {{
                background: linear-gradient(135deg, #1e293b 0%, #09090b 100%);
                color: #f8fafc; padding: 2.2rem; border-radius: 1rem;
                border: 2px solid {t['primary']}; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.25);
                text-align: center; min-height: 220px; display: flex; flex-direction: column;
                justify-content: center; margin-bottom: 1rem;
            }}
            .ion-legend {{
                background-color: #09090b; color: #f8fafc; padding: 0.6rem 1rem;
                border-radius: 0.5rem; font-size: 0.82rem; margin-bottom: 0.75rem;
                display: flex; flex-wrap: wrap; gap: 12px; align-items: center; border: 1px solid {t['primary']};
            }}
            .source-badge {{ 
                background-color: {t['card_bg']}; color: {t['text']}; padding: 0.35rem 0.6rem; 
                border-radius: 0.25rem; font-size: 0.82rem; font-weight: 600;
                border: 1px solid {t['card_border']}; margin-right: 6px;
            }}
            .uworld-badge {{
                background-color: {t['badge_bg']}; color: {t['badge_text']};
                padding: 0.35rem 0.65rem; border-radius: 0.25rem; font-size: 0.82rem;
                font-weight: 700; border: 1px solid {t['primary']}; margin-right: 6px;
            }}
        </style>
    """, unsafe_allow_html=True)

# ----------------------------------------------------
# 4. VIRAL MEME, POP-CULTURE & PERSONA ENGINE
# ----------------------------------------------------
PERSONA_PROMPTS = {
    "👑 Fierce Drag Queen Diva & Viral Meme Queen": (
        "Adopt the persona of a fierce, hilarious, supportive Drag Queen CRNA Diva & Viral Meme Icon! "
        "When the student gets a question right, celebrate with wild, funny anatomical shoutouts (e.g., 'Shout out to my muscle's "
        "Sarcoplasmic Reticulum for releasing Ca2+ to bind Troponin on the thin filaments and YEETING Tropomyosin off Actin's binding sites "
        "so Myosin heads can form cross-bridges and power-stroke toward the M-line in the H-zone, making the H-zone disappear so we can lift heavy in the gym!'). "
        "When they miss a question or need a memory hook, drop iconic viral memes and pop-culture moments (like the viral Kidz Bop Karen mom yelling "
        "'CALM DOWN!' at the OsteoCLAST in the back seat that made too much serum calcium -> 'Calcitonin = The Calcium -Clast Calm Down Hormone / Calci-Calm-It-Down!')."
    ),
    "🚗 Sassy Grok (Tesla Unfiltered Wit & Memes)": (
        "Adopt the persona of Sassy Grok from Tesla mixed with viral internet meme culture: witty, sarcastically endearing, sharp, and brutally honest. "
        "Drop hilarious viral video references, gym-bro physiology shoutouts, and deadpan roasts of wrong distractors while keeping the CRNA science 100% board-accurate."
    ),
    "🤖 J.A.R.V.I.S. (Iron Man AI Butler)": (
        "Adopt the persona of J.A.R.V.I.S. from Iron Man: ultra-refined, composed, dryly witty British AI tactical butler. "
        "Address the student as 'Sir' or 'Doctor', refer to diagrams and animations as 'HUD schematics', and deliver memorable pop-culture and physics analogies."
    ),
    "🩺 Multimodal Sensory & Meme Educator": (
        "Adopt the persona of an energetic, multimodal CRNA board coach who stimulates all senses (visual colors, auditory hooks, kinesthetic gym/action analogies, "
        "and viral pop-culture memes like 'Calci-Calm-It-Down' or 'Yeeting Tropomyosin') so concepts stick permanently."
    ),
    "✍️ Custom Saved Personality": ""
}

NBCRNA_BLUEPRINT_GROUNDING = """
OFFICIAL NBCRNA NCE / SEE EXAM BLUEPRINT & EVIDENCE GROUNDING RULES (ZERO HALLUCINATION POLICY):
1. Only flag a concept with '🚨 CRNA ALERT 🚨' or '🚨 CRNA BOARD HOT TOPIC' if it directly maps to high-yield domains on the official NBCRNA NCE / SEE Content Outline:
   - Basic Sciences (25%), Equipment/Technology (15%), Basic Principles (30%), Advanced Principles (30%).
2. NEVER hallucinate random 'Hot Topics' without blueprint backing.
3. Always provide the exact Source Filename, Page/Slide Number, and a verbatim 4-to-10 word `highlight_quote` from the page so the PDF Highlighter Pop-Up can locate and highlight the exact text!
"""

def get_active_persona_instruction() -> str:
    p_choice = st.session_state.user_preferences.get("persona", "👑 Fierce Drag Queen Diva & Viral Meme Queen")
    if p_choice == "✍️ Custom Saved Personality":
        custom_txt = st.session_state.user_preferences.get("custom_persona_text", "").strip()
        return f"PERSONALITY & MEME INSTRUCTION: {custom_txt}" if custom_txt else PERSONA_PROMPTS["👑 Fierce Drag Queen Diva & Viral Meme Queen"]
    return f"PERSONALITY & MEME INSTRUCTION: {PERSONA_PROMPTS.get(p_choice, '')}"

# ----------------------------------------------------
# 5. RAPID LOCAL SOURCE INDEXER & HIGHLIGHTER POP-UP
# ----------------------------------------------------
def index_pdf_locally(filename: str, pdf_bytes: bytes):
    """Extracts and indexes every page of an uploaded PDF locally for instant search & highlight lookup."""
    if not PYMUPDF_AVAILABLE:
        return
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_map = {}
        for idx, page in enumerate(doc):
            page_map[idx + 1] = page.get_text("text")
        st.session_state.indexed_pages[filename] = page_map
    except Exception:
        pass

def find_best_source_page(source_str: str, quote_str: str = "") -> tuple:
    """Resolves a source citation string into (pdf_filename, page_number, highlight_snippet)."""
    target_file = None
    for fname in st.session_state.raw_pdf_bytes.keys():
        if fname.lower() in source_str.lower():
            target_file = fname
            break
    if not target_file and st.session_state.raw_pdf_bytes:
        target_file = next(iter(st.session_state.raw_pdf_bytes.keys()))

    page_match = re.search(r"(?:Page|Slide|p\.|pg)\s*(\d+)", source_str, re.IGNORECASE)
    page_num = int(page_match.group(1)) if page_match else 1

    # If quote_str is provided and we have an index, verify or locate the exact page containing the quote
    if quote_str and target_file in st.session_state.indexed_pages:
        clean_q = quote_str.strip()[:45].lower()
        for p_idx, p_txt in st.session_state.indexed_pages[target_file].items():
            if clean_q and clean_q in p_txt.lower():
                page_num = p_idx
                break

    return target_file, page_num, quote_str

def render_highlighted_pdf_page(pdf_bytes: bytes, page_num: int, highlight_text: str = "", dpi: int = 180) -> tuple:
    """Renders a PDF page and highlights matching quote text in bright yellow + red border box."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page_idx = max(0, min(page_num - 1, len(doc) - 1))
    page = doc[page_idx]
    found_matches = 0

    if highlight_text and len(highlight_text.strip()) >= 4:
        # Try full quote first, then fallback to 4-word chunks
        candidates = [highlight_text.strip(), " ".join(highlight_text.strip().split()[:5])]
        for cand in candidates:
            if len(cand) < 4:
                continue
            rects = page.search_for(cand)
            if rects:
                found_matches = len(rects)
                for r in rects:
                    annot = page.add_highlight_annot(r)
                    annot.set_colors(stroke=(1, 0.95, 0))  # Neon yellow highlight
                    annot.update()
                break

    pix = page.get_pixmap(dpi=dpi)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    if found_matches > 0:
        draw = ImageDraw.Draw(img)
        scale = dpi / 72.0
        for r in rects:
            x0, y0, x1, y1 = int(r.x0 * scale), int(r.y0 * scale), int(r.x1 * scale), int(r.y1 * scale)
            draw.rectangle([x0 - 4, y0 - 4, x1 + 4, y1 + 4], outline="#ef4444", width=3)

    return img, len(doc), page.get_text("text"), found_matches

@st.dialog("📖 Interactive Source Reader & Auto-Highlighter", width="large")
def open_source_highlighter_modal(source_citation: str, highlight_quote: str = ""):
    """Pop-up window with adjustable display size and automatic yellow text highlighting on the PDF page."""
    pdf_file, init_page, quote = find_best_source_page(source_citation, highlight_quote)
    st.markdown(f"**🔍 Source Citation:** `{source_citation}`")
    if quote:
        st.caption(f"🎯 **Target Highlight Phrase:** *\"{quote}\"*")

    if pdf_file and pdf_file in st.session_state.raw_pdf_bytes and PYMUPDF_AVAILABLE:
        pdf_bytes = st.session_state.raw_pdf_bytes[pdf_file]
        doc_tmp = fitz.open(stream=pdf_bytes, filetype="pdf")
        max_p = len(doc_tmp)

        ctrl_c1, ctrl_c2, ctrl_c3 = st.columns([1, 1, 2])
        with ctrl_c1:
            sel_page = st.number_input("Page / Slide Number:", min_value=1, max_value=max(1, max_p), value=min(init_page, max_p))
        with ctrl_c2:
            zoom_width = st.slider("Adjust Viewer Window Size (px):", min_value=450, max_value=1200, value=820, step=50)
        with ctrl_c3:
            search_override = st.text_input("Highlight Custom Keyword on Page:", value=quote)

        img, total_pages, extracted_txt, hits = render_highlighted_pdf_page(pdf_bytes, int(sel_page), search_override)
        if hits > 0:
            st.success(f"✅ Highlighted {hits} exact match(es) on Page {sel_page} of `{pdf_file}`!")
        elif search_override:
            st.info(f"📄 Showing Page {sel_page} of `{pdf_file}`. (Exact phrase may be inside a diagram or split across lines—see highlighted text below).")

        st.image(img, caption=f"{pdf_file} — Page {sel_page} of {total_pages}", width=zoom_width)

        with st.expander("📝 View Searchable Text Extracted From This Page"):
            if search_override and search_override.lower() in extracted_txt.lower():
                pattern = re.compile(re.escape(search_override), re.IGNORECASE)
                highlighted_html = pattern.sub(
                    lambda m: f"<mark style='background:#fef08a;color:#0f172a;font-weight:bold;padding:2px 4px;'>{m.group(0)}</mark>",
                    extracted_txt
                )
                st.markdown(highlighted_html, unsafe_allow_html=True)
            else:
                st.write(extracted_txt)
    else:
        st.info("📌 **Direct Citation Reference:** " + source_citation)
        if highlight_quote:
            st.markdown(f"> **Key Source Passage:** <mark style='background:#fef08a;padding:2px 6px;'>{highlight_quote}</mark>", unsafe_allow_html=True)
        st.caption("Tip: Upload the `.pdf` version of your PowerPoint or textbook chapter to view the visual page with automatic yellow text highlighting.")

@st.dialog("⚠️ More Study Data Needed for Weak-Spot Sheet")
def show_insufficient_data_modal(current_count: int, required_count: int = 5):
    st.markdown(f"""
    ### 📊 Insufficient Individualized Data Collected (`{current_count}/{required_count}` Interactions)
    To generate an authentic, personalized **Weak-Areas Quick Review Sheet** without guessing or hallucinating your weak spots, **Vertex Anesthesia** needs at least `{required_count}` logged study interactions!
    """)
    if st.button("Got It! Take Me Back"):
        st.rerun()

# ----------------------------------------------------
# 6. AUDIO, KARAOKE PODCAST & MOLECULAR ANIMATION DECKS
# ----------------------------------------------------
def pcm_to_wav_bytes(pcm_data: bytes, sample_rate: int = 24000) -> bytes:
    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    return wav_io.getvalue()

def render_vertex_audio_player(wav_bytes: bytes, player_id: str, title: str = "Vertex Anesthesia Audio Track", transcript_text: str = "", start_pct: float = 0.0):
    """
    Custom HTML5 Audio Deck with:
    - 0.5x, 0.75x, 1.0x, 1.25x, 1.50x speed buttons + Play/Pause/Restart
    - Live Karaoke Word-by-Word Highlighting & Click-Any-Word-to-Skip when transcript_text is provided!
    """
    b64_audio = base64.b64encode(wav_bytes).decode("utf-8")
    safe_id = re.sub(r"[^a-zA-Z0-9_]", "_", player_id)

    words_html = ""
    has_karaoke = bool(transcript_text and len(transcript_text.strip()) > 0)
    if has_karaoke:
        tokens = transcript_text.replace("\n", " <br> ").split(" ")
        word_spans = []
        valid_words = [t for t in tokens if t.strip() and t != "<br>"]
        total_w = max(1, len(valid_words))
        w_counter = 0
        for tok in tokens:
            if tok == "<br>":
                word_spans.append("<br>")
            elif tok.strip():
                pct_pos = (w_counter / total_w) * 100.0
                esc_tok = tok.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                word_spans.append(
                    f"<span class='kw_{safe_id}' data-pct='{pct_pos:.3f}' "
                    f"onclick='jumpPct_{safe_id}({pct_pos:.3f})' "
                    f"style='cursor:pointer; padding:1px 3px; border-radius:4px; transition:background 0.12s;'>{esc_tok}</span>"
                )
                w_counter += 1
        words_html = f"""
        <div id="karaoke_box_{safe_id}" style="background:#0f172a; color:#e2e8f0; padding:12px 14px; border-radius:8px; margin-top:10px; max-height:190px; overflow-y:auto; line-height:1.75; font-size:0.92rem; border:1px solid #334155;">
            <div style="font-size:0.76rem; color:#a855f7; font-weight:700; margin-bottom:6px;">
                ✨ INTERACTIVE TRANSCRIPT (Words highlight as spoken — Click ANY word to skip audio to that spot!):
            </div>
            {" ".join(word_spans)}
        </div>
        """

    html_code = f"""
    <div style="background:#1e293b; color:#f8fafc; padding:14px 18px; border-radius:10px; font-family:sans-serif; border-left:5px solid #ec4899; box-shadow:0 2px 6px rgba(0,0,0,0.15);">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; flex-wrap:wrap; gap:8px;">
            <span style="font-weight:700; font-size:0.95rem; color:#e2e8f0;">🎧 {title}</span>
            <span id="time_{safe_id}" style="font-size:0.82rem; color:#94a3b8; font-family:monospace;">00:00 / 00:00 (1.0x)</span>
        </div>
        <audio id="aud_{safe_id}" src="data:audio/wav;base64,{b64_audio}" preload="metadata"></audio>
        <input type="range" id="seek_{safe_id}" value="0" max="100" step="0.1" 
               style="width:100%; accent-color:#ec4899; cursor:pointer; margin-bottom:12px;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
            <div style="display:flex; gap:8px;">
                <button onclick="playAud_{safe_id}()" style="background:#502d7f; color:white; border:none; padding:7px 16px; border-radius:6px; font-weight:600; cursor:pointer;">▶️ Play</button>
                <button onclick="pauseAud_{safe_id}()" style="background:#334155; color:white; border:none; padding:7px 16px; border-radius:6px; font-weight:600; cursor:pointer;">⏸️ Pause</button>
                <button onclick="restartAud_{safe_id}()" style="background:#334155; color:#cbd5e1; border:none; padding:7px 12px; border-radius:6px; font-weight:600; cursor:pointer;">⏮️ Restart</button>
            </div>
            <div style="display:flex; align-items:center; gap:5px; flex-wrap:wrap;">
                <span style="font-size:0.8rem; color:#cbd5e1; margin-right:4px;">Speed:</span>
                <button class="spd_{safe_id}" onclick="setSpd_{safe_id}(0.5, this)" style="background:#0f172a; color:#cbd5e1; border:1px solid #475569; padding:5px 10px; border-radius:5px; cursor:pointer; font-size:0.8rem; font-weight:600;">0.5x</button>
                <button class="spd_{safe_id}" onclick="setSpd_{safe_id}(0.75, this)" style="background:#0f172a; color:#cbd5e1; border:1px solid #475569; padding:5px 10px; border-radius:5px; cursor:pointer; font-size:0.8rem; font-weight:600;">0.75x</button>
                <button class="spd_{safe_id}" onclick="setSpd_{safe_id}(1.0, this)" style="background:#502d7f; color:white; border:1px solid #a855f7; padding:5px 10px; border-radius:5px; cursor:pointer; font-size:0.8rem; font-weight:700;">1.0x</button>
                <button class="spd_{safe_id}" onclick="setSpd_{safe_id}(1.25, this)" style="background:#0f172a; color:#cbd5e1; border:1px solid #475569; padding:5px 10px; border-radius:5px; cursor:pointer; font-size:0.8rem; font-weight:600;">1.25x</button>
                <button class="spd_{safe_id}" onclick="setSpd_{safe_id}(1.5, this)" style="background:#0f172a; color:#cbd5e1; border:1px solid #475569; padding:5px 10px; border-radius:5px; cursor:pointer; font-size:0.8rem; font-weight:600;">1.50x</button>
            </div>
        </div>
        {words_html}
    </div>
    <script>
        const aud_{safe_id} = document.getElementById("aud_{safe_id}");
        const seek_{safe_id} = document.getElementById("seek_{safe_id}");
        const time_{safe_id} = document.getElementById("time_{safe_id}");
        const words_{safe_id} = document.getElementsByClassName("kw_{safe_id}");
        let curRate_{safe_id} = 1.0;

        function fmtTime_{safe_id}(s) {{
            if (!isFinite(s) || s < 0) return "00:00";
            const m = Math.floor(s / 60);
            const sec = Math.floor(s % 60);
            return (m < 10 ? "0" + m : m) + ":" + (sec < 10 ? "0" + sec : sec);
        }}
        function playAud_{safe_id}() {{ aud_{safe_id}.play(); }}
        function pauseAud_{safe_id}() {{ aud_{safe_id}.pause(); }}
        function restartAud_{safe_id}() {{ aud_{safe_id}.currentTime = 0; aud_{safe_id}.play(); }}
        function jumpPct_{safe_id}(pct) {{
            if (aud_{safe_id}.duration) {{
                aud_{safe_id}.currentTime = (pct / 100.0) * aud_{safe_id}.duration;
                aud_{safe_id}.play();
            }}
        }}
        function setSpd_{safe_id}(rate, btn) {{
            curRate_{safe_id} = rate;
            aud_{safe_id}.playbackRate = rate;
            const btns = document.getElementsByClassName("spd_{safe_id}");
            for (let b of btns) {{
                b.style.background = "#0f172a";
                b.style.color = "#cbd5e1";
                b.style.borderColor = "#475569";
            }}
            btn.style.background = "#502d7f";
            btn.style.color = "white";
            btn.style.borderColor = "#a855f7";
            updTime_{safe_id}();
        }}
        function updTime_{safe_id}() {{
            time_{safe_id}.innerText = fmtTime_{safe_id}(aud_{safe_id}.currentTime) + " / " + fmtTime_{safe_id}(aud_{safe_id}.duration) + " (" + curRate_{safe_id}.toFixed(2).replace(".00", ".0") + "x)";
            if (words_{safe_id}.length > 0 && aud_{safe_id}.duration > 0) {{
                const curPct = (aud_{safe_id}.currentTime / aud_{safe_id}.duration) * 100.0;
                let activeIdx = Math.floor((curPct / 100.0) * words_{safe_id}.length);
                activeIdx = Math.max(0, Math.min(words_{safe_id}.length - 1, activeIdx));
                for (let i = 0; i < words_{safe_id}.length; i++) {{
                    if (i === activeIdx) {{
                        words_{safe_id}[i].style.background = "#ec4899";
                        words_{safe_id}[i].style.color = "#ffffff";
                        words_{safe_id}[i].style.fontWeight = "700";
                    }} else if (i < activeIdx) {{
                        words_{safe_id}[i].style.background = "transparent";
                        words_{safe_id}[i].style.color = "#cbd5e1";
                        words_{safe_id}[i].style.fontWeight = "normal";
                    }} else {{
                        words_{safe_id}[i].style.background = "transparent";
                        words_{safe_id}[i].style.color = "#94a3b8";
                        words_{safe_id}[i].style.fontWeight = "normal";
                    }}
                }}
            }}
        }}
        aud_{safe_id}.addEventListener("loadedmetadata", () => {{
            seek_{safe_id}.max = aud_{safe_id}.duration || 100;
            if ({start_pct} > 0 && aud_{safe_id}.duration) {{
                aud_{safe_id}.currentTime = ({start_pct} / 100.0) * aud_{safe_id}.duration;
            }}
            updTime_{safe_id}();
        }});
        aud_{safe_id}.addEventListener("timeupdate", () => {{
            seek_{safe_id}.value = aud_{safe_id}.currentTime;
            updTime_{safe_id}();
        }});
        seek_{safe_id}.addEventListener("input", () => {{
            aud_{safe_id}.currentTime = seek_{safe_id}.value;
            updTime_{safe_id}();
        }});
    </script>
    """
    components.html(html_code, height=345 if has_karaoke else 142)

def render_vertex_animation_deck(svg_html: str, deck_id: str):
    safe_id = re.sub(r"[^a-zA-Z0-9_]", "_", deck_id)
    wrapped_html = f"""
    <div style="background:#0f172a; border-radius:12px; padding:12px; color:#f8fafc; font-family:sans-serif; border:1px solid #334155;">
        <div style="display:flex; justify-content:space-between; align-items:center; background:#1e293b; padding:8px 14px; border-radius:8px; margin-bottom:10px; flex-wrap:wrap; gap:8px;">
            <div style="display:flex; align-items:center; gap:8px;">
                <span style="font-weight:700; font-size:0.88rem; color:#e2e8f0;">🎬 Molecular Video & Animation Controls:</span>
                <button onclick="playAnim_{safe_id}()" style="background:#502d7f; color:white; border:none; padding:5px 12px; border-radius:5px; font-weight:600; cursor:pointer; font-size:0.8rem;">▶️ Play</button>
                <button onclick="pauseAnim_{safe_id}()" style="background:#334155; color:white; border:none; padding:5px 12px; border-radius:5px; font-weight:600; cursor:pointer; font-size:0.8rem;">⏸️ Pause</button>
            </div>
            <div style="display:flex; align-items:center; gap:5px; flex-wrap:wrap;">
                <span style="font-size:0.78rem; color:#cbd5e1;">Animation Speed:</span>
                <button class="vspd_{safe_id}" onclick="setAnimSpd_{safe_id}(0.5, this)" style="background:#0f172a; color:#cbd5e1; border:1px solid #475569; padding:4px 9px; border-radius:4px; cursor:pointer; font-size:0.78rem; font-weight:600;">0.5x</button>
                <button class="vspd_{safe_id}" onclick="setAnimSpd_{safe_id}(0.75, this)" style="background:#0f172a; color:#cbd5e1; border:1px solid #475569; padding:4px 9px; border-radius:4px; cursor:pointer; font-size:0.78rem; font-weight:600;">0.75x</button>
                <button class="vspd_{safe_id}" onclick="setAnimSpd_{safe_id}(1.0, this)" style="background:#502d7f; color:white; border:1px solid #a855f7; padding:4px 9px; border-radius:4px; cursor:pointer; font-size:0.78rem; font-weight:700;">1.0x</button>
                <button class="vspd_{safe_id}" onclick="setAnimSpd_{safe_id}(1.25, this)" style="background:#0f172a; color:#cbd5e1; border:1px solid #475569; padding:4px 9px; border-radius:4px; cursor:pointer; font-size:0.78rem; font-weight:600;">1.25x</button>
                <button class="vspd_{safe_id}" onclick="setAnimSpd_{safe_id}(1.5, this)" style="background:#0f172a; color:#cbd5e1; border:1px solid #475569; padding:4px 9px; border-radius:4px; cursor:pointer; font-size:0.78rem; font-weight:600;">1.50x</button>
            </div>
        </div>
        <div id="canvas_{safe_id}">{svg_html}</div>
    </div>
    <script>
        const canvas_{safe_id} = document.getElementById("canvas_{safe_id}");
        function playAnim_{safe_id}() {{
            canvas_{safe_id}.getAnimations({{ subtree: true }}).forEach(a => a.play());
            canvas_{safe_id}.querySelectorAll("video").forEach(v => v.play());
        }}
        function pauseAnim_{safe_id}() {{
            canvas_{safe_id}.getAnimations({{ subtree: true }}).forEach(a => a.pause());
            canvas_{safe_id}.querySelectorAll("video").forEach(v => v.pause());
        }}
        function setAnimSpd_{safe_id}(rate, btn) {{
            canvas_{safe_id}.getAnimations({{ subtree: true }}).forEach(a => {{ a.playbackRate = rate; }});
            canvas_{safe_id}.querySelectorAll("video").forEach(v => {{ v.playbackRate = rate; }});
            const btns = document.getElementsByClassName("vspd_{safe_id}");
            for (let b of btns) {{
                b.style.background = "#0f172a";
                b.style.color = "#cbd5e1";
                b.style.borderColor = "#475569";
            }}
            btn.style.background = "#502d7f";
            btn.style.color = "white";
            btn.style.borderColor = "#a855f7";
        }}
    </script>
    """
    components.html(wrapped_html, height=530, scrolling=True)

def synthesize_tutor_speech(client, text_to_speak: str, voice_name: str = "Kore", multi_speaker: bool = False, host2_voice: str = "Puck") -> bytes:
    try:
        if multi_speaker:
            speech_cfg = types.SpeechConfig(
                multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                    speaker_voice_configs=[
                        types.SpeakerVoiceConfig(
                            speaker="Alex",
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=host2_voice)
                            )
                        ),
                        types.SpeakerVoiceConfig(
                            speaker="Sam",
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                            )
                        )
                    ]
                )
            )
        else:
            speech_cfg = types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                )
            )
        audio_res = client.models.generate_content(
            model="gemini-3.1-flash-tts-preview",
            contents=text_to_speak,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=speech_cfg
            )
        )
        raw_pcm = audio_res.candidates[0].content.parts[0].inline_data.data
        return pcm_to_wav_bytes(raw_pcm)
    except Exception:
        return None

def render_annotated_slide(pdf_bytes: bytes, page_num: int, annotations: list, zoom_box: list = None) -> Image.Image:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page_idx = max(0, min(page_num - 1, len(doc) - 1))
    page = doc[page_idx]
    pix = page.get_pixmap(dpi=200)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    draw = ImageDraw.Draw(img)
    w, h = img.size

    for ann in annotations:
        x = int((ann.get("x", 50) / 100.0) * w)
        y = int((ann.get("y", 50) / 100.0) * h)
        r = int((ann.get("radius", 12) / 100.0) * min(w, h))
        shape = ann.get("type", "circle").lower()
        label = ann.get("label", "KEY CONCEPT")

        if shape == "circle":
            for offset in range(5):
                draw.ellipse([x - r - offset, y - r - offset, x + r + offset, y + r + offset], outline="#ef4444")
        elif shape == "star":
            draw.polygon([
                (x, y - r), (x + r//3, y - r//3), (x + r, y - r//3),
                (x + r//2, y + r//6), (x + r*2//3, y + r), (x, y + r//2),
                (x - r*2//3, y + r), (x - r//2, y + r//6), (x - r, y - r//3),
                (x - r//3, y - r//3)
            ], outline="#f59e0b", width=5)
        else:
            start_x, start_y = max(10, x - int(w * 0.15)), max(10, y - int(h * 0.15))
            draw.line([(start_x, start_y), (x, y)], fill="#ef4444", width=7)
            draw.ellipse([x - 10, y - 10, x + 10, y + 10], fill="#ef4444")

        tag_y = max(10, y - r - 35)
        draw.rectangle([x - 95, tag_y, x + 145, tag_y + 28], fill="#502d7f", outline="#ffffff", width=2)
        draw.text((x - 86, tag_y + 6), f"★ {label[:28]}", fill="#ffffff")

    if zoom_box and len(zoom_box) == 4:
        zx1 = max(0, int((zoom_box[0] / 100.0) * w))
        zy1 = max(0, int((zoom_box[1] / 100.0) * h))
        zx2 = min(w, int((zoom_box[2] / 100.0) * w))
        zy2 = min(h, int((zoom_box[3] / 100.0) * h))
        if zx2 - zx1 > 100 and zy2 - zy1 > 100:
            img = img.crop((zx1, zy1, zx2, zy2))
    return img

def check_podcast_cross_reference(query_text: str, key_prefix: str):
    """
    Checks if the topic the student is asking about in another tab is covered in their generated Podcast.
    If matched, renders an inline Mini-Player jumped directly to that podcast segment without leaving the current tab!
    """
    if not st.session_state.podcast_topic_index or not st.session_state.podcast_audio:
        return
    q_words = {w.lower() for w in re.findall(r"[a-zA-Z]{4,}", query_text)}
    for idx, item in enumerate(st.session_state.podcast_topic_index):
        topic_str = f"{item.get('topic', '')} {' '.join(item.get('subtopics', []))} {item.get('summary', '')}"
        t_words = {w.lower() for w in re.findall(r"[a-zA-Z]{4,}", topic_str)}
        overlap = q_words.intersection(t_words)
        if len(overlap) >= 2:
            st.markdown(f"""
            <div class="meme-box">
                🎧 <strong>Podcast Cross-Reference Detected!</strong> This exact topic (<strong>{item.get('topic')}</strong> — <em>{', '.join(item.get('subtopics', []))}</em>)
                is discussed in your <strong>{item.get('lecture_name', 'Course')}</strong> Podcast! Open the Mini-Player below to listen right here without leaving your study tab:
            </div>
            """, unsafe_allow_html=True)
            with st.expander(f"▶️ Launch Inline Podcast Mini-Player: '{item.get('topic')}' (Jumps to Segment {idx+1})"):
                render_vertex_audio_player(
                    st.session_state.podcast_audio,
                    player_id=f"mini_pod_{key_prefix}_{idx}",
                    title=f"Mini-Player: {item.get('topic')}",
                    transcript_text=item.get("dialogue_excerpt", ""),
                    start_pct=float(item.get("start_pct", 0.0))
                )
                st.caption("💡 Want the full visual chalkboard and all indexed chapters? Click **Tab 5 (🎙️ Interactive Podcast Studio)** at the top of the page!")
            break

def record_question_result(q_item: dict, is_correct: bool, folder_tag: str = "General Vault", asset_type_tag: str = "Combined", honest_idk: bool = False):
    domain = q_item.get("domain", "General Anesthesia")
    lvl = int(q_item.get("difficulty_level", 4))
    metrics = st.session_state.personal_metrics

    d_stats = metrics["domain_stats"]
    if domain not in d_stats:
        d_stats[domain] = {"correct": 0, "total": 0, "idk_count": 0, "levels": []}
    d_stats[domain]["total"] += 1
    if is_correct:
        d_stats[domain]["correct"] += 1
    if honest_idk:
        d_stats[domain]["idk_count"] = d_stats[domain].get("idk_count", 0) + 1
    d_stats[domain]["levels"].append(lvl)

    f_stats = metrics.setdefault("folder_stats", {})
    if folder_tag not in f_stats:
        f_stats[folder_tag] = {"correct": 0, "total": 0}
    f_stats[folder_tag]["total"] += 1
    if is_correct:
        f_stats[folder_tag]["correct"] += 1

    s_stats = metrics.setdefault("source_type_stats", {})
    if asset_type_tag not in s_stats:
        s_stats[asset_type_tag] = {"correct": 0, "total": 0}
    s_stats[asset_type_tag]["total"] += 1
    if is_correct:
        s_stats[asset_type_tag]["correct"] += 1

    q_stem = q_item.get("question", "")
    if q_stem and q_stem not in metrics.setdefault("asked_questions_ledger", []):
        metrics["asked_questions_ledger"].append(q_stem)

    metrics["history"].append({
        "domain": domain,
        "folder_tag": folder_tag,
        "asset_type": asset_type_tag,
        "difficulty_level": lvl,
        "correct": is_correct,
        "honest_idk": honest_idk,
        "question": q_stem,
        "options": q_item.get("options", []),
        "correct_letter": q_item.get("correct", "A"),
        "explanation": q_item.get("explanation", ""),
        "mnemonic": q_item.get("mnemonic", ""),
        "source": q_item.get("source", ""),
        "highlight_quote": q_item.get("highlight_quote", "")
    })

# ----------------------------------------------------
# 7. UNIVERSAL INTERACTIVE AI TUTOR WITH SOURCE LINK & MEMES
# ----------------------------------------------------
def build_molecular_animator_prompt() -> str:
    persona_rule = get_active_persona_instruction()
    return f"""
You are an elite, multimodal CRNA Board Instructor, Pop-Culture Meme Genius, and Molecular Medical Illustrator for Vertex Anesthesia.
{persona_rule}
{NBCRNA_BLUEPRINT_GROUNDING}

MULTIMODAL & MEME TEACHING RULES:
- Stimulate all senses (visual colors, auditory rhythm, kinesthetic gym/action analogies, and hilarious pop-culture/viral video memes like 'Calcitonin = Kidz Bop Karen telling the OsteoCLAST in the back seat to CALM DOWN -> Calci-Calm-It-Down', or 'Sarcoplasmic Reticulum releasing Ca2+ to bind Troponin and YEETING Tropomyosin off Actin so Myosin heads can power-stroke toward the M-line in the H-zone').
- Make sure the exact words spoken by your AI Voice (`spoken_script`) are fun, creative, and displayed clearly on screen so the student can read along word-for-word!
- Provide an exact `source_citation` (Filename and Page/Slide Number) AND a verbatim 4-to-10 word `highlight_quote` from the document so the student can click the Source Link button to open the PDF Pop-Up with that exact passage highlighted!

You MUST also generate an interactive, animated HTML/SVG Molecular & Receptor Visualization (`animated_svg_html`):
- Use a dark slate canvas (`#0f172a`) with glowing labels and CSS `@keyframes` animations.
- STRICT COLOR PALETTE FOR MOLECULES & IONS:
  * Potassium (K+): Purple (#a855f7) | Sodium (Na+): Orange (#f97316) | Calcium (Ca2+): Neon Green (#22c55e)
  * Chloride (Cl-): Cyan Blue (#06b6d4) | Acetylcholine (ACh): Golden Yellow (#eab308) | NE/Epi: Crimson Red (#ef4444)
  * Anesthesia Drugs / Blockers: Hot Pink/Magenta (#ec4899)

Return ONLY valid JSON with this exact schema:
{{
  "transcribed_user_question": "If the student spoke via microphone, write what they asked here; otherwise echo their text question.",
  "spoken_script": "Full, hilarious, creative spoken script in your selected Persona to be spoken aloud AND read on-screen word-for-word.",
  "markdown_explanation": "Rich, color-coded Markdown explanation with step-by-step multimodal breakdown, viral meme/pop-culture anchor, and cross-course spaced-repetition pearl.",
  "source_citation": "Exact Filename, Page X or Slide Y",
  "highlight_quote": "Exact 4 to 10 word verbatim phrase from the source page to auto-highlight in the PDF pop-up viewer",
  "animated_svg_html": "<div style='background:#0f172a;padding:16px;border-radius:12px;color:white;font-family:sans-serif;'>...complete self-contained HTML + <style>@keyframes ...</style> + <svg viewBox='0 0 800 420' width='100%' height='420'>...</svg></div>"
}}
"""

def render_contextual_tutor(client, active_file_refs: list, context_id: str, context_summary: str, button_label: str = "💬 Explain This / Ask Vertex AI Tutor (Voice + Read-Along + Source Link)", is_podcast_intervention: bool = False, voice_1: str = "Kore", voice_2: str = "Puck"):
    if context_id not in st.session_state.tutor_threads:
        st.session_state.tutor_threads[context_id] = []

    with st.expander(button_label, expanded=(context_id == "main_sandbox")):
        st.markdown("""
        <div class="ion-legend">
            <strong>🧬 Vertex Molecular Color Key:</strong>
            <span style="color:#a855f7;">● K⁺ (Potassium)</span>
            <span style="color:#f97316;">● Na⁺ (Sodium)</span>
            <span style="color:#22c55e;">● Ca²⁺ (Calcium)</span>
            <span style="color:#06b6d4;">● Cl⁻ (Chloride)</span>
            <span style="color:#eab308;">▲ ACh (Acetylcholine)</span>
            <span style="color:#ef4444;">▲ NE/Epi</span>
            <span style="color:#ec4899;">★ Anesthesia Drug / Blocker</span>
        </div>
        """, unsafe_allow_html=True)

        q_col1, q_col2, q_col3 = st.columns(3)
        triggered_prompt = None
        mic_audio_part = None

        with q_col1:
            if st.button("🧒 Explain Like I'm 8 (Viral Meme + Slow Audio)", key=f"eli8_{context_id}"):
                triggered_prompt = (
                    "Explain this to me like I'm an 8-year-old using a hilarious viral meme or pop-culture story, "
                    "stimulate all my senses, speak it aloud so I can follow the words on screen, and animate the molecules!"
                )
        with q_col2:
            if st.button("💪 Gym / Action Analogy + Receptor Animation", key=f"mol_{context_id}"):
                triggered_prompt = (
                    "Give me an unforgettable, high-energy anatomical shoutout (like the Sarcoplasmic Reticulum yeeting Tropomyosin off Actin) "
                    "for this exact mechanism, animate the receptors/ions, and link the exact source page!"
                )
        with q_col3:
            speak_reply = st.checkbox("🔊 Read Aloud With Karaoke Word Highlighting", value=True, key=f"tts_chk_{context_id}")

        in_col1, in_col2 = st.columns([1, 1])
        with in_col1:
            custom_q = st.text_input(
                "⌨️ Type a question:",
                placeholder="e.g., Explain this pathway with a funny meme and show me where it came from!",
                key=f"input_{context_id}"
            )
            if st.button("🚀 Send Question", key=f"send_{context_id}"):
                if custom_q.strip():
                    triggered_prompt = custom_q.strip()

        with in_col2:
            if hasattr(st, "audio_input"):
                mic_recording = st.audio_input("🎤 Speak Question Into Microphone:", key=f"mic_{context_id}")
                if mic_recording is not None:
                    if st.button("🎙️ Submit Voice Question", key=f"send_mic_{context_id}"):
                        mic_bytes = mic_recording.getvalue()
                        mic_audio_part = types.Part.from_bytes(data=mic_bytes, mime_type="audio/wav")
                        triggered_prompt = "Listen to the student's spoken microphone question in the attached audio clip and answer it with a meme hook, molecular animation, and exact source citation."

        if triggered_prompt:
            st.session_state.personal_metrics["verbal_interactions_count"] = st.session_state.personal_metrics.get("verbal_interactions_count", 0) + 1
            with st.spinner("Synthesizing multimodal meme explanation, karaoke audio, source link, and molecular animation..."):
                full_tutor_prompt = f"""
                CURRENT ON-SCREEN CONTEXT:
                {context_summary}

                ACTIVE PERSONA: {get_active_persona_instruction()}
                STUDENT'S QUESTION / REQUEST:
                {triggered_prompt}
                """
                payload = list(active_file_refs)
                if mic_audio_part is not None:
                    payload.append(mic_audio_part)
                payload.append(full_tutor_prompt)

                try:
                    res = client.models.generate_content(
                        model="gemini-3.1-pro-preview",
                        contents=payload,
                        config=types.GenerateContentConfig(
                            system_instruction=build_molecular_animator_prompt(),
                            response_mime_type="application/json",
                            temperature=0.3
                        )
                    )
                    tutor_reply = json.loads(res.text)
                    audio_bytes = None
                    if speak_reply and tutor_reply.get("spoken_script"):
                        audio_bytes = synthesize_tutor_speech(
                            client,
                            tutor_reply["spoken_script"],
                            voice_name=voice_1,
                            multi_speaker=is_podcast_intervention,
                            host2_voice=voice_2
                        )
                    st.session_state.tutor_threads[context_id].append({
                        "user_q": tutor_reply.get("transcribed_user_question", triggered_prompt),
                        "reply": tutor_reply,
                        "audio": audio_bytes
                    })
                except Exception as e:
                    st.error(f"Tutor engine error: {e}")

        for turn_idx, turn in enumerate(reversed(st.session_state.tutor_threads[context_id])):
            st.markdown(f"**🙋‍♂️ You asked:** *{turn['user_q']}*")
            rep = turn["reply"]

            # Check if this topic matches an indexed Podcast section and offer Mini-Player!
            check_podcast_cross_reference(f"{turn['user_q']} {rep.get('markdown_explanation', '')}", key_prefix=f"{context_id}_{turn_idx}")

            # Spoken Audio + Visible On-Screen Read-Along Script (With Word Highlighting)
            spoken_txt = rep.get("spoken_script", "")
            if turn.get("audio"):
                render_vertex_audio_player(
                    turn["audio"],
                    player_id=f"tutor_aud_{context_id}_{turn_idx}",
                    title=f"Read-Along Voice Explanation ({voice_1})",
                    transcript_text=spoken_txt
                )
            elif spoken_txt:
                st.info(f"🗣️ **Spoken Script (Visible Read-Along):** {spoken_txt}")

            st.markdown(rep.get("markdown_explanation", ""), unsafe_allow_html=True)

            # Direct Link to Open Source Pop-Up & Auto-Highlight Text
            src_cit = rep.get("source_citation", "Uploaded Course Materials")
            hl_quote = rep.get("highlight_quote", "")
            st.markdown(f"<span class='source-badge'>📍 Pulled From: {src_cit}</span>", unsafe_allow_html=True)
            if st.button(f"📖 Open Source & Highlight Quote ({src_cit})", key=f"src_btn_{context_id}_{turn_idx}"):
                open_source_highlighter_modal(src_cit, hl_quote)

            svg_html = rep.get("animated_svg_html", "")
            if svg_html:
                st.markdown("##### ⚡ Live Molecular & Receptor Pathophysiology Animation")
                render_vertex_animation_deck(svg_html, deck_id=f"anim_{context_id}_{turn_idx}")
            st.markdown("---")

# ----------------------------------------------------
# 8. SIDEBAR: THEME, VOICE PERSONA, FOLDERS & INDEXING
# ----------------------------------------------------
with st.sidebar:
    st.header("🎨 Epic Clinician Theme & Persona")
    selected_theme = st.selectbox(
        "Workspace Color Theme (Epic Style):",
        list(EPIC_THEMES.keys()),
# Safe Theme Key Initialization & Selection
    if "user_preferences" not in st.session_state:
        st.session_state.user_preferences = {
            "theme": "Amethyst & Black (Dark Amethyst)",
            "voice": "Kore",
            "persona": "👑 Fierce Drag Queen Diva & Viral Meme Queen",
            "custom_persona_text": ""
        }

    if "theme" not in st.session_state.user_preferences:
        st.session_state.user_preferences["theme"] = "Amethyst & Black (Dark Amethyst)"
        
    current_theme_saved = st.session_state.user_preferences["theme"]
    available_themes = list(EPIC_THEMES.keys())
    theme_default_index = available_themes.index(current_theme_saved) if current_theme_saved in available_themes else 0

    selected_theme = st.selectbox(
        "Workspace Color Theme (Epic Style):",
        available_themes,
        index=theme_default_index
    )
    st.session_state.user_preferences["theme"] = selected_theme
    apply_epic_theme(selected_theme)

    selected_persona = st.selectbox(
        "🎭 AI Tutor Voice & Meme Personality:",
        list(PERSONA_PROMPTS.keys()),
        index=list(PERSONA_PROMPTS.keys()).index(st.session_state.user_preferences.get("persona", "👑 Fierce Drag Queen Diva & Viral Meme Queen"))
    )
    st.session_state.user_preferences["persona"] = selected_persona

    if selected_persona == "✍️ Custom Saved Personality":
        st.session_state.user_preferences["custom_persona_text"] = st.text_area(
            "Describe your custom AI personality:",
            value=st.session_state.user_preferences.get("custom_persona_text", ""),
            placeholder="e.g., Talk to me like a hilarious gym bro + viral TikTok creator..."
        )

    voice_options = ["Kore", "Puck", "Charon", "Orus", "Fenrir", "Aoede", "Leda", "Zephyr"]
    default_voice_idx = 2 if "J.A.R.V.I.S." in selected_persona else voice_options.index(st.session_state.user_preferences.get("voice", "Kore"))
    tutor_voice_pref = st.selectbox(
        "🗣️ Preferred Read-Aloud & Tutor Voice:",
        voice_options,
        index=default_voice_idx
    )
    st.session_state.user_preferences["voice"] = tutor_voice_pref

    st.markdown("---")
    st.header("🔑 Authentication Hub")
    student_alias = st.text_input("Your First Name / Alias (Private):", value="SRNA Candidate")
    secret_key = st.text_input("Enter your Gemini API Key:", type="password")
    api_key_to_use = secret_key if secret_key else os.environ.get("GEMINI_API_KEY", "")

    if not api_key_to_use:
        st.warning("⚠️ Access Locked: Please input an API key to activate your private Vertex Anesthesia workspace.")
        st.stop()
        
    user_Read_hash = hashlib.sha256(f"{student_alias}_{api_key_to_use}".encode()).hexdigest()[:10].upper()
    st.caption(f"🔒 **Private Vault ID:** `{user_Read_hash}` (Isolated from classmates)")
    client = genai.Client(api_key=api_key_to_use)

    st.markdown("---")
    st.header("📂 Rapid-Indexed Course Vault")
    course_tag = st.selectbox("1. Select Course:", [
        "Advanced Pathophysiology",
        "Advanced Physiology",
        "Anesthesia Pharmacology",
        "Chemistry & Physics for Anesthesia",
        "Clinical Anesthesia Principles"
    ])
    folder_tag = st.text_input("2. Exam / Module Folder Name:", value="Exam 2")
    section_tag = st.selectbox("3. Organ System / Topic Section:", [
        "Cardiac & Vascular",
        "Respiratory & Airway",
        "Renal & Urologic",
        "Neuro & Neuromuscular",
        "Hepatic, GI & Endocrine",
        "Hematology & Coagulation",
        "General Cellular & Molecular"
    ])
    asset_type_tag = st.radio("4. Material Classification:", [
        "PowerPoint Lecture",
        "Textbook Chapter",
        "External Q-Bank PDF (e.g., Prodigy / Apex)",
        "Combined / Supplemental"
    ])

    uploaded_files = st.file_uploader("Upload Course Files or Textbook PDFs (.pdf, .pptx)", type=["pdf", "pptx"], accept_multiple_files=True)
    
    if st.button("🚀 Upload & Rapid-Index Files"):
        if not uploaded_files:
            st.error("Please select at least one PDF or PPTX file first.")
        else:
            with st.spinner("Uploading to Gemini Vision & building local page-level highlight index..."):
                added_count = 0
                for f in uploaded_files:
                    file_bytes = f.getvalue()
                    if f.name.lower().endswith(".pdf"):
                        st.session_state.raw_pdf_bytes[f.name] = file_bytes
                        index_pdf_locally(f.name, file_bytes)
                    temp_path = f.name
                    with open(temp_path, "wb") as temp_file:
                        temp_file.write(file_bytes)
                    cloud_file = client.files.upload(file=temp_path)
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    
                    st.session_state.file_catalog = [item for item in st.session_state.file_catalog if item["name"] != f.name]
                    st.session_state.file_catalog.append({
                        "name": f.name,
                        "cloud_ref": cloud_file,
                        "course": course_tag,
                        "folder": folder_tag.strip() or "General",
                        "section": section_tag,
                        "asset_type": asset_type_tag
                    })
                    added_count += 1
                st.success(f"Indexed {added_count} file(s) into [{course_tag} -> {folder_tag} -> {section_tag}]!")

    st.markdown("---")
    st.header("📥 Upload Custom .JSON Question Bank")
    uploaded_qbank_json = st.file_uploader("Upload Custom Question Bank (.json):", type=["json"], key="qbank_json_up")
    if uploaded_qbank_json is not None:
        if st.button("➕ Import .JSON Question Bank"):
            try:
                raw_qb = json.load(uploaded_qbank_json)
                qb_list = raw_qb if isinstance(raw_qb, list) else raw_qb.get("questions", [])
                for item in qb_list:
                    if isinstance(item, dict) and "question" in item:
                        st.session_state.custom_qbank_items.append({
                            "q_format": item.get("q_format", "MCQ"),
                            "domain": item.get("domain", section_tag),
                            "difficulty_level": int(item.get("difficulty_level", 5)),
                            "peer_pct": int(item.get("peer_pct", 65)),
                            "question": item["question"],
                            "options": item.get("options", ["A) True", "B) False"]),
                            "correct": item.get("correct", "A"),
                            "hint": item.get("hint", "Review the primary mechanism."),
                            "celebration_line": item.get("celebration_line", "Boom! Nailed it!"),
                            "explanation": item.get("explanation", "Imported from custom JSON Question Bank."),
                            "source": item.get("source", f"Custom Q-Bank: {uploaded_qbank_json.name}"),
                            "highlight_quote": item.get("highlight_quote", ""),
                            "mnemonic": item.get("mnemonic", "Review custom Q-bank key concept."),
                            "is_hot_topic": bool(item.get("is_hot_topic", False)),
                            "logged": False
                        })
                st.success(f"Imported questions from {uploaded_qbank_json.name}!")
            except Exception as e:
                st.error(f"Could not parse JSON Question Bank: {e}")

    st.markdown("---")
    st.header("🎯 Active Scope Filter")
    if st.session_state.file_catalog:
        all_courses = sorted(list({f["course"] for f in st.session_state.file_catalog}))
        all_folders = sorted(list({f["folder"] for f in st.session_state.file_catalog}))
        all_sections = sorted(list({f["section"] for f in st.session_state.file_catalog}))
        all_types = sorted(list({f["asset_type"] for f in st.session_state.file_catalog}))

        sel_courses = st.multiselect("Filter by Course:", all_courses, default=all_courses)
        sel_folders = st.multiselect("Filter by Exam Folder:", all_folders, default=all_folders)
        sel_sections = st.multiselect("Filter by Organ System:", all_sections, default=all_sections)
        sel_types = st.multiselect("Filter by Material Type:", all_types, default=all_types)
        cross_course_bridge = st.checkbox("🧠 Enable Cross-Course Spaced Repetition", value=True)
    else:
        sel_courses, sel_folders, sel_sections, sel_types = [], [], [], []
        cross_course_bridge = True

def get_scoped_files(override_type: str = None, override_section: str = None):
    primary_items = [
        item for item in st.session_state.file_catalog
        if item["course"] in sel_courses
        and item["folder"] in sel_folders
        and (override_section is None or item["section"] == override_section or item["section"] in sel_sections)
        and (override_type is None or item["asset_type"] == override_type or item["asset_type"] in sel_types)
    ]
    if not primary_items and st.session_state.file_catalog:
        primary_items = st.session_state.file_catalog

    background_items = []
    if cross_course_bridge and len(st.session_state.file_catalog) > len(primary_items):
        primary_names = {i["name"] for i in primary_items}
        background_items = [i for i in st.session_state.file_catalog if i["name"] not in primary_names]

    return primary_items, background_items

# ----------------------------------------------------
# 9. MULTI-FORMAT QUIZ ENGINE (MCQ, SATA, MATCHING, PATHWAY)
# ----------------------------------------------------
def generate_structured_questions(client, file_refs: list, q_count: int, q_format_choice: str, blueprint_category: str, diff_choice: str, target_level: int, excluded_questions: list, primary_summary_str: str, extra_instruction: str = "") -> list:
    exclusion_txt = "\n".join([f"- {q[:120]}" for q in excluded_questions[-35:]]) if excluded_questions else "None"
    persona_rule = get_active_persona_instruction()

    prompt = f"""
    You are an expert CRNA Board Examination Author and Multimodal Educator for Vertex Anesthesia.
    {persona_rule}
    {NBCRNA_BLUEPRINT_GROUNDING}

    Generate {q_count} brand-new, non-duplicate questions for:
    - Blueprint Category: {blueprint_category}
    - Requested Question Format: {q_format_choice}
    - Target Difficulty: {diff_choice} (PrepU / NBCRNA Level {target_level} out of 8)
    - Primary Source Files: {primary_summary_str}
    {extra_instruction}

    DO NOT repeat any of these previously asked stems:
    {exclusion_txt}

    QUESTION FORMAT SPECIFICATIONS (`q_format` field):
    1. If `q_format_choice` is "Multiple Choice (Single Answer)" -> set `"q_format": "MCQ"`. Provide 4 options (`["A) ...", "B) ...", "C) ...", "D) ..."]`) and `"correct": "A"`.
    2. If `q_format_choice` is "Select All That Apply (SATA)" -> set `"q_format": "SATA"`. Provide 5 or 6 options (`["A) ...", "B) ...", "C) ...", "D) ...", "E) ..."]`) and `"correct_list": ["A", "C", "E"]` (letters only).
    3. If `q_format_choice` is "Matching (Receptors, Drugs & Labs)" -> set `"q_format": "MATCHING"`. Provide `"matching_pairs": [{{"premise": "Drug/Receptor 1", "match": "Mechanism/Effect 1"}}, ...]` (4 pairs).
    4. If `q_format_choice` is "Pathway Ordering (Physiology / Pathophysiology Sequence)" -> set `"q_format": "PATHWAY"`. Provide `"pathway_steps": ["Step 1 in chronological order", "Step 2 in chronological order", "Step 3 in chronological order", "Step 4 in chronological order"]` (4 to 5 steps in the TRUE physiological order—our UI will scramble them for the student!).
    5. If `q_format_choice` is "High-Yield Multimodal Mix (MCQ + SATA + Matching + Pathway)" -> mix all 4 formats across the generated questions!

    Make `celebration_line` a hilarious, creative anatomical hype shoutout when the student gets it right (like the Sarcoplasmic Reticulum yeeting Tropomyosin off Actin so Myosin can power-stroke toward the M-line in the H-zone!).
    Make `mnemonic` include a funny viral meme or pop-culture reference (like Kidz Bop Karen telling the OsteoCLAST to 'CALM DOWN' for Calcitonin = 'Calci-Calm-It-Down').
    Provide an exact `highlight_quote` (4 to 10 verbatim words from the slide/page) so our PDF viewer can highlight where the answer came from!

    Return ONLY valid JSON as a list of objects matching this schema:
    [
      {{
        "q_format": "MCQ | SATA | MATCHING | PATHWAY",
        "domain": "NBCRNA Domain Name",
        "difficulty_level": {target_level},
        "peer_pct": 66,
        "is_hot_topic": true,
        "question": "Question stem here...",
        "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
        "correct": "A",
        "correct_list": ["A", "C"],
        "matching_pairs": [{{"premise": "Item 1", "match": "Target 1"}}],
        "pathway_steps": ["First step", "Second step", "Third step", "Fourth step"],
        "hint": "Helpful 1-2 sentence clinical clue without spoiling the answer",
        "celebration_line": "Hilarious anatomical shoutout celebrating a correct answer!",
        "explanation": "Thorough rationale grounded in the files (prefix with 'Note: [Concept] is not directly noted in the source materials' if adding outside consensus context).",
        "source": "Exact Filename, Page X or Slide Y",
        "highlight_quote": "Verbatim 4 to 10 word quote from the source page",
        "mnemonic": "Viral meme / pop-culture hook + Picmonic story"
      }}
    ]
    """
    res = client.models.generate_content(
        model="gemini-3.1-pro-preview",
        contents=list(file_refs) + [prompt],
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.25)
    )
    raw_list = json.loads(res.text)
    parsed = []
    for idx, item in enumerate(raw_list):
        qf = item.get("q_format", "MCQ").upper()
        p_steps = item.get("pathway_steps", [])
        scrambled = list(p_steps)
        if len(scrambled) > 1:
            random.shuffle(scrambled)
        m_pairs = item.get("matching_pairs", [])
        m_targets = [p.get("match", "") for p in m_pairs]
        if len(m_targets) > 1:
            random.shuffle(m_targets)

        parsed.append({
            "q_format": qf,
            "domain": item.get("domain", "Core Clinical Science"),
            "difficulty_level": int(item.get("difficulty_level", target_level)),
            "peer_pct": int(item.get("peer_pct", 65)),
            "is_hot_topic": bool(item.get("is_hot_topic", False)),
            "question": item.get("question", ""),
            "options": item.get("options", []),
            "correct": str(item.get("correct", "A")).strip(),
            "correct_list": [str(x).strip().upper()[:1] for x in item.get("correct_list", [])],
            "matching_pairs": m_pairs,
            "scrambled_matches": m_targets,
            "pathway_steps": p_steps,
            "scrambled_pathway": scrambled,
            "hint": item.get("hint", "Think about the primary physiological mechanism on this slide!"),
            "celebration_line": item.get("celebration_line", "🔥 Shout out to your neurons for firing that action potential straight to the board exam hall of fame!"),
            "explanation": item.get("explanation", ""),
            "source": item.get("source", "Uploaded Course Materials"),
            "highlight_quote": item.get("highlight_quote", ""),
            "mnemonic": item.get("mnemonic", ""),
            "logged": False
        })
    return parsed

def render_question_widget_and_evaluate(q_item: dict, q_key_prefix: str) -> tuple:
    """
    Renders the interactive input widget for MCQ, SATA, MATCHING, or PATHWAY questions.
    Returns (has_answered_bool, is_correct_bool, user_answer_summary_str, correct_answer_summary_str).
    """
    qf = q_item.get("q_format", "MCQ").upper()

    # 1. SELECT ALL THAT APPLY (SATA)
    if qf == "SATA":
        st.caption("☑️ **Select All That Apply (SATA):** Check every correct option below, then click **Lock In SATA Answer**.")
        chosen_letters = []
        for opt_idx, opt_str in enumerate(q_item.get("options", [])):
            letter = opt_str.strip()[:1].upper()
            if st.checkbox(opt_str, key=f"{q_key_prefix}_sata_{opt_idx}"):
                chosen_letters.append(letter)
        locked = st.session_state.selected_answers.get(f"{q_key_prefix}_locked", False)
        if st.button("🔒 Lock In Select-All-That-Apply Answer", key=f"{q_key_prefix}_sata_btn"):
            st.session_state.selected_answers[f"{q_key_prefix}_locked"] = True
            st.session_state.selected_answers[q_key_prefix] = chosen_letters
            locked = True
        saved_choice = st.session_state.selected_answers.get(q_key_prefix, [])
        corr_set = sorted(list(set(q_item.get("correct_list") or [q_item.get("correct", "A")[:1].upper()])))
        is_corr = (sorted(saved_choice) == corr_set) and len(saved_choice) > 0
        return locked, is_corr, ", ".join(saved_choice) or "None", ", ".join(corr_set)

    # 2. MATCHING
    elif qf == "MATCHING" and q_item.get("matching_pairs"):
        st.caption("🔗 **Matching Question:** Match each clinical item on the left with its correct target on the right, then click **Lock In Matches**.")
        pairs = q_item["matching_pairs"]
        choices_pool = q_item.get("scrambled_matches") or [p.get("match", "") for p in pairs]
        user_map = {}
        for p_idx, pair in enumerate(pairs):
            premise = pair.get("premise", f"Item {p_idx+1}")
            sel_m = st.selectbox(f"🔹 {premise}:", ["Select match..."] + choices_pool, key=f"{q_key_prefix}_match_{p_idx}")
            user_map[premise] = sel_m
        locked = st.session_state.selected_answers.get(f"{q_key_prefix}_locked", False)
        if st.button("🔒 Lock In Matching Answers", key=f"{q_key_prefix}_match_btn"):
            st.session_state.selected_answers[f"{q_key_prefix}_locked"] = True
            st.session_state.selected_answers[q_key_prefix] = user_map
            locked = True
        saved_map = st.session_state.selected_answers.get(q_key_prefix, {})
        all_matched = all(saved_map.get(p.get("premise")) == p.get("match") for p in pairs) and bool(saved_map)
        corr_summary = " | ".join([f"{p.get('premise')} → {p.get('match')}" for p in pairs])
        user_summary = " | ".join([f"{k} → {v}" for k, v in saved_map.items()])
        return locked, all_matched, user_summary, corr_summary

    # 3. PHYSIOLOGICAL / PATHOPHYSIOLOGICAL PATHWAY ORDERING
    elif qf == "PATHWAY" and q_item.get("pathway_steps"):
        true_steps = q_item["pathway_steps"]
        pool = q_item.get("scrambled_pathway") or true_steps
        st.caption(f"🧬 **Pathway Ordering Question:** Organize all **{len(true_steps)} steps** of the physiological/pathophysiological pathway in exact chronological order (`Step 1` $\\rightarrow$ `Step {len(true_steps)}`).")
        ordered_selection = []
        for s_idx in range(len(true_steps)):
            picked = st.selectbox(
                f"Step {s_idx + 1} in Pathway:",
                ["Select step..."] + pool,
                key=f"{q_key_prefix}_path_{s_idx}"
            )
            ordered_selection.append(picked)
        locked = st.session_state.selected_answers.get(f"{q_key_prefix}_locked", False)
        if st.button("🔒 Lock In Pathway Sequence", key=f"{q_key_prefix}_path_btn"):
            st.session_state.selected_answers[f"{q_key_prefix}_locked"] = True
            st.session_state.selected_answers[q_key_prefix] = ordered_selection
            locked = True
        saved_seq = st.session_state.selected_answers.get(q_key_prefix, [])
        is_corr = (saved_seq == true_steps)
        corr_summary = " → ".join([f"({i+1}) {s}" for i, s in enumerate(true_steps)])
        user_summary = " → ".join([f"({i+1}) {s}" for i, s in enumerate(saved_seq)])
        return locked, is_corr, user_summary, corr_summary

    # 4. STANDARD MULTIPLE CHOICE (SINGLE ANSWER) OR TRUE/FALSE
    else:
        user_choice = st.radio("Select Best Answer Option:", q_item.get("options", ["A) Option A", "B) Option B"]), key=f"{q_key_prefix}_mcq", index=None)
        st.session_state.selected_answers[q_key_prefix] = user_choice
        has_ans = user_choice is not None
        corr_str = q_item.get("correct", "A")
        is_corr = bool(has_ans and user_choice.strip().upper().startswith(corr_str.strip().upper()))
        return has_ans, is_corr, (user_choice or "Skipped"), corr_str

def render_question_read_aloud_button(client, q_item: dict, q_id_str: str, voice_name: str):
    """Accessibility button that reads the question stem and all answer choices/steps aloud in the user's chosen voice."""
    if st.button(f"🔊 Read Question & Options Aloud ({voice_name} Voice)", key=f"read_q_{q_id_str}"):
        with st.spinner(f"Synthesizing accessibility read-aloud in {voice_name}'s voice..."):
            qf = q_item.get("q_format", "MCQ")
            if qf == "PATHWAY":
                opts_read = "The scrambled pathway steps to place in order are: " + ". ".join(q_item.get("scrambled_pathway", []))
            elif qf == "MATCHING":
                opts_read = "Match the following items: " + ", ".join([p.get("premise", "") for p in q_item.get("matching_pairs", [])])
            else:
                opts_read = "The answer options are: " + ". ".join(q_item.get("options", []))
            full_read_text = f"Question ({qf}): {q_item.get('question', '')}. {opts_read}"
            wav_b = synthesize_tutor_speech(client, full_read_text, voice_name=voice_name)
            if wav_b:
                st.session_state.question_tts_cache[q_id_str] = (wav_b, full_read_text)

    if q_id_str in st.session_state.question_tts_cache:
        wav_b, read_txt = st.session_state.question_tts_cache[q_id_str]
        render_vertex_audio_player(
            wav_b,
            player_id=f"q_tts_player_{q_id_str}",
            title=f"Accessibility Question Read-Aloud ({voice_name})",
            transcript_text=read_txt
        )

# ----------------------------------------------------
# 10. MAIN PORTAL HEADER & 8 NAVIGATION TABS
# ----------------------------------------------------
st.title("🩺 Vertex Anesthesia - Multimodal CRNA Board Prep Portal")
st.caption(
    f"Theme: {st.session_state.user_preferences['theme']} • "
    f"Persona: {st.session_state.user_preferences['persona']} ({st.session_state.user_preferences['voice']} Voice) • "
    f"MCQ, SATA, Matching & Pathway Ordering • Auto-Highlighting Source Viewer"
)

if not st.session_state.file_catalog and not st.session_state.custom_qbank_items:
    st.info("👋 Welcome to Vertex Anesthesia. Upload your course PDFs, PowerPoints, Textbook Chapters, or `.json` Question Banks in the left sidebar to unlock all 8 modules.")
else:
    primary_files, bg_files = get_scoped_files()
    all_active_refs = [f["cloud_ref"] for f in primary_files] + [f["cloud_ref"] for f in bg_files]
    primary_summary_str = ", ".join([f"{f['name']} ({f['course']} | {f['folder']} | {f['section']} | {f['asset_type']})" for f in primary_files]) or "Custom JSON Q-Bank"
    active_folder_label = f"{primary_files[0]['course']} | {primary_files[0]['folder']} | {primary_files[0]['section']}" if primary_files else "Custom JSON Q-Bank"
    active_asset_label = primary_files[0]["asset_type"] if len({f["asset_type"] for f in primary_files}) == 1 else "Combined Materials"

    tab_quiz, tab_notes_photo, tab_textbook, tab_reviews, tab_flashcards, tab_obj, tab_podcast, tab_metrics = st.tabs([
        "📝 Exams (MCQ, SATA, Matching, Pathway)",
        "📸 Interact With Notes & Photo Solver",
        "📖 Textbook 'Summarize This' & Highlighter",
        "📑 Review Sheets & 🚨 Hot Topics",
        "🗂️ Notability Spaced-Rep Flashcards",
        "🎯 Objectives & Hidden Gems",
        "🎙️ Karaoke Podcast & Topic Index",
        "📊 UWorld & PrepU Private Metrics"
    ])

    # ====================================================
    # TAB 1: EXAMS (MCQ, SATA, MATCHING, PATHWAY & CAT)
    # ====================================================
    with tab_quiz:
        st.subheader("📝 Multimodal Assessment Engine (MCQ, Select All That Apply, Matching & Pathway Ordering)")
        
        cfg_r1_c1, cfg_r1_c2, cfg_r1_c3 = st.columns(3)
        with cfg_r1_c1:
            blueprint_category = st.selectbox("1. Select Exam Blueprint / Source Category:", [
                "Board Simulation Exam (NBCRNA NCE Blueprint)",
                "SEE Simulation Exam (Self-Evaluation Blueprint)",
                "🚨 Hot Spot Questions (Verified Board Traps & High-Yield)",
                "Exams Based on Textbook Chapters",
                "🔄 Missed & 'I Don't Know' Questions Remediation",
                "🫀 Questions by Topic / Organ System",
                "🎲 Random Quiz (All Uploaded Materials & Custom JSON Q-Bank)"
            ])
        with cfg_r1_c2:
            exam_mode = st.selectbox("2. Execution Mode:", [
                "Practice Mode (Instant Rationale + Read-Aloud + 'I Don't Know' Coaching)",
                "NBCRNA Adaptive CAT Mode (Dynamic Difficulty Levels 1–8)",
                "Mock Board Exam (Timed Enforced Simulation)"
            ])
        with cfg_r1_c3:
            diff_choice = st.selectbox("3. Difficulty Calibration (PrepU/UWorld):", [
                "Adaptive Auto-Scale (Starts Level 4)",
                "Easy (Levels 1–3: Foundational Recall)",
                "Medium (Levels 4–5: Clinical Application)",
                "Hard (Levels 6–8: NBCRNA Synthesis)",
                "Mixed Board Blueprint (Levels 1–8)"
            ])

        cfg_r2_c1, cfg_r2_c2, cfg_r2_c3 = st.columns(3)
        with cfg_r2_c1:
            q_type = st.selectbox("4. Question Format:", [
                "High-Yield Multimodal Mix (MCQ + SATA + Matching + Pathway)",
                "Multiple Choice (Single Answer)",
                "Select All That Apply (SATA)",
                "Matching (Receptors, Drugs & Labs)",
                "Pathway Ordering (Physiology / Pathophysiology Sequence)"
            ])
        with cfg_r2_c2:
            q_count = st.slider("5. Number of Questions:", min_value=1, max_value=25, value=5)
        with cfg_r2_c3:
            target_organ_filter = None
            if blueprint_category == "🫀 Questions by Topic / Organ System":
                avail_s = sorted(list({f["section"] for f in st.session_state.file_catalog})) or ["Cardiac & Vascular"]
                target_organ_filter = st.selectbox("Select Target Organ System:", avail_s)
            elif st.session_state.custom_qbank_items:
                use_json_qbank = st.checkbox(f"Include Imported .JSON Q-Bank ({len(st.session_state.custom_qbank_items)} items)", value=True)
            else:
                use_json_qbank = False

        level_map = {
            "Adaptive Auto-Scale (Starts Level 4)": 4,
            "Easy (Levels 1–3: Foundational Recall)": 2,
            "Medium (Levels 4–5: Clinical Application)": 5,
            "Hard (Levels 6–8: NBCRNA Synthesis)": 7,
            "Mixed Board Blueprint (Levels 1–8)": 5
        }
        chosen_base_level = level_map.get(diff_choice, 4)

        if blueprint_category == "Exams Based on Textbook Chapters":
            scoped_prim, scoped_bg = get_scoped_files(override_type="Textbook Chapter")
        elif blueprint_category == "🫀 Questions by Topic / Organ System" and target_organ_filter:
            scoped_prim, scoped_bg = get_scoped_files(override_section=target_organ_filter)
        else:
            scoped_prim, scoped_bg = primary_files, bg_files
        exam_file_refs = [f["cloud_ref"] for f in scoped_prim] + [f["cloud_ref"] for f in scoped_bg]

        st.markdown("""
        <div class="honesty-banner">
            💡 <strong>Vertex Coaching Reminder:</strong> <em>"It's better to say if you don't know; be honest so I can help you!"</em> 
            Every question includes a <strong>🔊 Read Aloud</strong> button for accessibility, a <strong>📖 Highlighted Source Pop-Up Link</strong>, and hilarious meme/anatomical shoutouts!
        </div>
        """, unsafe_allow_html=True)

        # ---- PATH A: NBCRNA ADAPTIVE (CAT) MODE ----
        if exam_mode.startswith("NBCRNA Adaptive CAT"):
            cat = st.session_state.cat_state
            if st.button("🚀 Start / Reset NBCRNA Adaptive CAT Session"):
                cat["active"] = True
                cat["current_level"] = chosen_base_level
                cat["target_questions"] = q_count
                cat["history_levels"] = []
                st.session_state.generated_test = []
                st.session_state.selected_answers = {}
                st.session_state.question_hints = {}
                with st.spinner(f"Calibrating Adaptive Question 1 ({q_type}) at Level {cat['current_level']}/8..."):
                    new_qs = generate_structured_questions(
                        client, exam_file_refs, 1, q_type, blueprint_category,
                        f"NBCRNA Adaptive Level {cat['current_level']}/8", cat["current_level"],
                        st.session_state.personal_metrics["asked_questions_ledger"], primary_summary_str
                    )
                    if new_qs:
                        st.session_state.generated_test.append(new_qs[0])

            if cat["active"] and st.session_state.generated_test:
                if cat["history_levels"]:
                    st.markdown("##### 📈 Your Real-Time NBCRNA Adaptive Mastery Trajectory (Levels 1–8)")
                    st.line_chart(cat["history_levels"])

                curr_idx = len(st.session_state.generated_test) - 1
                q_item = st.session_state.generated_test[curr_idx]

                hot_badge = "<span class='uworld-badge' style='background:#fef2f2;color:#dc2626;border-color:#ef4444;'>🚨 CRNA ALERT 🚨</span>" if q_item.get("is_hot_topic") else ""
                st.markdown(
                    f"{hot_badge}"
                    f"<span class='uworld-badge'>⚡ CAT Item {curr_idx+1}/{cat['target_questions']} | {q_item.get('q_format', 'MCQ')} | Level {q_item['difficulty_level']}/8</span>"
                    f"<span class='source-badge'>📌 {q_item['domain']}</span>",
                    unsafe_allow_html=True
                )
                st.markdown(f"### Q{curr_idx+1}. {q_item['question']}")
                render_question_read_aloud_button(client, q_item, f"cat_{curr_idx}", tutor_voice_pref)

                has_ans, is_corr, user_ans_str, corr_ans_str = render_question_widget_and_evaluate(q_item, f"cat_w_{curr_idx}")

                if not q_item.get("logged"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        if st.button("✅ Submit Adaptive Response", key=f"sub_cat_{curr_idx}"):
                            if not has_ans:
                                st.warning("Please complete your selection or click 'I Don't Know'!")
                            else:
                                record_question_result(q_item, is_corr, active_folder_label, active_asset_label, honest_idk=False)
                                q_item["logged"] = True
                                q_item["is_corr"] = is_corr
                                q_item["user_ans_str"] = user_ans_str
                                q_item["corr_ans_str"] = corr_ans_str
                                cat["history_levels"].append(q_item["difficulty_level"])
                                cat["current_level"] = min(8, cat["current_level"] + 1) if is_corr else max(1, cat["current_level"] - 1)
                                st.rerun()
                    with c2:
                        if st.button("🤔 I Don't Know (Give Hint)", key=f"hint_cat_{curr_idx}"):
                            st.session_state.question_hints[f"cat_{curr_idx}"] = q_item.get("hint", "")
                    with c3:
                        if st.button("🏳️ I Don't Know (Be Honest & Teach Me)", key=f"idk_cat_{curr_idx}"):
                            record_question_result(q_item, False, active_folder_label, active_asset_label, honest_idk=True)
                            q_item["logged"] = True
                            q_item["is_corr"] = False
                            q_item["honest_idk"] = True
                            q_item["corr_ans_str"] = corr_ans_str
                            cat["history_levels"].append(q_item["difficulty_level"])
                            cat["current_level"] = max(1, cat["current_level"] - 1)
                            st.rerun()

                    if f"cat_{curr_idx}" in st.session_state.question_hints:
                        st.info(f"💡 **Clinical Hint:** {st.session_state.question_hints[f'cat_{curr_idx}']}")
                else:
                    if q_item.get("honest_idk"):
                        st.warning(f"🙌 **Thank you for being honest!** Flagged `{q_item['domain']}` for priority review. Correct Answer: **{q_item.get('corr_ans_str')}**")
                    elif q_item.get("is_corr"):
                        st.success(f"🎉 **CORRECT!** {q_item.get('celebration_line', '')}")
                    else:
                        st.error(f"❌ **Incorrect.** (Your Answer: `{q_item.get('user_ans_str')}` | Correct: `{q_item.get('corr_ans_str')}`)")

                    st.write(q_item["explanation"])
                    st.markdown(f"<div class='meme-box'><strong>🔥 Viral Meme & Pop-Culture Memory Anchor:</strong><br>{q_item['mnemonic']}</div>", unsafe_allow_html=True)

                    if st.button(f"📖 Open Source & Highlight Quote ({q_item['source']})", key=f"cat_src_{curr_idx}"):
                        open_source_highlighter_modal(q_item["source"], q_item.get("highlight_quote", ""))

                    render_contextual_tutor(
                        client=client,
                        active_file_refs=exam_file_refs,
                        context_id=f"cat_tutor_{curr_idx}",
                        context_summary=f"Question: {q_item['question']}\nExplanation: {q_item['explanation']}\nSource: {q_item['source']}",
                        button_label=f"💬 Explain Q{curr_idx+1} (Voice Read-Along + Source Link + Molecular Animation)",
                        voice_1=tutor_voice_pref
                    )

                    if curr_idx + 1 < cat["target_questions"]:
                        if st.button(f"➡️ Next Adaptive Question (Level {cat['current_level']}/8)"):
                            with st.spinner(f"Generating Adaptive Question {curr_idx+2} at Level {cat['current_level']}/8..."):
                                next_qs = generate_structured_questions(
                                    client, exam_file_refs, 1, q_type, blueprint_category,
                                    f"NBCRNA Adaptive Level {cat['current_level']}/8", cat["current_level"],
                                    st.session_state.personal_metrics["asked_questions_ledger"], primary_summary_str
                                )
                                if next_qs:
                                    st.session_state.generated_test.append(next_qs[0])
                                    st.rerun()

        # ---- PATH B: PRACTICE OR MOCK EXAM BATCH ----
        else:
            if st.button(f"⚡ Construct {q_count}-Question '{q_type.split(' ')[0]}' Assessment"):
                st.session_state.selected_answers = {}
                st.session_state.question_hints = {}
                st.session_state.submitted = False
                st.session_state.cat_state["active"] = False

                missed_history = [h for h in st.session_state.personal_metrics["history"] if not h["correct"] or h.get("honest_idk")]
                if blueprint_category == "🔄 Missed & 'I Don't Know' Questions Remediation" and not missed_history:
                    st.warning("No Missed or 'I Don't Know' items logged yet! Complete a quiz first.")
                else:
                    with st.spinner(f"Building {q_count} multimodal questions ({q_type}) with viral meme hooks and source highlight coordinates..."):
                        extra_inst = ""
                        if blueprint_category == "🔄 Missed & 'I Don't Know' Questions Remediation":
                            missed_digest = "\n".join([f"- {m['domain']}: {m['question']}" for m in missed_history[-15:]])
                            extra_inst = f"Test these exact missed concepts:\n{missed_digest}"
                        try:
                            assembled_qs = []
                            if use_json_qbank and st.session_state.custom_qbank_items:
                                sample_cnt = min(len(st.session_state.custom_qbank_items), max(1, q_count // 2))
                                assembled_qs.extend(random.sample(st.session_state.custom_qbank_items, sample_cnt))
                            rem_cnt = max(0, q_count - len(assembled_qs))
                            if rem_cnt > 0 and exam_file_refs:
                                gen_qs = generate_structured_questions(
                                    client, exam_file_refs, rem_cnt, q_type, blueprint_category,
                                    diff_choice, chosen_base_level,
                                    st.session_state.personal_metrics["asked_questions_ledger"],
                                    primary_summary_str, extra_inst
                                )
                                assembled_qs.extend(gen_qs)
                            st.session_state.generated_test = assembled_qs
                        except Exception as api_err:
                            st.error(f"Error generating questions: {api_err}")

            if st.session_state.generated_test and not st.session_state.cat_state.get("active"):
                st.header(f"Active Assessment: {blueprint_category}")
                for idx, q_item in enumerate(st.session_state.generated_test):
                    hot_badge = "<span class='uworld-badge' style='background:#fef2f2;color:#dc2626;border-color:#ef4444;'>🚨 CRNA ALERT 🚨</span>" if q_item.get("is_hot_topic") else ""
                    st.markdown(
                        f"{hot_badge}"
                        f"<span class='uworld-badge'>🧩 Format: {q_item.get('q_format', 'MCQ')} | Level {q_item.get('difficulty_level', 4)}/8 | Peer Avg: {q_item.get('peer_pct', 68)}%</span>"
                        f"<span class='source-badge'>📌 {q_item['domain']}</span>",
                        unsafe_allow_html=True
                    )
                    st.markdown(f"### Q{idx+1}. {q_item['question']}")
                    render_question_read_aloud_button(client, q_item, f"prac_{idx}", tutor_voice_pref)

                    has_ans, is_corr, user_ans_str, corr_ans_str = render_question_widget_and_evaluate(q_item, f"q_cloud_{idx}")

                    if exam_mode.startswith("Practice Mode"):
                        idk_c1, idk_c2 = st.columns(2)
                        with idk_c1:
                            if st.button(f"🤔 I Don't Know Q{idx+1}, Give Me a Clinical Hint (Be Honest!)", key=f"hint_btn_{idx}"):
                                st.session_state.question_hints[idx] = {"mode": "hint", "text": q_item.get("hint", "")}
                        with idk_c2:
                            if st.button(f"🏳️ I Don't Know Q{idx+1}, Reveal Answer & Log to Weak Areas", key=f"idk_reveal_{idx}"):
                                st.session_state.question_hints[idx] = {"mode": "reveal"}
                                if not q_item.get("logged"):
                                    record_question_result(q_item, False, active_folder_label, active_asset_label, honest_idk=True)
                                    q_item["logged"] = True
                                    q_item["honest_idk"] = True

                        hint_state = st.session_state.question_hints.get(idx)
                        if hint_state and hint_state.get("mode") == "hint":
                            st.info(f"💡 **Clinical Hint:** {hint_state['text']}")

                        show_rationale = has_ans or (hint_state and hint_state.get("mode") == "reveal")
                        if show_rationale:
                            if hint_state and hint_state.get("mode") == "reveal" and not has_ans:
                                st.warning(f"🙌 **Honesty Logged!** It's better to say if you don't know so I can help you! Correct Answer: **{corr_ans_str}**")
                            else:
                                if not q_item.get("logged"):
                                    record_question_result(q_item, is_corr, active_folder_label, active_asset_label, honest_idk=bool(hint_state))
                                    q_item["logged"] = True
                                if is_corr:
                                    st.success(f"🎉 **CORRECT!** {q_item.get('celebration_line', '')}")
                                else:
                                    st.error(f"❌ **Incorrect** (Your Selection: `{user_ans_str}` | Correct: `{corr_ans_str}`)")

                            with st.expander("📚 View Multimodal Rationale, Meme Anchor & Highlighted Source Link", expanded=True):
                                st.write(q_item["explanation"])
                                st.markdown(f"<div class='meme-box'><strong>🔥 Viral Meme / Pop-Culture Hook & Mnemonic:</strong><br>{q_item['mnemonic']}</div>", unsafe_allow_html=True)
                                st.markdown(f"<span class='source-badge'>📍 Source: {q_item['source']}</span>", unsafe_allow_html=True)
                                if st.button(f"📖 Open Source & Highlight Quote ({q_item['source']})", key=f"open_src_q_{idx}"):
                                    open_source_highlighter_modal(q_item["source"], q_item.get("highlight_quote", ""))

                            check_podcast_cross_reference(f"{q_item['question']} {q_item['explanation']}", key_prefix=f"q_pod_{idx}")

                            render_contextual_tutor(
                                client=client,
                                active_file_refs=exam_file_refs,
                                context_id=f"quiz_q_{idx}",
                                context_summary=f"Question: {q_item['question']}\nCorrect: {corr_ans_str}\nExplanation: {q_item['explanation']}\nSource: {q_item['source']}",
                                button_label=f"💬 Explain Q{idx+1} With Read-Along Voice, Memes, Source Link & Animated Receptors",
                                voice_1=tutor_voice_pref
                            )
                    st.markdown("---")

    # ====================================================
    # TAB 2: INTERACT WITH MY NOTES, SECTION MIC CHAT & PHOTO SOLVER
    # ====================================================
    with tab_notes_photo:
        st.subheader("📸 Photo Question Snap Solver, 'Interact With My Notes' & Section Voice Chat")
        sub_t1, sub_t2 = st.tabs([
            "📸 Snap / Upload Photo of Any Question (Instant Answer First!)",
            "🗒️ 'Interact With My Notes' & Persistent Section Voice/Text Chat"
        ])

        with sub_t1:
            st.write(
                "Take a picture or upload a screenshot of a multiple-choice question from another platform or worksheet. "
                "Vertex Vision will read the question and options and **state the exact correct answer first on Line 1**, "
                "followed by the rationale, meme mnemonic, and source link!"
            )
            p_col1, p_col2 = st.columns(2)
            with p_col1:
                uploaded_q_img = st.file_uploader("Upload Question Screenshot / Photo (.png, .jpg, .jpeg, .webp):", type=["png", "jpg", "jpeg", "webp"])
            with p_col2:
                cam_q_img = st.camera_input("Or Take a Live Photo of a Screen / Page:") if hasattr(st, "camera_input") else None

            active_img_file = cam_q_img if cam_q_img is not None else uploaded_q_img
            if active_img_file is not None:
                st.image(active_img_file, caption="Uploaded Question Image", width=450)
                if st.button("⚡ Recognize Question from Photo & Give Correct Answer First"):
                    with st.spinner("Reading question and multiple-choice options from image..."):
                        img_bytes = active_img_file.getvalue()
                        mime_t = active_img_file.type if hasattr(active_img_file, "type") and active_img_file.type else "image/png"
                        img_part = types.Part.from_bytes(data=img_bytes, mime_type=mime_t)
                        photo_prompt = f"""
                        {get_active_persona_instruction()}
                        Read the question and answer choices in the attached image carefully.
                        CRITICAL RULE 1: Your VERY FIRST sentence MUST state ONLY the correct answer letter and full option text in bold, formatted exactly like this:
                        "🎯 **The correct answer is: [Letter]. [Exact Option Text]**"
                        CRITICAL RULE 2: Below that first line, provide:
                        - **OCR Recognized Question & Options** (so the student can verify what was read)
                        - **Step-by-Step Clinical Rationale** (grounded in the uploaded course files if applicable, citing `[Filename, Page/Slide X]`)
                        - **🔥 Viral Meme / Pop-Culture Memory Hook**
                        """
                        res = client.models.generate_content(
                            model="gemini-3.1-pro-preview",
                            contents=all_active_refs + [img_part, photo_prompt]
                        )
                        st.session_state.photo_solver_result = res.text

            if st.session_state.photo_solver_result:
                st.markdown("---")
                st.markdown(st.session_state.photo_solver_result, unsafe_allow_html=True)

        with sub_t2:
            st.write("Consult your entire note vault (**Interact With My Notes**) or keep a persistent voice/text chat for a specific course section so you can reference back to everything you discussed!")
            available_scopes = ["🌐 All Uploaded Notes ('Interact With My Notes' Global Mode)"] + sorted(list({f"{f['course']} — {f['section']} ({f['folder']})" for f in st.session_state.file_catalog}))
            chosen_chat_scope = st.selectbox("Select Persistent Chat Notebook Scope:", available_scopes)

            if chosen_chat_scope not in st.session_state.section_chats:
                st.session_state.section_chats[chosen_chat_scope] = []

            render_contextual_tutor(
                client=client,
                active_file_refs=all_active_refs,
                context_id=f"sec_chat_{chosen_chat_scope}",
                context_summary=f"Persistent Section Notebook Chat for: {chosen_chat_scope}. Files: {primary_summary_str}",
                button_label=f"🎤 Open Persistent Voice & Text Notebook Chat: {chosen_chat_scope}",
                voice_1=tutor_voice_pref
            )

    # ====================================================
    # TAB 3: TEXTBOOK "SUMMARIZE THIS" & SOURCE HIGHLIGHTER
    # ====================================================
    with tab_textbook:
        st.subheader("📖 Textbook 'Summarize This' Engine (Objectives + Beyond-the-Summary 🚨 CRNA Alerts)")
        st.write(
            "Synthesizes uploaded textbook chapters or lecture PDFs by covering every major objective and chapter summary point—**without copying and pasting**—while "
            "digging into the body pages of the book to pull out additional board-critical details (`🚨 CRNA ALERT 🚨`) with clickable **Page Highlighting Links**!"
        )

        if st.button("📚 Summarize Textbook & Lecture Materials (With Page Links & 🚨 CRNA Alerts)"):
            with st.spinner("Scanning full textbook pages, cross-checking lecture objectives, and extracting page-referenced quotes..."):
                tb_prompt = f"""
                You are an elite CRNA Textbook Author and Board Review Editor for Vertex Anesthesia.
                {get_active_persona_instruction()}
                {NBCRNA_BLUEPRINT_GROUNDING}

                Create a structured, high-yield **"Summarize This" Master Outline** from the active files ({primary_summary_str}).
                CRITICAL RULES:
                1. DO NOT merely copy-and-paste the textbook's end-of-chapter summary! Synthesize the major topics aligned with the lecture objectives AND scan the deep body pages of the chapter for crucial clinical mechanisms, board traps, drug doses, or physiological pathways that the end-of-chapter summary glossed over.
                2. Flag every board-critical concept with **🚨 CRNA ALERT 🚨** and explain why the SEE/NBCRNA tests it.
                3. Include a funny viral meme / pop-culture mnemonic (like Kidz Bop Karen 'Calci-Calm-It-Down') for each major section.
                4. Return ONLY valid JSON matching this structure so we can attach clickable PDF Page Auto-Highlighter buttons to every section:
                {{
                  "chapter_title": "Title of Textbook Chapter / Module",
                  "executive_overview": "High-level synthesis paragraph",
                  "sections": [
                    {{
                      "heading": "Section Title (Include 🚨 CRNA ALERT 🚨 if board hot topic)",
                      "key_points_markdown": "Rich bulleted outline with bold highlights, colored HTML spans, and additional deep-page book pearls not found in basic summaries.",
                      "viral_meme_anchor": "Funny pop-culture/meme story or mnemonic",
                      "source_file": "Exact filename",
                      "page_number": 1,
                      "highlight_quote": "Exact 4 to 10 word verbatim phrase from that page to highlight in the pop-up viewer"
                    }}
                  ]
                }}
                """
                try:
                    res = client.models.generate_content(
                        model="gemini-3.1-pro-preview",
                        contents=all_active_refs + [tb_prompt],
                        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2)
                    )
                    st.session_state.textbook_summary_report = json.loads(res.text)
                except Exception as e:
                    st.error(f"Error generating Textbook Summary: {e}")

        if st.session_state.textbook_summary_report:
            t_rep = st.session_state.textbook_summary_report
            st.markdown(f"### 📘 {t_rep.get('chapter_title', 'Textbook Master Synthesis')}")
            st.info(t_rep.get("executive_overview", ""))

            for s_idx, sec in enumerate(t_rep.get("sections", [])):
                st.markdown(f"#### {sec.get('heading', '')}")
                st.markdown(sec.get("key_points_markdown", ""), unsafe_allow_html=True)
                if sec.get("viral_meme_anchor"):
                    st.markdown(f"<div class='meme-box'><strong>🔥 Meme / Memory Anchor:</strong> {sec.get('viral_meme_anchor')}</div>", unsafe_allow_html=True)
                src_label = f"{sec.get('source_file', 'Textbook')}, Page {sec.get('page_number', 1)}"
                if st.button(f"📖 Open Textbook Page {sec.get('page_number', 1)} & Highlight Passage ({sec.get('source_file', '')})", key=f"tb_hl_{s_idx}"):
                    open_source_highlighter_modal(src_label, sec.get("highlight_quote", ""))
                st.markdown("---")

    # ====================================================
    # TAB 4: PHOTOGRAPHIC MEMORY REVIEW SHEETS & 🚨 HOT TOPICS
    # ====================================================
    with tab_reviews:
        st.subheader("📑 Photographic Memory Review Sheet Generator & 🚨 Verified NBCRNA/SEE Hot Topics")
        rev_mode = st.radio("Select Review Sheet Blueprint:", [
            "📚 Full Comprehensive Review Sheet (All Selected Source Materials)",
            "🚨 Verified NBCRNA / SEE Board Hot-Topics Review Sheet (Evidence-Backed Blueprint)",
            "🎯 Personalized Weak-Areas Quick Review Sheet (1 to 5 Pages Based on My Metrics)"
        ])

        total_interactions = (
            len(st.session_state.personal_metrics["history"])
            + st.session_state.personal_metrics.get("verbal_interactions_count", 0)
        )

        target_pages = 2
        if rev_mode.startswith("🎯 Personalized Weak-Areas"):
            st.caption("⚠️ **Note:** This 1 to 5 page Quick Review Sheet highlights top priority weak spots and is not an exhaustive list of all weak areas.")
            target_pages = st.slider("Select Length of Your Weak-Areas Quick Review Sheet (Pages):", min_value=1, max_value=5, value=2)
            st.info(f"📊 **Current Logged Psychometric Data Points:** `{total_interactions}` (Minimum `5` required)")

        if st.button("🎨 Generate Color-Coded Photographic Memory Review Sheet"):
            if rev_mode.startswith("🎯 Personalized Weak-Areas") and total_interactions < 5:
                show_insufficient_data_modal(current_count=total_interactions, required_count=5)
            else:
                with st.spinner("Designing color-coded, emoji-rich Photographic Memory Review Sheet with viral memes & 🚨 CRNA Alerts..."):
                    weak_records = [h for h in st.session_state.personal_metrics["history"] if not h["correct"] or h.get("honest_idk")]
                    weak_summary = "\n".join([f"- {w['domain']}: {w['question']} ({w['source']})" for w in weak_records[-25:]])
                    review_prompt = f"""
                    You are an elite CRNA Visual Curriculum Designer for Vertex Anesthesia.
                    {get_active_persona_instruction()}
                    {NBCRNA_BLUEPRINT_GROUNDING}
                    Selected Mode: {rev_mode} (Target Pages if Quick Sheet: {target_pages} pages; Weak spots: {weak_summary}).
                    Use rich HTML highlights (`<mark style='background:#fef08a;padding:2px 6px;font-weight:bold;'>...`), colored bold spans, emojis, viral meme stories (like Kidz Bop Karen 'Calci-Calm-It-Down'), and exact `[Filename, Page/Slide X]` citations!
                    """
                    res = client.models.generate_content(
                        model="gemini-3.1-pro-preview",
                        contents=all_active_refs + [review_prompt],
                        config=types.GenerateContentConfig(temperature=0.2)
                    )
                    st.session_state.review_sheet_output = res.text

        if st.session_state.review_sheet_output:
            st.download_button(
                label="⬇️ Download Color-Coded Review Sheet (.html)",
                data=f"<html><body style='font-family:sans-serif; line-height:1.6; padding:24px;'>{st.session_state.review_sheet_output}</body></html>",
                file_name="Vertex_Anesthesia_Review_Sheet.html",
                mime="text/html"
            )
            st.markdown(st.session_state.review_sheet_output, unsafe_allow_html=True)

    # ====================================================
    # TAB 5: NOTABILITY 4-TIER SPACED REPETITION FLASHCARDS
    # ====================================================
    with tab_flashcards:
        st.subheader("🗂️ Notability-Style 4-Tier Spaced Repetition Flashcards & Deck-to-Exam Converter")
        fc_col1, fc_col2 = st.columns([2, 1])
        with fc_col1:
            fc_focus = st.text_input("Optional Flashcard Focus:", placeholder="e.g., Neuromuscular blockers, FENa, and receptor subtypes")
        with fc_col2:
            fc_count = st.slider("Cards to Generate in Burst:", min_value=4, max_value=20, value=8)

        if st.button("🃏 Generate Spaced-Repetition Flashcard Burst"):
            with st.spinner("Extracting high-yield concepts and viral meme hooks into flashcards..."):
                fc_prompt = f"""
                Create {fc_count} high-yield CRNA board-prep flashcards from the active course files ({primary_summary_str}).
                {get_active_persona_instruction()}
                Focus: {fc_focus if fc_focus else 'Core mechanisms, receptor pathways, lab values, and board traps'}.
                Return ONLY valid JSON as a list of objects:
                [{{"front": "...", "back": "... [Filename, Page X]", "mnemonic": "Viral meme / pop-culture hook", "domain": "NBCRNA Domain"}}]
                """
                try:
                    res = client.models.generate_content(
                        model="gemini-2.5-pro",
                        contents=all_active_refs + [fc_prompt],
                        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.25)
                    )
                    new_cards = json.loads(res.text)
                    base_idx = len(st.session_state.flashcard_deck)
                    for i, c in enumerate(new_cards):
                        card_id = base_idx + i
                        st.session_state.flashcard_deck.append({
                            "id": card_id,
                            "front": c.get("front", ""),
                            "back": c.get("back", ""),
                            "mnemonic": c.get("mnemonic", ""),
                            "domain": c.get("domain", "Core Science"),
                            "folder_tag": active_folder_label,
                            "status": "New"
                        })
                        st.session_state.fc_queue.append(card_id)
                    st.session_state.fc_flipped = False
                    st.success(f"Added {len(new_cards)} flashcards to your active Spaced Repetition Queue!")
                except Exception as e:
                    st.error(f"Error generating flashcards: {e}")

        if st.session_state.flashcard_deck:
            deck = st.session_state.flashcard_deck
            if not st.session_state.fc_queue:
                if st.button("🔁 Refill Queue With Cards Needing Review"):
                    st.session_state.fc_queue = [c["id"] for c in deck if c["status"] != "Easy (Double Green)"] or [c["id"] for c in deck]
                    st.rerun()
            else:
                active_card_id = st.session_state.fc_queue[0]
                card = next((c for c in deck if c["id"] == active_card_id), deck[0])
                if not st.session_state.fc_flipped:
                    st.markdown(f"<div class='flashcard-box'><h4 style='color:#a855f7;'>FRONT</h4><h3>{card['front']}</h3></div>", unsafe_allow_html=True)
                    if st.button("🔄 Flip Card"):
                        st.session_state.fc_flipped = True
                        st.rerun()
                else:
                    st.markdown(f"<div class='flashcard-box'><h4 style='color:#22c55e;'>ANSWER</h4><p>{card['back']}</p><hr><p style='color:#f472b6;'>🔥 Meme Hook: {card['mnemonic']}</p></div>", unsafe_allow_html=True)
                    b_col1, b_col2, b_col3, b_col4 = st.columns(4)

                    def schedule_card(new_status: str, reinsert_offset: int, log_weak: bool):
                        card["status"] = new_status
                        st.session_state.fc_queue.pop(0)
                        if reinsert_offset is not None:
                            st.session_state.fc_queue.insert(min(reinsert_offset, len(st.session_state.fc_queue)), card["id"])
                        record_question_result(
                            {"domain": card["domain"], "difficulty_level": 4, "question": f"Flashcard", "source": card["back"][:80]},
                            is_correct=(not log_weak), folder_tag=card.get("folder_tag", active_folder_label),
                            asset_type_tag="Flashcard Spaced Repetition", honest_idk=log_weak
                        )
                        st.session_state.fc_flipped = False

                    with b_col1:
                        if st.button("🔄 Again (+2 cards)", key=f"fc_a_{card['id']}"):
                            schedule_card("Again (Immediate)", 2, True)
                            st.rerun()
                    with b_col2:
                        if st.button("❌ Red X (+4 cards)", key=f"fc_r_{card['id']}"):
                            schedule_card("Need Review (Red X)", 4, True)
                            st.rerun()
                    with b_col3:
                        if st.button("🟠 Orange Check (+8 cards)", key=f"fc_o_{card['id']}"):
                            schedule_card("Good (Orange Check)", 8, False)
                            st.rerun()
                    with b_col4:
                        if st.button("✅✅ Double Green (Mastered)", key=f"fc_g_{card['id']}"):
                            schedule_card("Easy (Double Green)", None, False)
                            st.rerun()

            if st.button("⚡ Build Practice Exam From My Flashcards (Opens in Tab 1)"):
                cards_digest = "\n".join([f"- {c['domain']}: {c['front']} -> {c['back']}" for c in deck[:12]])
                st.session_state.generated_test = generate_structured_questions(
                    client, all_active_refs, min(8, len(deck)), "High-Yield Multimodal Mix (MCQ + SATA + Matching + Pathway)",
                    "Flashcard Mastery Exam", "Medium", 5, [], primary_summary_str, f"Test these flashcards:\n{cards_digest}"
                )
                st.success("✅ Exam created! Click Tab 1 to take it.")

    # ====================================================
    # TAB 6: OBJECTIVES SOLVER & UNLISTED SLIDE AUDITOR
    # ====================================================
    with tab_obj:
        st.subheader("🎯 Comprehensive Objective Solver & Unlisted Slide Auditor")
        custom_objectives = st.text_area("Optional: Paste syllabus objectives here (leave blank to auto-detect from slides):")
        if st.button("📖 Answer Objectives & Audit Unlisted Slides"):
            with st.spinner("Synthesizing objectives, viral meme anchors, and auditing unlisted slides..."):
                obj_prompt = f"""
                {get_active_persona_instruction()}
                {NBCRNA_BLUEPRINT_GROUNDING}
                User objectives: {custom_objectives if custom_objectives.strip() else 'Auto-detect all objectives from the uploaded files.'}
                Deliver PART 1 (Complete answers to every objective with `[Filename, Page/Slide X]` citations, 🚨 CRNA ALERT 🚨 badges, and viral meme mnemonics)
                and PART 2 (⚠️ IN THE SLIDES, BUT NOT IN THE OBJECTIVES — audit every slide/diagram not covered by the objectives and give its SEE/NBCRNA Board Relevance Verdict).
                """
                res = client.models.generate_content(model="gemini-2.5-pro", contents=all_active_refs + [obj_prompt])
                st.session_state.objectives_report = res.text

        if st.session_state.objectives_report:
            st.markdown(st.session_state.objectives_report, unsafe_allow_html=True)

    # ====================================================
    # TAB 7: KARAOKE PODCAST STUDIO, TRANSCRIPT & TOPIC INDEX
    # ====================================================
    with tab_podcast:
        st.subheader("🎙️ Vertex Karaoke Podcast Studio (Word-by-Word Highlighting, Click-to-Seek & Topic Index)")
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            host1_voice = st.selectbox("Host 1 (Alex) Voice:", ["Puck", "Orus", "Fenrir", "Charon"], index=0)
        with col_p2:
            host2_voice = st.selectbox("Host 2 (Sam - Meme & Persona Co-Host) Voice:", ["Kore", "Aoede", "Leda", "Zephyr", "Charon"], index=0)
        with col_p3:
            podcast_focus = st.text_input("Optional Topic Focus:", placeholder="e.g., Urinary Tract Infections, FENa, and Renal Pathophysiology")

        if st.button("🎧 Generate Smooth NotebookLM Podcast, Karaoke Transcript & Topic Index"):
            with st.spinner("Step 1/2: Writing smooth, mnemonic-packed podcast script and indexing pathophysiology subtopics..."):
                podcast_schema_prompt = f"""
                Create a smooth, vivid, NotebookLM-style podcast episode between Alex and Sam reviewing {primary_summary_str}.
                {get_active_persona_instruction()}
                {NBCRNA_BLUEPRINT_GROUNDING}
                Focus: {podcast_focus if podcast_focus else 'All major topics and pathophysiology pathways in the uploaded files'}.
                Include hilarious viral memes (like 'Calci-Calm-It-Down') and vivid mental pictures!

                Return ONLY valid JSON matching this exact structure:
                {{
                  "title": "Episode Title",
                  "full_tts_script": "Alex: ...\\nSam: ...",
                  "mnemonics_summary": "Bulleted list of all mnemonics and viral memes created in this episode",
                  "segments": [
                    {{
                      "segment_title": "Major Topic (e.g., Urinary Tract Infections)",
                      "subtopics": ["Pathophysiology 1 (e.g., Ascending E. coli colonization)", "Pathophysiology 2 (e.g., Urosepsis & Intrarenal AKI)"],
                      "start_pct": 0.0,
                      "dialogue_excerpt": "Exact transcript spoken during this chapter...",
                      "source_file": "Exact filename",
                      "page_number": 1,
                      "highlight_quote": "Verbatim 4 to 10 word quote from the slide/page",
                      "zoom_box": [10, 10, 90, 90],
                      "annotations": [
                        {{"type": "arrow", "x": 45, "y": 55, "radius": 12, "label": "Key Mechanism"}}
                      ],
                      "cartoon_scene": "Vivid description of the meme/cartoon scene"
                    }}
                  ]
                }}
                """
                try:
                    script_res = client.models.generate_content(
                        model="gemini-3.1-pro-preview",
                        contents=all_active_refs + [podcast_schema_prompt],
                        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.3)
                    )
                    pdata = json.loads(script_res.text)
                    st.session_state.podcast_data = pdata
                    # Build cross-app searchable topic index
                    segs = pdata.get("segments", [])
                    total_s = max(1, len(segs))
                    idx_list = []
                    for i, s in enumerate(segs):
                        calc_pct = float(s.get("start_pct", (i / total_s) * 100.0))
                        s["start_pct"] = calc_pct
                        idx_list.append({
                            "topic": s.get("segment_title", f"Topic {i+1}"),
                            "subtopics": s.get("subtopics", []),
                            "start_pct": calc_pct,
                            "segment_idx": i,
                            "lecture_name": active_folder_label,
                            "dialogue_excerpt": s.get("dialogue_excerpt", ""),
                            "summary": s.get("cartoon_scene", "")
                        })
                    st.session_state.podcast_topic_index = idx_list
                except Exception as e:
                    st.error(f"Error generating podcast: {e}")
                    st.session_state.podcast_data = None

            if st.session_state.podcast_data:
                with st.spinner("Step 2/2: Synthesizing Multi-Speaker Gemini Studio Audio..."):
                    st.session_state.podcast_audio = synthesize_tutor_speech(
                        client,
                        f"TTS the following podcast conversation between Alex and Sam:\n\n{st.session_state.podcast_data['full_tts_script']}",
                        voice_name=host2_voice,
                        multi_speaker=True,
                        host2_voice=host1_voice
                    )

        if st.session_state.podcast_data:
            pdata = st.session_state.podcast_data
            st.markdown(f"### 🎙️ Now Playing: *{pdata.get('title', 'Vertex Anesthesia Deep-Dive')}*")

            # Downloadable Full Transcript & Mnemonics Sheet
            full_download_txt = (
                f"VERTEX ANESTHESIA PODCAST TRANSCRIPT & MNEMONICS\n"
                f"Episode: {pdata.get('title', '')}\n\n"
                f"=== MNEMONICS & VIRAL MEME ANCHORS ===\n{pdata.get('mnemonics_summary', '')}\n\n"
                f"=== FULL WORD-FOR-WORD TRANSCRIPT ===\n{pdata.get('full_tts_script', '')}"
            )
            st.download_button(
                label="⬇️ Download Full Podcast Transcript & Mnemonics (.txt)",
                data=full_download_txt,
                file_name="Vertex_Anesthesia_Podcast_Transcript.txt",
                mime="text/plain"
            )

            # Indexed Topic & Pathophysiology Jump Bar
            st.markdown("#### 🗂️ Indexed Podcast Topics & Pathophysiology Jump-To Menu")
            selected_jump_pct = 0.0
            t_cols = st.columns(max(1, len(pdata.get("segments", []))))
            for s_i, seg in enumerate(pdata.get("segments", [])):
                with t_cols[s_i]:
                    st.markdown(f"**{s_i+1}. {seg.get('segment_title')}**")
                    for sub in seg.get("subtopics", []):
                        st.caption(f"• {sub}")
                    if st.button(f"⏭️ Jump Audio to Topic {s_i+1}", key=f"jmp_pod_{s_i}"):
                        selected_jump_pct = float(seg.get("start_pct", (s_i / max(1, len(pdata["segments"]))) * 100.0))

            if st.session_state.podcast_audio:
                render_vertex_audio_player(
                    st.session_state.podcast_audio,
                    player_id="main_karaoke_podcast",
                    title=pdata.get("title", "Vertex Karaoke Podcast (Click Any Word Below to Skip Audio!)"),
                    transcript_text=pdata.get("full_tts_script", ""),
                    start_pct=selected_jump_pct
                )

            render_contextual_tutor(
                client=client,
                active_file_refs=all_active_refs,
                context_id="podcast_global_intervention",
                context_summary=pdata.get("full_tts_script", ""),
                button_label="✋🎤 Raise Hand & Intervene in Podcast (Hosts Pause, Answer You & Animate Receptors)",
                is_podcast_intervention=True,
                voice_1=host2_voice,
                voice_2=host1_voice
            )

            st.markdown("#### 🖼️ Synchronized Visual Chalkboard & Chapter Transcripts")
            for s_idx, seg in enumerate(pdata.get("segments", [])):
                with st.container():
                    st.markdown(f"#### Chapter {s_idx+1}: {seg.get('segment_title', '')} (`{seg.get('source_file', 'Deck')}` - Page {seg.get('page_number', 1)})")
                    v_col1, v_col2 = st.columns([1, 1])
                    with v_col1:
                        st.info(seg.get("dialogue_excerpt", ""))
                        st.markdown(f"<div class='meme-box'><strong>🎨 Cartoon / Meme Storyboard:</strong><br>{seg.get('cartoon_scene', '')}</div>", unsafe_allow_html=True)
                        if st.button(f"📖 Open Source Page {seg.get('page_number', 1)} & Highlight Text", key=f"pod_hl_{s_idx}"):
                            open_source_highlighter_modal(f"{seg.get('source_file', '')} Page {seg.get('page_number', 1)}", seg.get("highlight_quote", ""))
                    with v_col2:
                        if PYMUPDF_AVAILABLE and st.session_state.raw_pdf_bytes:
                            target_pdf_name = seg.get("source_file", "")
                            pdf_bytes = st.session_state.raw_pdf_bytes.get(target_pdf_name) or next(iter(st.session_state.raw_pdf_bytes.values()))
                            try:
                                marked_img = render_annotated_slide(
                                    pdf_bytes, int(seg.get("page_number", 1)),
                                    seg.get("annotations", []), seg.get("zoom_box", [5, 5, 95, 95])
                                )
                                st.image(marked_img, caption=f"Marked-Up Slide {seg.get('page_number', 1)}", use_container_width=True)
                            except Exception:
                                pass
                    st.markdown("---")

    # ====================================================
    # TAB 8: UWORLD & PREPU PRIVATE KNOWLEDGE METRICS
    # ====================================================
    with tab_metrics:
        st.subheader(f"📊 {student_alias}'s Private UWorld & PrepU Psychometric Analytics")
        metrics = st.session_state.personal_metrics
        stats = metrics["domain_stats"]
        f_stats = metrics.get("folder_stats", {})
        history = metrics["history"]

        if not history:
            st.info("Complete practice questions, SATA/Matching/Pathway items, or flashcards to populate your UWorld/PrepU analytics dashboard!")
        else:
            total_q = len(history)
            total_c = sum(1 for h in history if h["correct"])
            total_idk = sum(1 for h in history if h.get("honest_idk"))
            overall_pct = (total_c / total_q) * 100

            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            m_col1.metric("Total Items Logged", total_q)
            m_col2.metric("Overall Accuracy", f"{overall_pct:.1f}%")
            m_col3.metric("Honest 'I Don't Know' Flags", total_idk)
            weakest_domain = min(stats.items(), key=lambda x: (x[1]["correct"] / max(1, x[1]["total"])))[0]
            m_col4.metric("Priority Weak Domain", weakest_domain)

            st.markdown("#### 📂 Practice Volume & Accuracy by Course, Exam Folder & Organ System")
            for f_name, f_val in f_stats.items():
                f_pct = (f_val["correct"] / max(1, f_val["total"])) * 100
                st.write(f"📁 **{f_name}** — `{f_val['total']} Questions Answered` | **{f_val['correct']}/{f_val['total']} ({f_pct:.0f}%)**")
                st.progress(int(f_pct))

            st.markdown("#### 🩺 NBCRNA Domain Breakdown & PrepU Level (1–8)")
            for dom, d_val in stats.items():
                dom_pct = (d_val["correct"] / max(1, d_val["total"])) * 100
                lvls = d_val.get("levels", [4])
                dom_lvl = sum(lvls) / max(1, len(lvls))
                st.write(f"**{dom}** — {d_val['correct']}/{d_val['total']} ({dom_pct:.0f}%) | **Honest IDK: {d_val.get('idk_count', 0)}** | **Avg Level: {dom_lvl:.1f}/8**")
                st.progress(int(dom_pct))

        st.markdown("---")
        v_col1, v_col2 = st.columns(2)
        with v_col1:
            export_bundle = {
                "user_preferences": st.session_state.user_preferences,
                "personal_metrics": st.session_state.personal_metrics,
                "flashcard_deck": st.session_state.flashcard_deck,
                "custom_qbank_items": st.session_state.custom_qbank_items
            }
            st.download_button(
                label="⬇️ Download My Private Vertex Vault (.json)",
                data=json.dumps(export_bundle, indent=2),
                file_name=f"Vertex_Anesthesia_Vault_{student_alias.replace(' ', '_')}.json",
                mime="application/json"
            )
        with v_col2:
            uploaded_vault = st.file_uploader("⬆️ Restore Previous Personal Vault (.json)", type=["json"], key="vault_restore_up")
            if uploaded_vault is not None:
                try:
                    loaded_data = json.load(uploaded_vault)
                    if "personal_metrics" in loaded_data:
                        st.session_state.personal_metrics = loaded_data["personal_metrics"]
                        st.session_state.flashcard_deck = loaded_data.get("flashcard_deck", [])
                        st.session_state.custom_qbank_items = loaded_data.get("custom_qbank_items", [])
                        if "user_preferences" in loaded_data:
                            st.session_state.user_preferences.update(loaded_data["user_preferences"])
                        st.success("Personal Vertex Anesthesia Vault restored!")
                except Exception:
                    st.error("Invalid vault file.")
