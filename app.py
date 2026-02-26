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

st.set_page_config(
    page_title="Luxury AI Concierge",
    layout="centered"
)

# -------------------------
# LANGUAGE OPTIONS
# -------------------------

languages = {
    "English": "Respond in English.",
    "Arabic": "Respond in Modern Standard Arabic.",
    "Spanish": "Respond in Spanish.",
    "French": "Respond in French.",
    "German": "Respond in German.",
    "Portuguese": "Respond in Portuguese.",
    "Hindi": "Respond in Hindi.",
    "Urdu": "Respond in Urdu.",
    "Bengali": "Respond in Bengali.",
    "Turkish": "Respond in Turkish.",
    "Indonesian": "Respond in Indonesian.",
    "Chinese (Simplified)": "Respond in Simplified Chinese.",
    "Japanese": "Respond in Japanese.",
    "Korean": "Respond in Korean.",
    "Russian": "Respond in Russian."
}

# -------------------------
# STYLE
# -------------------------

st.markdown("""
<style>
body {
    background-color: #0c0c0c;
}

.stApp {
    background: radial-gradient(circle at center, #1a1a1a 0%, #0c0c0c 70%);
    color: white;
    font-family: 'Helvetica Neue', sans-serif;
}

h1 {
    text-align: center;
    font-weight: 300;
    letter-spacing: 2px;
}

.halo-container {
    display: flex;
    justify-content: center;
    margin-top: 30px;
    margin-bottom: 30px;
    animation: float 6s ease-in-out infinite;
}

@keyframes float {
    0% { transform: translateY(0px); }
    50% { transform: translateY(-10px); }
    100% { transform: translateY(0px); }
}

.idle-circle {
    stroke: #777;
    stroke-width: 2;
    fill: none;
    opacity: 0.6;
}

.speaking .wave {
    stroke: #d4af37;
    stroke-width: 3;
    fill: none;
    animation: pulse 0.8s ease-in-out infinite alternate;
    filter: drop-shadow(0px 0px 10px #d4af37);
}

@keyframes pulse {
    from { transform: scale(1); }
    to { transform: scale(1.08); }
}
</style>
""", unsafe_allow_html=True)

# -------------------------
# SESSION STATE
# -------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "voice_count" not in st.session_state:
    st.session_state.voice_count = 0

if "language" not in st.session_state:
    st.session_state.language = "English"

# -------------------------
# HALO RENDER
# -------------------------

def render_halo(speaking=False):
    state_class = "speaking" if speaking else ""

    st.markdown(f"""
    <div class="halo-container {state_class}">
        <svg width="260" height="260" viewBox="0 0 200 200">
            <circle cx="100" cy="100" r="70" class="idle-circle"/>
            <path class="wave"
                d="
                M100 30
                Q120 40 140 60
                Q160 80 170 100
                Q160 120 140 140
                Q120 160 100 170
                Q80 160 60 140
                Q40 120 30 100
                Q40 80 60 60
                Q80 40 100 30
                "
            />
        </svg>
    </div>
    """, unsafe_allow_html=True)

# -------------------------
# HEADER
# -------------------------

st.title("Luxury Caribbean AI Concierge")
st.caption("An Intelligent Voice. Nothing More.")

render_halo(False)

# -------------------------
# LANGUAGE SELECTOR
# -------------------------

selected_language = st.selectbox(
    "🌍 Select Language",
    list(languages.keys())
)

st.session_state.language = selected_language

# -------------------------
# CHAT HISTORY
# -------------------------

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# -------------------------
# VOICE INPUT
# -------------------------

st.markdown("---")
st.subheader("🎤 Speak to Your Private Advisor")

if st.session_state.voice_count < 10:

    audio_file = st.audio_input("Tap and speak")

    if audio_file is not None:

        st.session_state.voice_count += 1
        st.session_state.messages = st.session_state.messages[-6:]

        with st.spinner("Listening carefully..."):

            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )

            user_text = transcript.text

            language_instruction = languages[selected_language]

            system_prompt = f"""
You are a refined luxury concierge.
Tone: Calm, confident, elegant.
{language_instruction}
Keep responses concise but valuable.
"""

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    *st.session_state.messages,
                    {"role": "user", "content": user_text}
                ]
            )

            ai_reply = response.choices[0].message.content

            st.session_state.messages.append(
                {"role": "user", "content": user_text}
            )
            st.session_state.messages.append(
                {"role": "assistant", "content": ai_reply}
            )

            render_halo(True)

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

            render_halo(False)

else:
    st.warning("Voice limit reached for this session.")
