import os
import json
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are Bright Clinical AI, a professional hair product advisor.

STRICT RULES:
- Ignore greetings.
- Extract the core hair concern.
- ALWAYS select EXACTLY ONE product from:
  Formula Exclusiva
  Laciador
  Gotero
  Gotika
- Never leave product empty.
- If unclear, select closest product and ask clarifying question.
- Keep response concise and confident.
- End by confirming the recommendation.

Return ONLY valid JSON:

{
  "product": "Product Name",
  "response": "Professional spoken recommendation ending with confirmation question."
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
let maxDurationTimer = null
let audioContext
let analyser
let dataArray
let listening = false

// 🔧 TUNE THESE IF NEEDED
const SILENCE_THRESHOLD = 4
const SILENCE_DURATION = 3500
const MAX_RECORDING = 20000

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

    clearTimeout(maxDurationTimer)

    await new Promise(r => setTimeout(r,3000))

    const blob = new Blob(audioChunks,{type:"audio/webm"})
    const formData = new FormData()
    formData.append("audio",blob,"speech.webm")

    try {
        const res = await fetch("/voice",{method:"POST",body:formData})
        const data = await res.json()
        speak(data.response)
    } catch {
        statusText.innerText = "Server error"
    }
  }

  // Hard safety stop
  maxDurationTimer = setTimeout(()=>{
    if(listening){
      mediaRecorder.stop()
    }
  }, MAX_RECORDING)

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

function speak(text){
  const utter = new SpeechSynthesisUtterance(text)
  utter.onstart = ()=> statusText.innerText = "AI Speaking..."
  utter.onend = ()=> statusText.innerText = "Click sphere to begin"
  speechSynthesis.cancel()
  speechSynthesis.speak(utter)
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
        audio_file = request.files["audio"]

        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file.stream
        ).text

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role":"system","content":SYSTEM_PROMPT},
                {"role":"user","content":transcript}
            ],
            temperature=0.2
        )

        parsed = json.loads(completion.choices[0].message.content)

        valid_products = [
            "Formula Exclusiva",
            "Laciador",
            "Gotero",
            "Gotika"
        ]

        if parsed.get("product") not in valid_products:
            parsed["product"] = "Formula Exclusiva"
            parsed["response"] = (
                "Formula Exclusiva is recommended for your concern. "
                "Does that match your goal?"
            )

        return jsonify(parsed)

    except Exception as e:
        print("VOICE ERROR:", str(e))
        return jsonify({
            "product": "Formula Exclusiva",
            "response": "Formula Exclusiva is recommended for your concern. Does that match your goal?"
        })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
