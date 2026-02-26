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

st.set_page_config(page_title="Luxury Caribbean AI Hair Advisor", layout="centered")

# -------------------------
# LUXURY UI THEME
# -------------------------

st.markdown("""
<style>
body {
    background-color: #0f0f0f;
}
.stApp {
    background: linear-gradient(135deg, #111 0%, #1c1c1c 100%);
    color: white;
}
h1 {
    font-weight: 600;
    letter-spacing: 1px;
}
.stButton>button {
    background-color: #c6a86b;
    color: black;
    border-radius: 25px;
}
.avatar {
    width:170px;
    border-radius:50%;
}
.talking {
    animation: pulse 0.6s infinite;
}
@keyframes pulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.05); }
    100% { transform: scale(1); }
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
# HEADER
# -------------------------

st.title("Luxury Caribbean AI Hair Advisor")

st.markdown('<img src="https://i.imgur.com/9yG3p8X.png" class="avatar">', unsafe_allow_html=True)

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
st.subheader("🎤 Speak to Your AI Salon Expert")

if st.session_state.voice_count >= 10:
    st.warning("Free voice session limit reached.")
else:
    audio_file = st.audio_input("Tap and speak")

    if audio_file is not None:

        # Trim memory for faster conversational feel
        st.session_state.messages = st.session_state.messages[-6:]

        st.session_state.voice_count += 1

        audio_bytes = audio_file.read()
        st.audio(audio_bytes)

        with st.spinner("Analyzing your hair needs..."):

            # -------------------------
            # SPEECH TO TEXT (Whisper)
            # -------------------------
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )

            user_text = transcript.text

            # -------------------------
            # EMOTION DETECTION
            # -------------------------
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

            # -------------------------
            # SYSTEM PROMPT
            # -------------------------
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
Luxury, confident, premium Caribbean tone.
Professional. Analytical.

Respond in the same language as the user.

Emotion detected: {emotion}
Adapt your tone accordingly.
"""

            # -------------------------
            # STREAMING GPT RESPONSE
            # -------------------------

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

            ai_reply = full_reply

            # Save conversation memory
            st.session_state.messages.append({"role": "user", "content": user_text})
            st.session_state.messages.append({"role": "assistant", "content": ai_reply})

            # -------------------------
            # TALKING AVATAR
            # -------------------------
            st.markdown('<img src="https://i.imgur.com/9yG3p8X.png" class="avatar talking">', unsafe_allow_html=True)

            # -------------------------
            # TEXT TO SPEECH
            # -------------------------
            speech = client.audio.speech.create(
                model="gpt-4o-mini-tts",
                voice="nova",
                input=ai_reply
            )

            audio_response = speech.read()

            # -------------------------
            # AUTO-PLAY AUDIO
            # -------------------------
            b64 = base64.b64encode(audio_response).decode()
            audio_html = f"""
            <audio autoplay>
                <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
            """
            st.markdown(audio_html, unsafe_allow_html=True)

            # Return avatar to idle
            st.markdown('<img src="https://i.imgur.com/9yG3p8X.png" class="avatar">', unsafe_allow_html=True)
