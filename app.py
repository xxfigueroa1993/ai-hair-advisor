import os
from flask import Flask, request, jsonify

app = Flask(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# =============================
# Hair Product Logic
# =============================

PRODUCTS = {
    "formula": "Formula Exclusiva – All-in-one natural professional salon hair treatment",
    "laciador": "Laciador – All-natural hair styler",
    "gotero": "Gotero – All-natural hair gel",
    "gotika": "Gotika – All-natural hair color treatment"
}

def detect_product(text):
    text = text.lower()

    if any(word in text for word in ["dry", "damage", "frizz", "repair", "breakage"]):
        return "formula"
    if any(word in text for word in ["straight", "smooth", "styling", "control"]):
        return "laciador"
    if any(word in text for word in ["hold", "gel", "shape", "spike"]):
        return "gotero"
    if any(word in text for word in ["color", "dye", "gray", "roots"]):
        return "gotika"

    return None

def generate_response(user_text):
    product_key = detect_product(user_text)

    if not product_key:
        return {
            "text": "I specialize in professional hair product solutions. Could you describe your concern more specifically, for example: dry hair, frizz, color treatment, or styling needs?",
            "recommendation": None
        }

    product = PRODUCTS[product_key]

    return {
        "text": f"Based on what you described, I recommend {product}. Does that match what you're looking to improve?",
        "recommendation": product
    }

# =============================
# Routes
# =============================

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
  color:white;
  font-family:sans-serif;
  flex-direction:column;
}

#sphere {
  width:160px;
  height:160px;
  border-radius:50%;
  background: radial-gradient(circle at 30% 30%, #00f0ff, #0044ff);
  box-shadow: 0 0 60px rgba(0,200,255,0.8);
  transition: transform 0.1s ease;
}

#status {
  margin-top:20px;
}
</style>
</head>
<body>

<div id="sphere"></div>
<div id="status">Tap to speak</div>

<script>
const sphere = document.getElementById("sphere")
const statusText = document.getElementById("status")

let recognition
let speaking = false
let audioContext
let analyser
let micStream

function pulse(size) {
    sphere.style.transform = "scale(" + size + ")"
}

async function setupMic() {
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true })
    audioContext = new AudioContext()
    const source = audioContext.createMediaStreamSource(micStream)
    analyser = audioContext.createAnalyser()
    analyser.fftSize = 256
    source.connect(analyser)

    const dataArray = new Uint8Array(analyser.frequencyBinCount)

    function animate() {
        analyser.getByteFrequencyData(dataArray)
        let values = 0
        for (let i = 0; i < dataArray.length; i++) {
            values += dataArray[i]
        }
        let average = values / dataArray.length
        let scale = 1 + (average / 300)
        pulse(scale)
        requestAnimationFrame(animate)
    }
    animate()
}

function speak(text) {
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.onstart = () => { speaking = true }
    utterance.onend = () => { speaking = false }
    speechSynthesis.speak(utterance)
}

function startRecognition() {
    recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)()
    recognition.lang = "en-US"
    recognition.continuous = false
    recognition.interimResults = false

    recognition.onstart = () => {
        statusText.innerText = "Listening..."
    }

    recognition.onresult = async (event) => {
        let transcript = event.results[0][0].transcript
        statusText.innerText = "Analyzing..."

        let res = await fetch("/chat", {
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({message: transcript})
        })

        let data = await res.json()
        speak(data.text)
        statusText.innerText = "Tap to speak"
    }

    recognition.start()
}

document.body.onclick = () => {
    if (!recognition) {
        setupMic()
        startRecognition()
    } else {
        startRecognition()
    }
}
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
