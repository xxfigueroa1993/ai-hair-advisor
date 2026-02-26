import streamlit as st
import os
import base64
import time
from dotenv import load_dotenv
from openai import OpenAI

# -------------------------
# CONFIG
# -------------------------

load_dotenv()
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

st.set_page_config(page_title="Luxury AI Salon Concierge", layout="centered")

# -------------------------
# LANGUAGE OPTIONS
# -------------------------

languages = {
    "English": "Respond in English.",
    "Arabic": "Respond in Modern Standard Arabic.",
    "Spanish": "Respond in Spanish.",
    "French": "Respond in French.",
    "German": "Respond in German."
}

# -------------------------
# STYLE
# -------------------------

st.markdown("""
<style>
body { background-color: #0c0c0c; }

.stApp {
    background: radial-gradient(circle at center, #1a1a1a 0%, #0c0c0c 70%);
    color: white;
}

.halo-container {
    display: flex;
    justify-content: center;
    margin-top: 30px;
    margin-bottom: 30px;
}

.idle-circle {
    stroke: #666;
    stroke-width: 2;
    fill: none;
    opacity: 0.5;
}

.speaking .wave {
    stroke: #d4af37;
    stroke-width: 3;
    fill: none;
    animation: pulse 0.6s ease-in-out infinite alternate;
    filter: drop-shadow(0px 0px 12px #d4af37);
}

@keyframes pulse {
    from { transform: scale(1); }
    to { transform: scale(1.12); }
}
</style>
""", unsafe_allow_html=True)

# -------------------------
# SESSION STATE
# -------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "speaking" not in st.session_state:
    st.session_state.speaking = False

# -------------------------
# HALO RENDER
# -------------------------

def render_halo():
    speaking_class = "speaking" if st.session_state.speaking else ""
    st.markdown(f"""
    <div class="halo-container {speaking_class}">
        <svg width="240" height="240" viewBox="0 0 200 200">
            <circle cx="100" cy="100" r="70" class="idle-circle"/>
            <path class="wave"
                d="M100 30
                Q130 40 160 70
                Q180 100 160 130
                Q130 160 100 170
                Q70 160 40 130
                Q20 100 40 70
                Q70 40 100 30"/>
        </svg>
    </div>
    """, unsafe_allow_html=True)

# -------------------------
# HEADER
# -------------------------

st.title("Luxury Salon AI Concierge")
render_halo()

selected_language = st.selectbox("🌍 Language", list(languages.keys()))
language_instruction = languages[selected_language]

# -------------------------
# CHAT HISTORY
# -------------------------

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# -------------------------
# VOICE INPUT
# -------------------------

audio_file = st.audio_input("🎤 Speak")

if audio_file:

    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file
    )

    user_text = transcript.text

    # -------------------------
    # STRICT SALON SYSTEM RULE
    # -------------------------

    system_prompt = f"""
You are a Professional Salon Hair Expert working for our company.

ONLY recommend:
- Formula Exclusiva
- Laciador
- Gotero
- Gotika

If the user asks anything unrelated to salon hair solutions,
reply politely with something similar to:

"I am a Professional Salon Hair Expert here to recommend hair solutions available within our company support."

Do NOT answer unrelated questions.
Remain elegant and professional.

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

    # -------------------------
    # SPEAKING MODE ON
    # -------------------------

    st.session_state.speaking = True
    render_halo()

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

    # Wait to keep animation during playback
    time.sleep(2.5)

    st.session_state.speaking = False
    render_halo()
