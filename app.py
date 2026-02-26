import streamlit as st
import os
import base64
from dotenv import load_dotenv
from openai import OpenAI

# -------------------------
# CONFIG
# -------------------------

load_dotenv()
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
st.set_page_config(page_title="Professional Salon AI", layout="centered")

# -------------------------
# BRAND KNOWLEDGE BASE
# -------------------------

BRAND_KNOWLEDGE = """
Major Hair Brands FAQ Knowledge:

Dove:
- Focus: moisture, gentle care
- Known for sulfate-balanced shampoos
- Good for dry or damaged hair

L’Oréal:
- Professional salon science
- Keratin, bond repair, color protection
- Targets advanced hair repair

Head & Shoulders:
- Anti-dandruff specialist
- Scalp treatment focus
- Zinc-based formulas

Aussie:
- Botanical extracts
- Volume & hydration lines
- Youthful, fruity positioning

Herbal Essences:
- Plant-based ingredients
- Paraben-free ranges
- Natural positioning

TRESemmé:
- Salon performance at drugstore price
- Keratin smooth
- Heat protection products

Sephora (Hair Category):
- Premium & luxury hair brands
- High-end treatments
- Professional styling lines

Our Professional Solutions:

Formula Exclusiva:
- Deep repair
- Advanced smoothing
- Professional restoration

Laciador:
- Straightening & smoothing
- Frizz control
- Long-lasting sleek finish

Gotero:
- Scalp & growth treatment
- Targeted hair strengthening

Gotika:
- Intensive hydration
- Luxury conditioning treatment
"""

# -------------------------
# LANGUAGE OPTIONS
# -------------------------

languages = {
    "English": "Respond in English.",
    "Spanish": "Respond in Spanish.",
    "French": "Respond in French.",
    "Arabic": "Respond in Modern Standard Arabic."
}

# -------------------------
# UI STYLE
# -------------------------

st.markdown("""
<style>
body { background-color: #0c0c0c; }

.stApp {
    background: radial-gradient(circle at center, #1a1a1a 0%, #0c0c0c 70%);
    color: white;
    text-align: center;
}

.halo-button {
    margin-top: 30px;
    margin-bottom: 20px;
}

button[kind="primary"] {
    background-color: #d4af37;
    color: black;
    font-weight: bold;
    border-radius: 50%;
    height: 120px;
    width: 120px;
    font-size: 18px;
}

.product-box {
    border: 1px solid #444;
    padding: 15px;
    margin: 10px;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

# -------------------------
# HEADER
# -------------------------

st.title("Luxury Professional Salon AI")
st.caption("Expert Hair Guidance. Intelligent Comparison.")

# -------------------------
# LANGUAGE SELECT
# -------------------------

selected_language = st.selectbox("🌍 Select Language", list(languages.keys()))
language_instruction = languages[selected_language]

# -------------------------
# PRODUCT INTRO SECTION
# -------------------------

st.subheader("Our Professional Solutions")

st.markdown("""
<div class="product-box">
<b>Formula Exclusiva</b> – Deep repair & professional restoration.
</div>

<div class="product-box">
<b>Laciador</b> – Advanced smoothing & frizz control.
</div>

<div class="product-box">
<b>Gotero</b> – Scalp strengthening & growth-focused care.
</div>

<div class="product-box">
<b>Gotika</b> – Intensive hydration luxury treatment.
</div>
""", unsafe_allow_html=True)

# -------------------------
# CHAT STATE
# -------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

# -------------------------
# DISPLAY CHAT
# -------------------------

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# -------------------------
# HALO CLICK INTERACTION
# -------------------------

st.markdown("<div class='halo-button'>", unsafe_allow_html=True)
halo_clicked = st.button("Tap To Speak", type="primary")
st.markdown("</div>", unsafe_allow_html=True)

if halo_clicked:

    audio_file = st.audio_input("Speak now")

    if audio_file:

        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )

        user_text = transcript.text

        system_prompt = f"""
You are a Professional Salon Hair Expert.

You can:
- Answer hair care questions
- Compare major brands
- Recommend the most suitable solution
- Position our products professionally against global brands

Use this knowledge:

{BRAND_KNOWLEDGE}

Always speak confidently and professionally.
If question is unrelated to hair care,
respond politely that you specialize in salon hair solutions only.

{language_instruction}
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ]
        )

        ai_reply = response.choices[0].message.content

        st.session_state.messages.append({"role": "user", "content": user_text})
        st.session_state.messages.append({"role": "assistant", "content": ai_reply})

        speech = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="nova",
            input=ai_reply
        )

        audio_bytes = speech.read()
        b64 = base64.b64encode(audio_bytes).decode()

        st.markdown(f"""
        <audio autoplay>
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        """, unsafe_allow_html=True)
