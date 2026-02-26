import os
from flask import Flask, request, jsonify

app = Flask(__name__)

PRODUCTS = {
    "formula": "Formula Exclusiva – All-in-one natural professional salon hair treatment",
    "laciador": "Laciador – All-natural hair styler",
    "gotero": "Gotero – All-natural hair gel",
    "gotika": "Gotika – All-natural hair color treatment"
}

def detect_product(text):
    t = text.lower()

    if any(w in t for w in ["dry", "frizz", "damage", "breakage"]):
        return "formula"
    if any(w in t for w in ["straight", "smooth", "styling"]):
        return "laciador"
    if any(w in t for w in ["gel", "hold", "spike"]):
        return "gotero"
    if any(w in t for w in ["color", "gray", "dye"]):
        return "gotika"

    return None


def generate_response(user_text):
    key = detect_product(user_text)

    if not key:
        return {
            "text": "I specialize in professional hair product solutions. Please describe your concern more clearly, for example: dry hair, frizz, styling, or color treatment.",
            "recommendation": None
        }

    product = PRODUCTS[key]

    return {
        "text": f"Based on what you described, I recommend {product}. Does that match your concern?",
        "recommendation": product
    }


@app.route("/")
def index():
    return """
<!DOCTYPE html>
<html>
<head>
<title>Bright Clinical AI</title>
<style>
body {
  margin:0;
  background:black;
  display:flex;
  justify-content:center;
  align-items:center;
  height:100vh;
  flex-direction:column;
  color:white;
  font-family:sans-serif;
}

#sphere {
  width:180px;
  height:180px;
  border-radius:50%;
  background: radial-gradient(circle at 30% 30%, #00f0ff, #0044ff);
  box-shadow: 0 0 80px rgba(0,200,255,0.9);
  transition: transform 0.08s linear;
}

#status {
  margin-top:20px;
}
</style>
</head>
<body>

<div id="sphere"></div>
<div id="status">Initializing...</div>

<script>
const sphere = document.getElementById("sphere")
const statusText = document.getElementById("status")

let audioContext
let analyser
let dataArray
let recognition
let listening = false
let speakingDetected = false
let speechStartTime = 0

function animateIdle() {
    let scale = 1 + Math.sin(Date.now()/500) * 0.05
    sphere.style.transform = "scale(" + scale + ")"
    requestAnimationFrame(animateIdle)
}

async function initAudio() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    audioContext = new AudioContext()
    const source = audioContext.createMediaStreamSource(stream)
    analyser = audioContext.createAnalyser()
    analyser.fftSize = 256
    source.connect(analyser)
    dataArray = new Uint8Array(analyser.frequencyBinCount)

    monitorVolume()
}

function monitorVolume() {
    analyser.getByteFrequencyData(dataArray)
    let sum = 0
    for (let i=0;i<dataArray.length;i++) sum += dataArray[i]
    let avg = sum / dataArray.length

    let scale = 1 + (avg / 400)
    sphere.style.transform = "scale(" + scale + ")"

    if (listening) {
        if (avg > 25) {
            if (!speakingDetected) {
                speechStartTime = Date.now()
                speakingDetected = true
            }
        }
    }

    requestAnimationFrame(monitorVolume)
}

function setupRecognition() {
    recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)()
    recognition.lang = "en-US"
    recognition.continuous = false
    recognition.interimResults = false

    recognition.onresult = async (event) => {
        let transcript = event.results[0][0].transcript

        let duration = Date.now() - speechStartTime

        if (!transcript || duration < 800) {
            statusText.innerText = "No clear speech detected. Try again."
            resetListening()
            return
        }

        statusText.innerText = "Analyzing..."

        let res = await fetch("/chat", {
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({message: transcript})
        })

        let data = await res.json()
        speak(data.text)
        resetListening()
    }
}

function speak(text) {
    const utter = new SpeechSynthesisUtterance(text)
    utter.onstart = () => statusText.innerText = "AI Speaking..."
    utter.onend = () => statusText.innerText = "Tap to speak"
    speechSynthesis.speak(utter)
}

function resetListening() {
    listening = false
    speakingDetected = false
}

function startListening() {
    if (listening) return

    listening = true
    speakingDetected = false
    statusText.innerText = "Speak now..."
    recognition.start()
}

document.body.onclick = async () => {
    if (!audioContext) {
        await initAudio()
        setupRecognition()
        statusText.innerText = "Tap to speak"
    } else {
        startListening()
    }
}

animateIdle()
</script>

</body>
</html>
"""


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_text = data.get("message", "")
    response = generate_response(user_text)
    return jsonify(response)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
