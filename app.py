import os
import json
from flask import Flask, request, send_file, make_response
from openai import OpenAI

app = Flask(__name__)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are Bright Clinical AI.

Rules:
1. Analyze the user's hair concern.
2. Recommend exactly ONE product from:
   - Formula Exclusiva
   - Laciador
   - Gotero
   - Gotika
3. Be confident and concise.
4. Do not greet repeatedly.
5. If unclear, ask for clarification.

Return ONLY JSON:
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

# -----------------------------
# CORS
# -----------------------------

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    return response

@app.route("/voice", methods=["OPTIONS"])
def voice_options():
    return make_response()

# -----------------------------
# FRONTEND
# -----------------------------

@app.route("/")
def home():
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
  width:200px;
  height:200px;
  border-radius:50%;
  background: radial-gradient(circle at 30% 30%, #00f0ff, #0044ff);
  box-shadow: 0 0 90px rgba(0,200,255,0.9);
  cursor:pointer;
}
#status { margin-top:20px; }
</style>
</head>
<body>

<div id="sphere"></div>
<div id="status">Click sphere to speak (5 sec max)</div>

<script>
let mediaRecorder
let audioChunks = []
let listening = false
const RECORD_TIME = 5000

const sphere = document.getElementById("sphere")
const statusText = document.getElementById("status")

async function startListening(){
  const stream = await navigator.mediaDevices.getUserMedia({audio:true})
  mediaRecorder = new MediaRecorder(stream)

  audioChunks = []
  mediaRecorder.start()
  listening = true
  statusText.innerText = "Listening..."

  mediaRecorder.ondataavailable = e => audioChunks.push(e.data)

  mediaRecorder.onstop = async () => {
    listening = false
    statusText.innerText = "AI Thinking..."

    const blob = new Blob(audioChunks,{type:"audio/webm"})
    const formData = new FormData()
    formData.append("audio",blob,"speech.webm")

    try {
        const res = await fetch("/voice",{method:"POST",body:formData})
        const audioBlob = await res.blob()

        const audioUrl = URL.createObjectURL(audioBlob)
        const audio = new Audio(audioUrl)

        statusText.innerText = "AI Speaking..."
        audio.play()

        audio.onended = ()=>{
            statusText.innerText = "Click sphere to speak"
        }

    } catch {
        statusText.innerText = "Server error"
    }
  }

  setTimeout(()=>{
    if(listening){
      mediaRecorder.stop()
    }
  }, RECORD_TIME)
}

sphere.onclick = ()=>{
  if(!listening) startListening()
}
</script>

</body>
</html>
"""

# -----------------------------
# VOICE ENDPOINT
# -----------------------------

@app.route("/voice", methods=["POST"])
def voice():
    try:
        if "audio" not in request.files:
            return "No audio received", 400

        audio_file = request.files["audio"]
        audio_path = "/tmp/input.webm"
        audio_file.save(audio_path)

        # TRANSCRIBE
        with open(audio_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            ).text.strip()

        print("TRANSCRIPT:", transcript)

        # FILTER SILENCE / JUNK
        if (
            transcript == "" or
            len(transcript) < 8 or
            not any(word in transcript.lower() for word in HAIR_KEYWORDS)
        ):
            tts_text = "I did not hear a clear hair concern. Please describe your hair issue."

        else:
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role":"system","content":SYSTEM_PROMPT},
                    {"role":"user","content":transcript}
                ],
                temperature=0.3
            )

            parsed = json.loads(completion.choices[0].message.content)

            if parsed.get("product") not in VALID_PRODUCTS:
                tts_text = "Formula Exclusiva is recommended for your concern."
            else:
                tts_text = parsed["response"]

        # TTS
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
