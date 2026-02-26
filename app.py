import os
from flask import Flask, request, jsonify, session
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = "supersecretkey"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -----------------------------
# PRODUCT CLASSIFIER
# -----------------------------

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


# -----------------------------
# PROCESS VOICE
# -----------------------------

@app.route("/process", methods=["POST"])
def process_voice():

    if "attempts" not in session:
        session["attempts"] = 0

    audio_file = request.files["audio"]

    # Silence protection (basic size check)
    audio_bytes = audio_file.read()
    audio_file.seek(0)

    if len(audio_bytes) < 5000:
        return jsonify({
            "transcript": "",
            "reply": "",
            "audio": "",
            "state": "silence"
        })

    # Transcribe
    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file
    )

    user_text = transcript.text.strip()

    # Reject empty transcript
    if not user_text or len(user_text.split()) < 2:
        return jsonify({
            "transcript": "",
            "reply": "",
            "audio": "",
            "state": "silence"
        })

    product = classify_product(user_text)

    if not product:
        session["attempts"] += 1

        if session["attempts"] >= 2:
            reply_text = (
                "For a precise recommendation, please contact our professional support team for personalized assistance. "
                "You may also restart and briefly mention dryness, frizz, styling hold, or hair color."
            )
            session["attempts"] = 0
        else:
            reply_text = (
                "Please briefly describe if your concern involves dryness, frizz, styling hold, or hair color."
            )

    else:
        session["attempts"] = 0

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"""
You are a professional salon specialist.

Selected product: {product}

Rules:
- Only respond based on the transcribed speech.
- Do not introduce yourself.
- Confidently recommend the product.
- Explain why it fits.
- End with confirmation.
"""
                },
                {"role": "user", "content": user_text}
            ]
        )

        reply_text = completion.choices[0].message.content

    # Generate speech
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


@app.route("/")
def home():
    return "Bright Clinical AI Running"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
