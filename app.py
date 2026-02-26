from flask import Flask, request, jsonify, render_template_string, send_file
from openai import OpenAI
import os
import tempfile

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route("/")
def index():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Global AI Hair Intelligence</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {
                margin:0;
                background: radial-gradient(circle at center,#0f1c2e,#050a14);
                display:flex;
                justify-content:center;
                align-items:center;
                height:100vh;
                flex-direction:column;
                font-family:Arial;
                color:white;
            }

            #halo {
                width:220px;
                height:220px;
                border-radius:50%;
                border:6px solid rgba(0,170,255,0.35);
                box-shadow:0 0 40px rgba(0,170,255,0.5);
                cursor:pointer;
                transition:all .3s ease;
            }

            #halo.recording {
                border-color:rgba(255,0,0,0.8);
                box-shadow:0 0 60px rgba(255,0,0,0.8);
            }

            #halo.processing {
                animation:rotate 2s linear infinite;
            }

            @keyframes rotate {
                from { transform:rotate(0deg); }
                to { transform:rotate(360deg); }
            }

            select {
                margin-top:20px;
                padding:8px;
                border-radius:8px;
                border:none;
            }

            #status {
                margin-top:20px;
                opacity:0.9;
            }
        </style>
    </head>
    <body>

        <div id="halo"></div>

        <select id="language">
            <option value="en">English</option>
            <option value="es">Spanish</option>
            <option value="fr">French</option>
            <option value="de">German</option>
            <option value="pt">Portuguese</option>
            <option value="it">Italian</option>
            <option value="zh">Chinese</option>
            <option value="ar">Arabic</option>
        </select>

        <div id="status">Click Halo to Speak</div>

        <script>
            let mediaRecorder;
            let audioChunks = [];

            const halo = document.getElementById("halo");
            const status = document.getElementById("status");
            const languageSelect = document.getElementById("language");

            halo.onclick = async () => {

                if (halo.classList.contains("recording")) {
                    mediaRecorder.stop();
                    return;
                }

                const stream = await navigator.mediaDevices.getUserMedia({ audio:true });

                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];

                mediaRecorder.ondataavailable = e => {
                    audioChunks.push(e.data);
                };

                mediaRecorder.onstop = async () => {
                    const blob = new Blob(audioChunks, { type:'audio/webm' });

                    halo.classList.remove("recording");
                    halo.classList.add("processing");
                    status.innerText = "Processing...";

                    const formData = new FormData();
                    formData.append("audio", blob);
                    formData.append("language", languageSelect.value);

                    const response = await fetch("/process", {
                        method:"POST",
                        body:formData
                    });

                    const data = await response.json();

                    status.innerText = data.text;

                    const audio = new Audio("data:audio/mp3;base64," + data.audio);
                    audio.play();

                    halo.classList.remove("processing");
                };

                mediaRecorder.start();
                halo.classList.add("recording");
                status.innerText = "Recording...";
            };
        </script>

    </body>
    </html>
    """
    return render_template_string(html)


@app.route("/process", methods=["POST"])
def process_audio():
    audio_file = request.files["audio"]
    language = request.form.get("language","en")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        audio_file.save(tmp.name)

        # 1️⃣ Transcribe with Whisper
        with open(tmp.name, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )

    user_text = transcript.text

    # 2️⃣ GPT Response
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":"You are a professional salon hair expert."},
            {"role":"user","content":user_text}
        ]
    )

    reply_text = completion.choices[0].message.content

    # 3️⃣ Neural TTS
    speech = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=reply_text
    )

    audio_bytes = speech.read()

    import base64
    encoded_audio = base64.b64encode(audio_bytes).decode("utf-8")

    return jsonify({
        "text": reply_text,
        "audio": encoded_audio
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0", port=port)
