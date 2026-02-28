import os
import tempfile
import base64
from flask import Flask, request, jsonify
from openai import OpenAI

os.environ["PYTHONUNBUFFERED"] = "1"

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# =====================================================
# FRONTEND
# =====================================================

@app.route("/", methods=["GET"])
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<title>AI Hair Advisor</title>
<style>
body {
    margin: 0;
    height: 100vh;
    background: radial-gradient(circle at center, #0f0f0f 0%, #000000 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    font-family: Arial;
    color: white;
    overflow: hidden;
}

.halo {
    width: 180px;
    height: 180px;
    border-radius: 50%;
    cursor: pointer;
    position: relative;
    background: rgba(255,255,255,0.03);
    backdrop-filter: blur(8px);
    transition: transform 0.05s linear, box-shadow 0.05s linear;
    box-shadow:
        0 0 30px rgba(0,255,255,0.25),
        inset 0 0 50px rgba(0,255,255,0.12);
}

.halo::before {
    content: "";
    position: absolute;
    inset: -14px;
    border-radius: 50%;
    background: radial-gradient(circle,
        rgba(0,255,255,0.5) 0%,
        rgba(0,255,255,0.25) 40%,
        rgba(0,255,255,0.08) 70%,
        transparent 85%);
    opacity: 0.7;
}

#response {
    margin-top: 40px;
    width: 70%;
    text-align: center;
    font-size: 18px;
    line-height: 1.6;
}
</style>
</head>
<body>

<div id="halo" class="halo"></div>
<div id="response">Tap the ring and ask about your hair.</div>

<script>

const halo = document.getElementById("halo");
let audioContext;
let analyser;
let dataArray;
let animationId;

let silenceTimer = null;
const SILENCE_DELAY = 2300;  // 2.3 seconds
const SILENCE_THRESHOLD = 8; // mic sensitivity

function idlePulse() {
    let scale = 1 + Math.sin(Date.now() * 0.002) * 0.03;
    halo.style.transform = `scale(${scale})`;
    requestAnimationFrame(idlePulse);
}
idlePulse();

halo.addEventListener("click", startRecording);

async function startRecording() {

    cancelAnimationFrame(animationId);

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;

    const source = audioContext.createMediaStreamSource(stream);
    source.connect(analyser);

    dataArray = new Uint8Array(analyser.frequencyBinCount);

    const mediaRecorder = new MediaRecorder(stream);
    let chunks = [];

    mediaRecorder.ondataavailable = e => chunks.push(e.data);

    mediaRecorder.onstop = async () => {

        stream.getTracks().forEach(track => track.stop());

        const blob = new Blob(chunks, { type: "audio/webm" });
        const form = new FormData();
        form.append("audio", blob);

        const res = await fetch("/voice", {
            method: "POST",
            body: form
        });

        const data = await res.json();
        document.getElementById("response").innerText = data.text;

        playAIResponse(data.audio);
    };

    mediaRecorder.start();
    detectSpeech(mediaRecorder);
}

function detectSpeech(mediaRecorder) {
    analyser.getByteFrequencyData(dataArray);

    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i];
    }

    let volume = sum / dataArray.length;

    // Live mic reactive halo
    let scale = 1 + (volume / 300);
    halo.style.transform = `scale(${scale})`;
    halo.style.boxShadow = `0 0 ${30 + volume/4}px rgba(0,255,255,0.7)`;

    // Silence detection
    if (volume < SILENCE_THRESHOLD) {
        if (!silenceTimer) {
            silenceTimer = setTimeout(() => {
                mediaRecorder.stop();
                silenceTimer = null;
            }, SILENCE_DELAY);
        }
    } else {
        if (silenceTimer) {
            clearTimeout(silenceTimer);
            silenceTimer = null;
        }
    }

    animationId = requestAnimationFrame(() => detectSpeech(mediaRecorder));
}

function playAIResponse(base64Audio) {

    const audio = new Audio("data:audio/mp3;base64," + base64Audio);

    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;

    const sourceNode = audioContext.createMediaElementSource(audio);
    sourceNode.connect(analyser);
    analyser.connect(audioContext.destination);

    dataArray = new Uint8Array(analyser.frequencyBinCount);

    audio.play();
    reactToAI();

    audio.onended = () => {
        idlePulse();
    };
}

function reactToAI() {
    analyser.getByteFrequencyData(dataArray);

    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i];
    }

    let volume = sum / dataArray.length;
    let scale = 1 + (volume / 300);

    halo.style.transform = `scale(${scale})`;
    halo.style.boxShadow = `0 0 ${30 + volume/4}px rgba(0,255,150,0.8)`;

    animationId = requestAnimationFrame(reactToAI);
}

</script>
</body>
</html>
"""

# =====================================================
# BACKEND LOGIC
# =====================================================

PRODUCTS = {
    "Laciador": {
        "description": "It deeply hydrates dry and brittle hair, restoring softness and shine.",
        "price": 34.99
    },
    "Gotero": {
        "description": "It balances excess oil while keeping your scalp fresh and clean.",
        "price": 29.99
    },
    "Formula Exclusiva": {
        "description": "It repairs damaged strands and strengthens hair from root to tip.",
        "price": 39.99
    },
    "Gotika": {
        "description": "It protects color-treated hair and enhances vibrancy and glow.",
        "price": 36.99
    }
}

def choose_product(text):
    text = text.lower()
    if "dry" in text: return "Laciador"
    if "damaged" in text: return "Formula Exclusiva"
    if "oily" in text: return "Gotero"
    if "color" in text: return "Gotika"
    return None

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

    if not user_text or len(user_text) < 3:
        return speak("I didn't hear anything. Please try again.")

    product = choose_product(user_text)

    if not product:
        return speak("Please tell me your hair concern like dry, damaged, oily, or color-treated.")

    info = PRODUCTS[product]

    message = (
        f"I recommend {product}. "
        f"{info['description']} "
        f"With tax and shipping, you're looking at ${info['price']}."
    )

    return speak(message)

def speak(message):
    speech = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=message
    )
    audio_bytes = speech.read()
    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
    return jsonify({"text": message, "audio": audio_base64})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
