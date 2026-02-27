import os
import json
from flask import Flask, request, send_file, Response
from openai import OpenAI

app = Flask(__name__)

client = None

VALID_PRODUCTS = [
    "Formula Exclusiva",
    "Laciador",
    "Gotero",
    "Gotika"
]

HAIR_KEYWORDS = [
    "hair","dry","frizz","frizzy","damage","damaged",
    "thin","thinning","break","breaking","loss",
    "smooth","volume","brittle","scalp","growth",
    "repair","hydration","fall","shedding"
]

SYSTEM_PROMPT = """
You are Bright Clinical AI.

Analyze the hair concern.
Recommend exactly ONE product from:
Formula Exclusiva, Laciador, Gotero, Gotika

Be confident and concise.

Return JSON:
{"product":"...","response":"..."}
"""

@app.route("/")
def home():
    return """
    <html>
    <head>
    <title>Bright Clinical AI</title>
    <style>
    body{
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
    #sphere{
        width:200px;
        height:200px;
        border-radius:50%;
        background: radial-gradient(circle at 30% 30%, #00f0ff, #0044ff);
        box-shadow: 0 0 80px rgba(0,200,255,0.9);
        cursor:pointer;
    }
    #status{margin-top:20px;}
    </style>
    </head>
    <body>

    <div id="sphere"></div>
    <div id="status">Click sphere to speak (5 sec)</div>

    <script>
    let mediaRecorder
    let audioChunks = []
    let listening = false

    const sphere = document.getElementById("sphere")
    const statusText = document.getElementById("status")

    sphere.onclick = async () => {
        if(listening) return

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

            const res = await fetch("/voice",{method:"POST",body:formData})

            if(res.status === 204){
                statusText.innerText = "Click sphere to speak"
                return
            }

            if(!res.ok){
                statusText.innerText = "Error occurred"
                return
            }

            const audioBlob = await res.blob()
            const audioUrl = URL.createObjectURL(audioBlob)
            const audio = new Audio(audioUrl)

            statusText.innerText = "AI Speaking..."
            audio.play()

            audio.onended = ()=>{
                statusText.innerText = "Click sphere to speak"
            }
        }

        setTimeout(()=>{
            if(listening){
                mediaRecorder.stop()
            }
        },5000)
    }
    </script>

    </body>
    </html>
    """

@app.route("/voice", methods=["POST"])
def voice():
    global client

    try:
        if client is None:
            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        if "audio" not in request.files:
            return Response(status=400)

        audio_file = request.files["audio"]
        audio_path = "/tmp/input.webm"
        audio_file.save(audio_path)

        # 🔹 TRANSCRIBE
        with open(audio_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            ).text.strip()

        print("TRANSCRIPT:", transcript)

        clean = transcript.lower().strip()
        words = clean.split()

        filler_words = [
            "uh","um","okay","ok",
            "thanks","thank you","hmm"
        ]

        # 🔹 REALISTIC SILENCE FILTER
        if (
            clean == "" or
            len(words) < 2 or
            clean in filler_words
        ):
            print("Rejected as silence")
            return Response(status=204)

        # 🔹 Must contain at least one hair keyword
        if not any(k in clean for k in HAIR_KEYWORDS):
            print("No hair concern detected")
            return Response(status=204)

        # 🔹 GPT CALL
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type":"json_object"},
            messages=[
                {"role":"system","content":SYSTEM_PROMPT},
                {"role":"user","content":transcript}
            ]
        )

        parsed = json.loads(completion.choices[0].message.content)

        if parsed.get("product") not in VALID_PRODUCTS:
            return Response(status=204)

        response_text = parsed["response"]

        # 🔹 TEXT TO SPEECH
        speech_path = "/tmp/output.mp3"

        tts = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=response_text
        )

        with open(speech_path,"wb") as f:
            f.write(tts.read())

        return send_file(speech_path, mimetype="audio/mpeg")

    except Exception as e:
        print("ERROR:", e)
        return Response(status=500)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
