import os
import tempfile
import base64
from flask import Flask, request, jsonify
from openai import OpenAI

os.environ["PYTHONUNBUFFERED"] = "1"

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# =====================================
# FRONTEND PAGE
# =====================================

@app.route("/", methods=["GET"])
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Hair Advisor</title>
    </head>
    <body>
        <h1>AI Hair Advisor</h1>
        <button onclick="startRecording()">🎤 Ask About Your Hair</button>
        <p id="response"></p>

        <script>
        let mediaRecorder;
        let audioChunks = [];

        async function startRecording() {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = event => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                const formData = new FormData();
                formData.append("audio", audioBlob);

                const response = await fetch("/voice", {
                    method: "POST",
                    body: formData
                });

                const data = await response.json();

                document.getElementById("response").innerText = data.text;

                const audio = new Audio("data:audio/mp3;base64," + data.audio);
                audio.play();
            };

            mediaRecorder.start();

            setTimeout(() => {
                mediaRecorder.stop();
            }, 4000);
        }
        </script>
    </body>
    </html>
    """

# =====================================
# SIMPLE RULE ENGINE
# =====================================

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

    return "Formula Exclusiva"

# =====================================
# VOICE ROUTE
# =====================================

@app.route("/voice", methods=["POST"])
def voice():

    if "audio" not in request.files:
        return jsonify({"error": "No audio"}), 400

    file = request.files["audio"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
        file.save(temp_audio.name)
        audio_path = temp_audio.name

    with open(audio_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text"
        )

    user_text = transcript.strip()

    product = choose_product(user_text)

    speech = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=f"I recommend {product}."
    )

    audio_bytes = speech.read()
    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

    return jsonify({
        "text": f"I recommend {product}.",
        "audio": audio_base64
    })

# =====================================
# RUN
# =====================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
