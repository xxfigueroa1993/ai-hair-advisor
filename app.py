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
# LUXURY UI + ANIMATED FACE STYLES
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
    text-align: center;
}
.face-container {
    display:flex;
    justify-content:center;
    margin-bottom:20px;
}
.eye {
    animation: blink 4s infinite;
    transform-origin: center;
}
@keyframes blink {
    0%, 95%, 100% { transform: scaleY(1); }
    97% { transform: scaleY(0.1); }
}
.mouth {
    transition: all 0.2s ease;
    transform-origin: center;
}
.talking .mouth {
    animation: talk 0.4s infinite alternate;
}
@keyframes talk {
    from { transform: scaleY(1); }
    to { transform: scaleY(1.6); }
}
.stButton>button {
    background-color: #c6a86b;
    color: black;
    border-radius: 25px;
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
# FACE RENDER FUNCTION
# -------------------------

def render_face(talking=False):
    state_class = "talking" if talking else ""
    st.markdown(f"""
    <div class="face-container {state_class}">
        <svg width="200" height="200" viewBox="0 0 200 200">
            <!-- Face -->
            <circle cx="100" cy="100" r="90" fill="#c6a86b"/>
            
            <!-- Eyes -->
            <circle class="eye" cx="70" cy="85" r="10" fill="#111"/>
            <circle class="eye" cx="130" cy="85" r="10" fill="#111"/>
            
            <!-- Mouth -->
            <ellipse class="mouth" cx="100" cy="135" rx="30" ry="12" fill="#111"/>
        </svg>
    </div>
    """, unsafe_allow_html=True)

# -------------------------
# HEADER
# -------------------------

st.title("Luxury Caribbean AI Hair Advisor")

render_face(talking=False)

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

        # Keep conversation light & fast
        st.session_state.messages = st.session_state.messages[-6:]
        st.session_state.voice_count += 1

        with st.spinner("Analyzing your hair needs..."):

            # -------------------------
            # SPEECH TO TEXT
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

Luxury Caribbean tone.
Respond in same language as user.
Emotion detected: {emotion}
Adapt tone accordingly.
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

            # Save conversation
            st.session_state.messages.append({"role": "user", "content": user_text})
            st.session_state.messages.append({"role": "assistant", "content": ai_reply})

            # -------------------------
            # TALKING FACE
            # -------------------------
            render_face(talking=True)

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

            # Return to idle face
            render_face(talking=False)
