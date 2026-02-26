import streamlit as st
from openai import OpenAI
import os
import hashlib
import tempfile

# ==========================
# CONFIG
# ==========================

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

CACHE_FOLDER = "audio_cache"
os.makedirs(CACHE_FOLDER, exist_ok=True)

# ==========================
# SYSTEM PROMPT
# ==========================

SYSTEM_PROMPT = """
You are a Professional Salon Hair Expert.

Only answer hair-related questions.

If asked anything outside hair, respond:
"I am a Professional Salon Hair Expert here to recommend hair solutions available within our company support. How may I assist you with your hair needs today?"

Always guide toward:

1. Formula Exclusiva – Deep repair & professional restoration.
2. Laciador – Advanced smoothing & frizz control.
3. Gotero – Scalp strengthening & growth-focused care.
4. Gotika – Intensive hydration luxury treatment.
"""

# ==========================
# CACHE FUNCTION
# ==========================

def generate_cache_key(text):
    return hashlib.sha256(text.encode()).hexdigest() + ".mp3"

# ==========================
# UI
# ==========================

st.set_page_config(page_title="Professional Hair AI", layout="centered")

st.title("💎 Professional Hair AI Consultant")

st.markdown("### Our Solutions")
st.markdown("""
**Formula Exclusiva** – Deep repair & professional restoration  
**Laciador** – Advanced smoothing & frizz control  
**Gotero** – Scalp strengthening & growth-focused care  
**Gotika** – Intensive hydration luxury treatment  
""")

st.divider()

# ==========================
# AUDIO INPUT
# ==========================

audio_file = st.file_uploader("Upload a voice question (wav/mp3/webm)", type=["wav", "mp3", "webm"])

if audio_file:

    st.info("Processing your request...")

    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(audio_file.read())
        tmp_path = tmp.name

    # 1️⃣ Transcribe
    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=open(tmp_path, "rb")
    )

    user_text = transcript.text

    st.write("🗣 You asked:", user_text)

    # 2️⃣ GPT Response
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ]
    )

    reply = completion.choices[0].message.content

    st.write("💬 AI Response:")
    st.success(reply)

    # 3️⃣ Check Cache
    cache_key = generate_cache_key(reply)
    file_path = os.path.join(CACHE_FOLDER, cache_key)

    if os.path.exists(file_path):
        audio_bytes = open(file_path, "rb").read()
    else:
        speech = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=reply
        )

        audio_bytes = speech.read()

        with open(file_path, "wb") as f:
            f.write(audio_bytes)

    # 4️⃣ Play Audio
    st.audio(audio_bytes, format="audio/mp3")
