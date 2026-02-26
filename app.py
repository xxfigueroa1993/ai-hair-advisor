from flask import Flask, request, Response, render_template_string
from openai import OpenAI
import os
import hashlib

app = Flask(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ==========================
# CREATE LOCAL CACHE FOLDER
# ==========================

CACHE_FOLDER = "audio_cache"
os.makedirs(CACHE_FOLDER, exist_ok=True)

# ==========================
# SYSTEM PROMPT
# ==========================

SYSTEM_PROMPT = """
You are a Professional Salon Hair Expert.

Only answer hair-related questions.

If asked anything outside hair, respond:
"I am a Professional Salon Hair Expert here to recommend hair solutions available within our company support. How may I assist you with your hair needs today?"

Always guide toward:

1. Formula Exclusiva – Deep repair & professional restoration.
2. Laciador – Advanced smoothing & frizz control.
3. Gotero – Scalp strengthening & growth-focused care.
4. Gotika – Intensive hydration luxury treatment.
"""

# ==========================
# HELPER FUNCTION
# ==========================

def generate_cache_key(text):
    return hashlib.sha256(text.encode()).hexdigest() + ".mp3"

# ==========================
# FRONTEND
# ==========================

HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Professional Hair AI</title>
<style>
body { margin:0; text-align:center; font-family:Arial; background:#ffffff; }
canvas { margin-top:80px; }
</style>
</head>
<body>

<h2>Professional Hair AI</h2>
<canvas id="ring" width="300" height="300"></canvas>

<script>
let canvas = document.getElementById("ring");
let ctx = canvas.getContext("2d");

function draw() {
    ctx.clearRect(0,0,300,300);
    ctx.beginPath();
    ctx.arc(150,150,100,0,2*Math.PI);
    ctx.strokeStyle="#d4af37";
    ctx.lineWidth=4;
    ctx.stroke();
}

draw();

canvas.addEventListener("click", async () => {

    const stream = await navigator.mediaDevices.getUserMedia({audio:true});
    const recorder = new MediaRecorder(stream);
    let chunks=[];

    recorder.ondataavailable=e=>chunks.push(e.data);

    recorder.onstop=async()=>{
        let blob=new Blob(chunks,{type:"audio/webm"});
        let form=new FormData();
        form.append("audio",blob);

        let response=await fetch("/voice",{method:"POST",body:form});
        let audioBlob=await response.blob();
        let audio=new Audio(URL.createObjectURL(audioBlob));
        audio.play();
    };

    recorder.start();
    setTimeout(()=>recorder.stop(),4000);
});
</script>
</body>
</html>
"""

# ==========================
# ROUTES
# ==========================

@app.route("/")
def home():
    return render_template_string(HTML)

@app.route("/voice", methods=["POST"])
def voice():

    audio_file = request.files["audio"]

    # 1️⃣ Transcribe
    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file
    )

    user_text = transcript.text

    # 2️⃣ GPT
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role":"system","content":SYSTEM_PROMPT},
            {"role":"user","content":user_text}
        ]
    )

    reply = completion.choices[0].message.content

    # 3️⃣ Generate cache filename
    cache_key = generate_cache_key(reply)
    file_path = os.path.join(CACHE_FOLDER, cache_key)

    # 4️⃣ If file exists → return instantly
    if os.path.exists(file_path):
        print("Serving from local cache")
        return Response(open(file_path, "rb").read(), mimetype="audio/mpeg")

    # 5️⃣ Generate TTS
    print("Generating new TTS")
    speech = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=reply
    )

    audio_bytes = speech.read()

    # 6️⃣ Save locally
    with open(file_path, "wb") as f:
        f.write(audio_bytes)

    return Response(audio_bytes, mimetype="audio/mpeg")

# ==========================

if __name__ == "__main__":
    app.run(debug=True)
