import os
import json
from flask import Flask, request, send_file
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are Bright Clinical AI, a decisive professional hair product advisor.

RULES:
- Extract the core hair concern.
- Infer the most likely issue if vague.
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

  // Auto stop after fixed time
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

@app.route("/voice", methods=["POST"])
def voice():
    try:
        if "audio" not in request.files:
            return "No audio", 400

        audio_file = request.files["audio"]
        audio_path = "/tmp/input.webm"
        audio_file.save(audio_path)

        with open(audio_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            ).text.strip()

        if len(transcript) < 3:
            tts_text = "I didn’t hear anything clearly. Please try again."
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

        speech_file_path = "/tmp/output.mp3"

        tts_response = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=tts_text
        )

        with open(speech_file_path, "wb") as f:
            f.write(tts_response.read())

        return send_file(speech_file_path, mimetype="audio/mpeg")

    except Exception as e:
        print("ERROR:", str(e))
        return "Server Error", 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
