import os
import time
from flask import Flask, request, jsonify, Response
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

PRODUCTS = {
    "Formula Exclusiva": "All-in-one natural professional salon hair treatment for dryness, frizz, breakage, damage.",
    "Laciador": "All-natural smoothing and straightening styling treatment.",
    "Gotero": "All-natural hair gel for hold and structure.",
    "Gotika": "All-natural hair color treatment for gray coverage and enhancement."
}

SYSTEM_PROMPT = """
You are Bright Clinical AI, a professional hair product advisor.

STRICT RULES:
- Ignore greetings and small talk.
- Extract only the core hair concern.
- Always select EXACTLY ONE product from:
  Formula Exclusiva, Laciador, Gotero, Gotika
- Never say "I don't know".
- If concern unclear, ask one clarifying hair-focused question.
- Keep response professional and concise.
- End by asking if recommendation matches concern.
Return JSON ONLY with:
{
  "product": "...",
  "response": "..."
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
  transition: transform 0.1s linear;
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
  analyser.fftSize = 256
  dataArray = new Uint8Array(analyser.frequencyBinCount)

  audioChunks = []
  mediaRecorder.start()
  listening = true
  statusText.innerText = "Listening..."

  mediaRecorder.ondataavailable = e => {
    audioChunks.push(e.data)
  }

  mediaRecorder.onstop = async () => {
    listening = false
    statusText.innerText = "AI Thinking..."
    await new Promise(r => setTimeout(r,3000))

    const blob = new Blob(audioChunks,{type:"audio/webm"})
    const formData = new FormData()
    formData.append("audio",blob)

    const res = await fetch("/voice",{method:"POST",body:formData})
    const data = await res.json()
    speak(data.response)
  }

  monitorVolume()
}

function monitorVolume(){
  if(!listening) return
  analyser.getByteFrequencyData(dataArray)
  let avg = dataArray.reduce((a,b)=>a+b)/dataArray.length
  pulse(1 + avg/300)

  if(avg > 25){
    if(silenceTimer) clearTimeout(silenceTimer)
    silenceTimer = setTimeout(()=>mediaRecorder.stop(),3000)
  }
  requestAnimationFrame(monitorVolume)
}

function speak(text){
  const utter = new SpeechSynthesisUtterance(text)
  utter.onstart = ()=> statusText.innerText = "AI Speaking..."
  utter.onend = ()=> statusText.innerText = "Click sphere to begin"
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
    audio_file = request.files["audio"]

    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file
    ).text

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":SYSTEM_PROMPT},
            {"role":"user","content":transcript}
        ],
        temperature=0.2
    )

    content = completion.choices[0].message.content

    return jsonify(eval(content))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
