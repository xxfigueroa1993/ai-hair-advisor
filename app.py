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
    background: radial-gradient(circle at center, #0a0f12 0%, #000000 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    font-family: Arial;
    color: white;
    overflow: hidden;
}

/* PERFECT SEAMLESS HALO */
.halo {
    width: 190px;
    height: 190px;
    border-radius: 50%;
    cursor: pointer;
    position: relative;
    transition: all 0.6s ease;
    background: radial-gradient(circle at center,
        rgba(0,255,200,0.35) 0%,
        rgba(0,255,200,0.25) 35%,
        rgba(0,255,200,0.12) 60%,
        rgba(0,255,200,0.05) 75%,
        transparent 85%);
    box-shadow: 0 0 50px rgba(0,255,200,0.35);
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

let state = "idle"; // idle | listening | thinking | speaking
let silenceTimer = null;
let audioContext;
let analyser;
let dataArray;
let animationId;

const SILENCE_DELAY = 2300;
const SILENCE_THRESHOLD = 8;

/* =========================
   VIBRANT CLICK SOUND
========================= */
function playClickSound() {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = ctx.createOscillator();
    const gainNode = ctx.createGain();

    oscillator.type = "sine";
    oscillator.frequency.setValueAtTime(440, ctx.currentTime);
    oscillator.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.15);

    gainNode.gain.setValueAtTime(0.3, ctx.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);

    oscillator.connect(gainNode);
    gainNode.connect(ctx.destination);

    oscillator.start();
    oscillator.stop(ctx.currentTime + 0.3);
}

/* =========================
   COLOR TRANSITIONS
========================= */

function setColorIdle() {
    halo.style.background = `radial-gradient(circle at center,
        rgba(0,255,200,0.35) 0%,
        rgba(0,255,200,0.25) 40%,
        rgba(0,255,200,0.1) 70%,
        transparent 90%)`;
}

function setColorGold() {
    halo.style.background = `radial-gradient(circle at center,
        rgba(255,200,0,0.45) 0%,
        rgba(255,180,0,0.35) 40%,
        rgba(255,150,0,0.15) 70%,
        transparent 90%)`;
}

function setColorThinking() {
    halo.style.background = `radial-gradient(circle at center,
        rgba(0,255,255,0.6) 0%,
        rgba(0,220,255,0.4) 40%,
        rgba(0,180,255,0.2) 70%,
        transparent 90%)`;
}

/* =========================
   IDLE PULSE
========================= */

function idlePulse() {
    if (state !== "idle") return;

    let scale = 1 + Math.sin(Date.now() * 0.002) * 0.03;
    halo.style.transform = `scale(${scale})`;
    requestAnimationFrame(idlePulse);
}

setColorIdle();
idlePulse();

/* =========================
   CLICK BEHAVIOR
========================= */

halo.addEventListener("click", () => {

    playClickSound();

    if (state !== "idle") {
        resetToIdle();
        return;
    }

    startRecording();
});

/* =========================
   RESET
========================= */

function resetToIdle() {
    state = "idle";
    cancelAnimationFrame(animationId);
    setColorIdle();
    idlePulse();
}

/* =========================
   RECORDING
========================= */

async function startRecording() {

    state = "listening";
    setColorGold();

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

        state = "thinking";
        setColorThinking();

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

/* =========================
   SPEECH DETECTION
========================= */

function detectSpeech(mediaRecorder) {

    analyser.getByteFrequencyData(dataArray);

    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
    let volume = sum / dataArray.length;

    let scale = 1 + (volume / 300);
    halo.style.transform = `scale(${scale})`;

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

/* =========================
   AI RESPONSE
========================= */

function playAIResponse(base64Audio) {

    state = "speaking";

    const audio = new Audio("data:audio/mp3;base64," + base64Audio);

    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioContext.createAnalyser();

    const sourceNode = audioContext.createMediaElementSource(audio);
    sourceNode.connect(analyser);
    analyser.connect(audioContext.destination);

    dataArray = new Uint8Array(analyser.frequencyBinCount);

    audio.play();

    audio.onended = () => {
        state = "idle";
        setColorIdle();
        idlePulse();
    };
}

/* ========================= */

</script>
</body>
</html>
"""

# =====================================================
# BACKEND
# =====================================================

PRODUCTS = {
    "Laciador": {
        "description": "It deeply hydrates dry and brittle hair, restoring softness and shine.",
        "price": 34.99
    },
    "Gotero": {
        "description": "It balances excess oil while keeping your scalp fresh and clean.",
        "price": 29.99
    }
}

def choose_product(text):
    text = text.lower()
    if "dry" in text: return "Laciador"
    if "oily" in text: return "Gotero"
    return None

@app.route("/voice", methods=["POST"])
def voice():
    try:
        if "audio" not in request.files:
            return speak("I’m sorry, I didn’t quite catch that. Could you please repeat your hair concern?")

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
            return speak("I’m sorry, I didn’t quite catch that. Could you please repeat your hair concern?")

        product = choose_product(user_text)

        if not product:
            return speak("Please tell me if your hair is dry or oily so I can recommend the right product.")

        info = PRODUCTS[product]

        message = (
            f"I recommend {product}. "
            f"{info['description']} "
            f"With tax and shipping, you're looking at ${info['price']}."
        )

        return speak(message)

    except Exception:
        return speak("I’m sorry, something went wrong. Please try again.")

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
