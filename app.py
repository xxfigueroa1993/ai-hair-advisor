import os
from flask import Flask, request, send_file, Response
from openai import OpenAI

app = Flask(__name__)

client = None

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
                box-shadow: 0 0 80px rgba(0,200,255,0.9);
                cursor:pointer;
            }
            #status { margin-top:20px; }
        </style>
    </head>
    <body>

        <div id="sphere"></div>
        <div id="status">Click sphere to speak</div>

        <script>
            let mediaRecorder
            let audioChunks = []
            let listening = false

            const sphere = document.getElementById("sphere")
            const statusText = document.getElementById("status")

            sphere.onclick = async () => {

                if(listening) return

                const stream = await navigator.mediaDevices.getUserMedia({audio:true})

                mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" })

                audioChunks = []
                mediaRecorder.start()
                listening = true
                statusText.innerText = "Listening..."

                mediaRecorder.ondataavailable = e => {
                    if(e.data.size > 0){
                        audioChunks.push(e.data)
                    }
                }

                mediaRecorder.onstop = async () => {

                    listening = false
                    statusText.innerText = "AI thinking..."

                    const blob = new Blob(audioChunks,{type:"audio/webm"})

                    if(blob.size < 1000){
                        statusText.innerText = "No speech detected"
                        return
                    }

                    const formData = new FormData()
                    formData.append("audio", blob, "speech.webm")

                    try{
                        const res = await fetch("/voice",{
                            method:"POST",
                            body:formData
                        })

                        if(res.status === 204){
                            statusText.innerText = "No speech detected"
                            return
                        }

                        if(!res.ok){
                            statusText.innerText = "Server error"
                            return
                        }

                        const audioBlob = await res.blob()
                        const audioUrl = URL.createObjectURL(audioBlob)
                        const audio = new Audio(audioUrl)

                        statusText.innerText = "AI speaking..."
                        audio.play()

                        audio.onended = () => {
                            statusText.innerText = "Click sphere to speak"
                        }

                    } catch(e){
                        statusText.innerText = "Error occurred"
                    }
                }

                setTimeout(()=>{
                    if(listening){
                        mediaRecorder.stop()
                    }
                }, 5000)
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

        print("VOICE endpoint hit")

        if "audio" not in request.files:
            print("No audio file received")
            return Response(status=400)

        audio_file = request.files["audio"]
        audio_path = "/tmp/input.webm"
        audio_file.save(audio_path)

        size = os.path.getsize(audio_path)
        print("Audio file size:", size)

        if size < 1000:
            print("Audio too small — likely silence")
            return Response(status=204)

        # 🔹 Transcribe with Whisper
        with open(audio_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            ).text.strip()

        print("RAW TRANSCRIPT:", transcript)

        if transcript == "":
            print("Whisper returned empty transcript")
            return Response(status=204)

        # 🔹 Ask GPT
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role":"system",
                    "content":"User describes a hair issue. Recommend the best product clearly and confidently."
                },
                {
                    "role":"user",
                    "content": transcript
                }
            ]
        )

        response_text = completion.choices[0].message.content
        print("GPT RESPONSE:", response_text)

        # 🔹 Convert to Speech
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
