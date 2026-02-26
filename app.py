from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI
import os, tempfile, base64

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---- MEMORY TRACKING (very light session-based logic) ----
conversation_memory = {}

@app.route("/")
def index():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Clinical AI Hair Specialist</title>
<style>
body{
    margin:0;
    background:linear-gradient(to bottom,#f8fbff,#eaf3fc);
    display:flex;
    flex-direction:column;
    align-items:center;
    justify-content:center;
    height:100vh;
    font-family:Arial;
    color:#1a2b3c;
}
h1{ margin-bottom:50px; }

#sphere{
    width:220px;
    height:220px;
    border-radius:50%;
    background:radial-gradient(circle at 30% 30%,white,#cfe6fb);
    box-shadow:0 0 40px rgba(0,140,255,0.25);
    animation:breathe 3s ease-in-out infinite;
    transition:transform .1s linear, box-shadow .1s linear;
    cursor:pointer;
}

@keyframes breathe {
    0%{ transform:scale(1); }
    50%{ transform:scale(1.05); }
    100%{ transform:scale(1); }
}

#sphere.recording{
    animation:none;
    box-shadow:0 0 60px rgba(255,0,0,0.35);
}

#sphere.processing{
    animation:none;
    box-shadow:0 0 70px rgba(0,140,255,0.5);
}

select{
    margin-top:40px;
    padding:10px 14px;
    border-radius:8px;
}

#status{
    margin-top:40px;
    max-width:450px;
    text-align:center;
    font-size:15px;
}
</style>
</head>
<body>

<h1>Clinical AI Hair Specialist</h1>
<div id="sphere"></div>

<select id="language">
<option value="en">English</option>
</select>

<div id="status">Tap Sphere to Begin Consultation</div>

<script>
let mediaRecorder;
let audioChunks=[];
let analyser;
let audioContext=new AudioContext();

const sphere=document.getElementById("sphere");
const status=document.getElementById("status");

sphere.onclick=async()=>{
    if(sphere.classList.contains("recording")){
        mediaRecorder.stop();
        return;
    }

    const stream=await navigator.mediaDevices.getUserMedia({audio:true});
    const source=audioContext.createMediaStreamSource(stream);
    analyser=audioContext.createAnalyser();
    analyser.fftSize=256;
    source.connect(analyser);

    mediaRecorder=new MediaRecorder(stream);
    audioChunks=[];

    mediaRecorder.ondataavailable=e=>audioChunks.push(e.data);

    mediaRecorder.onstop=async()=>{
        stream.getTracks().forEach(track=>track.stop());

        sphere.classList.remove("recording");
        sphere.classList.add("processing");
        status.innerText="Analyzing...";

        const blob=new Blob(audioChunks,{type:"audio/webm"});
        const formData=new FormData();
        formData.append("audio",blob);

        const response=await fetch("/process",{method:"POST",body:formData});
        const data=await response.json();

        status.innerText=data.text;

        const audio=new Audio("data:audio/mp3;base64,"+data.audio);
        audio.play();

        sphere.classList.remove("processing");
    };

    sphere.classList.add("recording");
    status.innerText="Recording... Click again to stop.";
    mediaRecorder.start();
};
</script>
</body>
</html>
""")


@app.route("/process", methods=["POST"])
def process_audio():

    audio_file = request.files["audio"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        audio_file.save(tmp.name)
        with open(tmp.name, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )

    user_text = transcript.text.strip()

    if not user_text:
        reply_text = "I did not detect a clear hair concern. Please briefly describe your hair issue so I can recommend the correct treatment."
    else:

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """
You are a clinical AI hair product specialist.

You ONLY recommend ONE of these four products:

1. Formula Exclusiva – Professional all-in-one treatment for dry, damaged, or weakened hair.
2. Laciador – Natural smoothing solution for frizz, texture control, and sleek styling.
3. Gotero – Natural hair gel for hold and structure.
4. Gotika – Natural hair color treatment.

STRICT RULES:

- Never greet.
- Never discuss non-hair topics.
- If off-topic: politely redirect to hair products.
- Always narrow vague answers.
- If user says "my hair is dry", ask ONE clarifying question such as:
  "Is the dryness accompanied by breakage, frizz, or color damage?"

- After 2 vague exchanges, choose the closest matching product and explain why.

- If still unclear after multiple attempts, say:
  "To ensure precision, I recommend contacting our professional support team for a personalized consultation. We can also restart if you'd like."

- Keep responses concise, professional, and solution-oriented.
- Always end by guiding toward ONE product OR a clear next step.
"""
                },
                {"role": "user", "content": user_text}
            ]
        )

        reply_text = completion.choices[0].message.content

    speech = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=reply_text
    )

    audio_bytes = speech.read()
    encoded = base64.b64encode(audio_bytes).decode("utf-8")

    return jsonify({"text": reply_text, "audio": encoded})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
