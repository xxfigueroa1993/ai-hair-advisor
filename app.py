import streamlit as st
import os
import tempfile
import base64
from dotenv import load_dotenv
from openai import OpenAI

# -------------------------
# CONFIG
# -------------------------

load_dotenv()
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

st.set_page_config(page_title="Luxury AI Hair Expert", layout="centered")

# -------------------------
# SESSION STATE
# -------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "voice_count" not in st.session_state:
    st.session_state.voice_count = 0

# -------------------------
# AVATAR
# -------------------------

st.markdown("""
<style>
.avatar {
    width:150px;
    border-radius:50%;
    animation: float 4s ease-in-out infinite;
}
@keyframes float {
    0% { transform: translatey(0px); }
    50% { transform: translatey(-12px); }
    100% { transform: translatey(0px); }
}
</style>
""", unsafe_allow_html=True)

st.image("https://i.imgur.com/9yG3p8X.png", width=150)

st.title("Luxury Caribbean AI Hair Advisor")

# -------------------------
# AUDIO TRANSCRIPTION
# -------------------------

def transcribe_audio(audio_bytes):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    with open(tmp_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json"
        )

    return transcript.text, transcript.language

# -------------------------
# EMOTION DETECTION
# -------------------------

def detect_emotion(text):

    emotion_prompt = f"""
    Analyze emotional tone of this sentence:
    {text}

    Return one word:
    calm, stressed, frustrated, excited, neutral
    """

    stream = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": system_prompt},
        *st.session_state.messages,
        {"role": "user", "content": user_text}
    ],
    temperature=0.4,
    stream=True
)

full_reply = ""
response_placeholder = st.empty()

for chunk in stream:
    if chunk.choices[0].delta.content is not None:
        full_reply += chunk.choices[0].delta.content
        response_placeholder.markdown(full_reply)
    )

    return response.choices[0].message.content.strip().lower()

# -------------------------
# SYSTEM PROMPT BUILDER
# -------------------------

def build_system_prompt(language, emotion):

    base = """
You are Hair Expert Advisor, a luxury Caribbean salon AI assistant.

Mission:
Recommend ONE of:
Formula Exclusiva
Laciador
Gotero
Gotika
Or Go see medical professional

Style:
Luxury, confident, premium Caribbean salon tone.
Professional. Analytical. ROI-focused.

If language detected is Spanish, respond fully in Spanish.
If English, respond fully in English.
"""

    if emotion == "stressed":
        base += "\nSpeak calmly and reassuring."
    elif emotion == "frustrated":
        base += "\nBe empathetic and supportive."
    elif emotion == "excited":
        base += "\nMatch excitement but remain professional."

    return base

# -------------------------
# VOICE GENERATION
# -------------------------

def generate_voice(text):

    speech = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="nova",
        input=text
    )

    return speech.read()

# -------------------------
# AUTO PLAY
# -------------------------

def autoplay_audio(audio_bytes):

    b64 = base64.b64encode(audio_bytes).decode()
    audio_html = f"""
    <audio autoplay>
    <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
    </audio>
    """
    st.markdown(audio_html, unsafe_allow_html=True)

# -------------------------
# CHAT DISPLAY
# -------------------------

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# -------------------------
# VOICE INPUT (Native Streamlit)
# -------------------------

st.markdown("---")
st.subheader("🎤 Speak to Your AI Salon Expert")

if st.session_state.voice_count >= 10:
    st.warning("Free voice session limit reached.")
else:
    audio_file = st.audio_input("Tap and speak")

    if audio_file is not None:

        st.session_state.voice_count += 1

        audio_bytes = audio_file.read()
        st.audio(audio_bytes)

        with st.spinner("Analyzing your hair needs..."):

            # Whisper transcription (auto language detection built-in)
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )

            user_text = transcript.text

            # Emotion detection
            emotion_prompt = f"""
            Analyze emotional tone of this sentence:
            {user_text}

            Return one word:
            calm, stressed, frustrated, excited, neutral
            """

            emotion_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": emotion_prompt}],
                temperature=0
            )

            emotion = emotion_response.choices[0].message.content.strip().lower()

            # System prompt (Caribbean luxury branding)
            system_prompt = f"""
You are Hair Expert Advisor, a luxury Caribbean salon AI assistant.

Mission:
Recommend ONE of:
Formula Exclusiva
Laciador
Gotero
Gotika
Or Go see medical professional

Style:
Luxury, confident, premium Caribbean salon tone.
Professional. Analytical.

Language rule:
Respond in the same language as the user.

Emotion detected: {emotion}
Adapt your tone accordingly.
"""

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    *st.session_state.messages,
                    {"role": "user", "content": user_text}
                ],
                temperature=0.4
            )

            ai_reply = full_reply
            # Save conversation memory
            st.session_state.messages.append({"role": "user", "content": user_text})
            st.session_state.messages.append({"role": "assistant", "content": ai_reply})

            with st.chat_message("assistant"):
                st.markdown(ai_reply)

            # Generate Caribbean premium voice
            speech = client.audio.speech.create(
                model="gpt-4o-mini-tts",
                voice="nova",
                input=ai_reply
            )

            audio_response = speech.read()

            # Auto-play response
            import base64
            b64 = base64.b64encode(audio_response).decode()
            audio_html = f"""
            <audio autoplay>
                <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
            """
            st.markdown(audio_html, unsafe_allow_html=True)


