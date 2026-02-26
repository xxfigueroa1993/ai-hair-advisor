import os
import audioop
from flask import Flask, request, jsonify, session
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = "supersecretkey"
CORS(app)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------------------------------
# AUDIO SILENCE DETECTION
# ---------------------------------

def is_silence(audio_file):
    audio_bytes = audio_file.read()
    audio_file.seek(0)

    if len(audio_bytes) < 1000:
        return True

    try:
        rms = audioop.rms(audio_bytes, 2)
        return rms < 300  # Adjust sensitivity if needed
    except:
        return False


# ---------------------------------
# PRODUCT CLASSIFIER (DETERMINISTIC)
# ---------------------------------

def classify_product(text):
    text = text.lower()

    formula_keywords = ["dry","damaged","breakage","weak","brittle","split","repair","restore"]
    laciador_keywords = ["frizz","smooth","straight","puffy","texture","sleek"]
    gotero_keywords = ["gel","hold","style","spike","shape","structure"]
    gotika_keywords = ["color","dye","grey","gray","blonde","shade","tint"]

    for word in formula_keywords:
        if word in text:
            return "Formula Exclusiva"

    for word in laciador_keywords:
        if word in text:
            return "Laciador"

    for word in gotero_keywords:
        if word in text:
            return "Gotero"

    for word in gotika_keywords:
        if word in text:
            return "Gotika"

    return None


# ---------------------------------
# VOICE PROCESSING
# ---------------------------------

@app.route("/process", methods=["POST"])
def process_voice():

    if "attempts" not in session:
        session["attempts"] = 0

    audio_file = request.files["audio"]

    # 🛑 Reject Silence Immediately
    if is_silence(audio_file):
        return jsonify({
            "transcript": "",
            "reply": "",
            "audio": "",
            "state": "silence"
        })

    # 1️⃣ Transcribe
    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file
    )

    user_text = transcript.text.strip()

    # 🛑 Reject if too short
    if len(user_text) < 3:
        return jsonify({
            "transcript": "",
            "reply": "",
            "audio": "",
            "state": "silence"
        })

    # 2️⃣ Classify Product
    product = classify_product(user_text)

    # 3️⃣ Clarification Logic
    if not product:

        session["attempts"] += 1

        if session["attempts"] >= 2:
            reply_text = (
                "For a precise recommendation, please contact our professional support team for a personalized consultation. "
                "You may also restart and briefly mention if your concern involves dryness, frizz, styling hold, or hair color."
            )
            session["attempts"] = 0
        else:
            reply_text = (
                "Please briefly describe if your concern involves dryness, frizz, styling hold, or hair color so I can recommend the correct product."
            )

    else:

        session["attempts"] = 0

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"""
You are a professional clinical salon specialist.

Selected product: {product}

Rules:
- Only respond based on what the user said.
- Do not introduce yourself.
- Do not ask unrelated questions.
- Confidently recommend the selected product.
- Explain why it matches the user's concern.
- End with a confirmation question.
"""
                },
                {"role": "user", "content": user_text}
            ]
        )

        reply_text = completion.choices[0].message.content

    # 4️⃣ Generate Speech
    speech = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=reply_text
    )

    audio_output = speech.read()

    return jsonify({
        "transcript": user_text,
        "reply": reply_text,
        "audio": audio_output.hex(),
        "state": "speaking"
    })


# ---------------------------------
# ROOT CHECK
# ---------------------------------

@app.route("/")
def home():
    return "Bright Clinical AI Running"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
