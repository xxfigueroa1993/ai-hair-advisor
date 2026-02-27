import os
import json
from flask import Flask, request, jsonify, send_file
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are Bright Clinical AI, a decisive professional hair product advisor.

RULES:
- Ignore greetings.
- Extract the core hair concern even if vague.
- Infer the most likely issue if unclear.
- NEVER ask for clarification before recommending.
- ALWAYS select EXACTLY ONE product from:
  Formula Exclusiva
  Laciador
  Gotero
  Gotika
- Be confident and direct.
- End with a short confirmation question.

Return ONLY valid JSON:

{
  "product": "Product Name",
  "response": "Confident professional recommendation ending with short confirmation."
}
"""

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
  width:200px;
  height:200px;
  border-radius:50%;
  background: radial-gradient(circle at 30% 30%, #00f0ff, #0044ff);
  box-shadow: 0 0 90px rgba(0,200,255,0.9);
  transition: transform 0.07s linear;
  cursor:pointer;
}
#status { margin-top:20px; }
</style>
</head>
<body>

<div id="sphere"></div>
<div id="status">Click sphere to begin</div>

<script>
let mediaRecorder
let audioChunks = []
let silenceTimer = null
let audioContext
let analyser
let dataArray
let listening = false

const SILENCE_THRESHOLD = 4
const SILENCE_DURATION = 3000

const sphere = document.getElementById("sphere")
const statusText = document.getElementById("status")

function pulse(scale){
  sphere.style.transform = "scale(" + scale + ")"
}

async function startListening(){
  const stream = await navigator.mediaDevices.getUserMedia({audio:true})
  mediaRecorder = new MediaRecorder(stream)

  audioContext = new AudioContext()
  const source = audioContext.createMediaStreamSource(stream)
  analyser = audioContext.createAnalyser()
  source.connect(analyser)

  analyser.fftSize = 2048
  dataArray = new Uint8Array(analyser.fftSize)

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
            statusText.innerText = "Click sphere to begin"
        }

    } catch {
        statusText.innerText = "Server error"
    }
  }

  monitorVolume()
}

function monitorVolume(){
  if(!listening) return

  analyser.getByteTimeDomainData(dataArray)

  let sum = 0
  for(let i=0;i<dataArray.length;i++){
    let value = (dataArray[i] - 128) / 128
    sum += Math.abs(value)
  }

  let avg = sum / dataArray.length * 100

  pulse(1 + avg/10)

  if(avg < SILENCE_THRESHOLD){
      if(!silenceTimer){
          silenceTimer = setTimeout(()=>{
              mediaRecorder.stop()
          }, SILENCE_DURATION)
      }
  } else {
      if(silenceTimer){
          clearTimeout(silenceTimer)
          silenceTimer = null
      }
  }

  requestAnimationFrame(monitorVolume)
}

sphere.onclick = ()=>{
  if(!listening) startListening()
}
</script>

</body>
</html>
"""

@app.route("/voice", methods=["POST"])
def voice():
    try:
        if "audio" not in request.files:
            return "No audio", 400

        audio_file = request.files["audio"]
        audio_path = "/tmp/input.webm"
        audio_file.save(audio_path)

        # Transcribe
        with open(audio_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            ).text.strip()

        if len(transcript) < 3:
            tts_text = "I didn’t hear anything clearly. Please try speaking again."
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

            valid_products = [
                "Formula Exclusiva",
                "Laciador",
                "Gotero",
                "Gotika"
            ]

            if parsed.get("product") not in valid_products:
                tts_text = "Formula Exclusiva is recommended for your concern. Does that align with your goal?"
            else:
                tts_text = parsed["response"]

        # 🔥 OpenAI Real TTS
        speech_file_path = "/tmp/output.mp3"

        tts_response = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=tts_text
        )

        with open(speech_file_path, "wb") as f:
            f.write(tts_response.read())

        return send_file(
            speech_file_path,
            mimetype="audio/mpeg"
        )

    except Exception as e:
        print("TTS ERROR:", str(e))
        return "Server Error", 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
