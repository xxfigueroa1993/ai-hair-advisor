import os
import json
from flask import Flask, request, send_file, make_response
from openai import OpenAI

app = Flask(__name__)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# ==============================
# SYSTEM PROMPT
# ==============================

SYSTEM_PROMPT = """
You are Bright Clinical AI.

Rules:
1. Always analyze the user's hair concern.
2. Always recommend exactly ONE product from:
   - Formula Exclusiva
   - Laciador
   - Gotero
   - Gotika
3. Give short, confident recommendation.
4. Do NOT greet repeatedly.
5. Do NOT ask unnecessary questions.
6. If unclear concern, ask for clarification.
7. Sound premium and clinical.
Respond ONLY in JSON:
{
  "product": "...",
  "response": "..."
}
"""

VALID_PRODUCTS = [
    "Formula Exclusiva",
    "Laciador",
    "Gotero",
    "Gotika"
]

HAIR_KEYWORDS = [
    "hair", "dry", "frizz", "damage",
    "thin", "break", "loss", "smooth",
    "volume", "brittle", "scalp",
    "growth", "repair", "hydration"
]

# ==============================
# MANUAL CORS HANDLING
# ==============================

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    return response

@app.route("/voice", methods=["OPTIONS"])
def voice_options():
    response = make_response()
    return response

# ==============================
# HEALTH CHECK
# ==============================

@app.route("/")
def home():
    return "Bright Clinical AI is running."

# ==============================
# VOICE ENDPOINT
# ==============================

@app.route("/voice", methods=["POST"])
def voice():
    try:
        if "audio" not in request.files:
            return "No audio received", 400

        audio_file = request.files["audio"]
        audio_path = "/tmp/input.webm"
        audio_file.save(audio_path)

        # -----------------------------
        # 1. TRANSCRIBE (Whisper)
        # -----------------------------
        with open(audio_path, "rb") as f:
            transcript_response = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )

        transcript = transcript_response.text.strip()
        print("TRANSCRIPT:", transcript)

        # -----------------------------
        # 2. STRICT FILTERING
        # -----------------------------

        if (
            transcript == "" or
            len(transcript) < 8 or
            transcript.lower() in ["you", "uh", "um", "hello", "thanks"]
        ):
            tts_text = "I did not hear a clear hair concern. Please describe your hair issue."

        elif not any(word in transcript.lower() for word in HAIR_KEYWORDS):
            tts_text = "Please describe your specific hair concern so I can recommend the correct product."

        else:
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": transcript}
                ],
                temperature=0.3
            )

            parsed = json.loads(completion.choices[0].message.content)

            if parsed.get("product") not in VALID_PRODUCTS:
                tts_text = "Formula Exclusiva is recommended for your concern."
            else:
                tts_text = parsed["response"]

        # -----------------------------
        # 3. TEXT TO SPEECH
        # -----------------------------

        speech_path = "/tmp/output.mp3"

        tts_response = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=tts_text
        )

        with open(speech_path, "wb") as f:
            f.write(tts_response.read())

        return send_file(speech_path, mimetype="audio/mpeg")

    except Exception as e:
        print("ERROR:", str(e))
        return "Server error", 500


# ==============================
# RUN
# ==============================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
