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
    layout="centered",
)

# -------------------------
# STYLING
# -------------------------

st.markdown("""
<style>
body {
    background-color: #0c0c0c;
}

.stApp {
    background: radial-gradient(circle at top, #1a1a1a 0%, #0c0c0c 70%);
    color: #ffffff;
    font-family: 'Helvetica Neue', sans-serif;
}

h1 {
    text-align: center;
    letter-spacing: 2px;
    font-weight: 300;
}

/* Floating motion */
.silhouette-container {
    display: flex;
    justify-content: center;
    margin-top: 20px;
    margin-bottom: 30px;
    animation: float 7s ease-in-out infinite;
}

@keyframes float {
    0%   { transform: translateY(0px); }
    50%  { transform: translateY(-12px); }
    100% { transform: translateY(0px); }
}

/* Glow when speaking */
.speaking path, 
.speaking circle, 
.speaking line {
    stroke: #f0d27a;
    filter: drop-shadow(0px 0px 15px #f0d27a);
}

/* Chat spacing */
.block-container {
    padding-top: 2rem;
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

# -------------------------
# SILHOUETTE RENDER
# -------------------------

def render_silhouette(speaking=False):
    state = "speaking" if speaking else ""

    st.markdown(f"""
    <div class="silhouette-container {state}">
        <svg width="260" height="260" viewBox="0 0 200 200">

            <!-- Head outline (no features) -->
            <circle 
                cx="100" 
                cy="60" 
                r="28" 
                stroke="#d4af37" 
                stroke-width="3" 
                fill="none" />

            <!-- Shoulders -->
            <path 
                d="M35 150 Q100 105 165 150" 
                stroke="#d4af37" 
                stroke-width="3" 
                fill="none" />

            <!-- Suit lapels -->
            <path 
                d="M60 150 L100 115 L140 150" 
                stroke="#d4af37" 
                stroke-width="3" 
                fill="none" />

            <!-- Tie line -->
            <line 
                x1="100" 
                y1="115" 
                x2="100" 
                y2="160" 
                stroke="#d4af37" 
                stroke-width="3"/>

        </svg>
    </div>
    """, unsafe_allow_html=True)

# -------------------------
# HEADER
# -------------------------

st.title("Luxury Caribbean AI Concierge")
st.caption("Refined. Private. Discreet.")

render_silhouette(False)

# -------------------------
# DISPLAY CHAT HISTORY
# -------------------------

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# -------------------------
# VOICE INPUT SECTION
# -------------------------

st.markdown("---")
st.subheader("🎤 Speak to Your Private Advisor")

if st.session_state.voice_count < 10:

    audio_file = st.audio_input("Tap and speak")

    if audio_file is not None:

        st.session_state.voice_count += 1
        st.session_state.messages = st.session_state.messages[-6:]

        with st.spinner("Listening carefully..."):

            # Transcribe voice
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )

            user_text = transcript.text

            system_prompt = """
You are a refined luxury concierge.
Tone: Calm, elegant, composed.
Provide clear, confident, premium guidance.
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

            # Animate speaking glow
            render_silhouette(True)

            # Text-to-speech
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

            render_silhouette(False)

else:
    st.warning("Voice limit reached for this session.")
