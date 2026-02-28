import os
import tempfile
import base64
from flask import Flask, request, jsonify
from openai import OpenAI

os.environ["PYTHONUNBUFFERED"] = "1"

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# ======================================
# FRONTEND
# ======================================

@app.route("/", methods=["GET"])
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>AI Hair Advisor</title></head>
    <body>
        <h1>AI Hair Advisor</h1>
        <button onclick="record()">🎤 Ask</button>
        <p id="response"></p>

        <script>
        let recorder;
        let chunks = [];

        async function record() {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            recorder = new MediaRecorder(stream);
            chunks = [];

            recorder.ondataavailable = e => chunks.push(e.data);

            recorder.onstop = async () => {
                const blob = new Blob(chunks, { type: "audio/webm" });
                const form = new FormData();
                form.append("audio", blob);

                const res = await fetch("/voice", {
                    method: "POST",
                    body: form
                });

                const data = await res.json();
                document.getElementById("response").innerText = data.text;

                if (data.audio) {
                    const audio = new Audio("data:audio/mp3;base64," + data.audio);
                    audio.play();
                }
            };

            recorder.start();
            setTimeout(() => recorder.stop(), 4000);
        }
        </script>
    </body>
    </html>
    """

# ======================================
# RULE ENGINE
# ======================================

def choose_product(text):
    text = text.lower()

    if "dry" in text:
        return "Laciador"
    if "damaged" in text:
        return "Formula Exclusiva"
    if "oily" in text:
        return "Gotero"
    if "color" in text:
        return "Gotika"

    return None  # important change


# ======================================
# VOICE ROUTE
# ======================================

@app.route("/voice", methods=["POST"])
def voice():

    print("VOICE ROUTE HIT")

    if "audio" not in request.files:
        return jsonify({"error": "No audio"}), 400

    file = request.files["audio"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
        file.save(temp_audio.name)
        audio_path = temp_audio.name

    # Transcribe
    with open(audio_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text"
        )

    user_text = transcript.strip()

    print("Transcript:", user_text)

    # ==============================
    # SILENCE GUARD
    # ==============================

    if not user_text or len(user_text) < 3:
        return speak("I didn't hear anything. Please try again.")

    # Check for real hair keywords
    hair_keywords = ["dry", "damaged", "oily", "color", "falling", "tangly"]

    if not any(word in user_text.lower() for word in hair_keywords):
        return speak("Please tell me your hair concern like dry, damaged, or oily.")

    # ==============================
    # PRODUCT SELECTION
    # ==============================

    product = choose_product(user_text)

    if product is None:
        return speak("I couldn't determine your hair concern. Please try again.")

    return speak(f"I recommend {product}.")


# ======================================
# SPEECH RESPONSE FUNCTION
# ======================================

def speak(message):

    speech = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=message
    )

    audio_bytes = speech.read()
    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

    return jsonify({
        "text": message,
        "audio": audio_base64
    })


# ======================================
# RUN
# ======================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
