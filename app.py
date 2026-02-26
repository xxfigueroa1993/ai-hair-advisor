from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI
import os, tempfile, base64

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route("/")
def index():
    html = """
<!DOCTYPE html>
<html>
<head>
<title>Global Clinical Hair Intelligence</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>

body{
    margin:0;
    background:linear-gradient(to bottom,#f4f9ff,#e6f1fb);
    display:flex;
    justify-content:center;
    align-items:center;
    height:100vh;
    flex-direction:column;
    font-family:Arial;
    color:#1a2b3c;
}

h1{
    font-weight:600;
    letter-spacing:1px;
}

#halo-container{
    perspective:800px;
}

#halo{
    width:220px;
    height:220px;
    border-radius:50%;
    border:6px solid rgba(0,120,255,0.25);
    background:radial-gradient(circle at center,rgba(255,255,255,0.8),rgba(200,230,255,0.3));
    box-shadow:0 0 40px rgba(0,140,255,0.2);
    cursor:pointer;
    transition:all .2s ease;
    transform-style:preserve-3d;
}

#halo.recording{
    border-color:rgba(255,0,0,0.6);
    box-shadow:0 0 60px rgba(255,0,0,0.3);
}

#halo.processing{
    animation:rotate 2s linear infinite;
}

@keyframes rotate{
    from{ transform:rotateY(0deg); }
    to{ transform:rotateY(360deg); }
}

select{
    margin-top:20px;
    padding:8px 12px;
    border-radius:8px;
    border:1px solid #cde0f5;
    background:white;
}

#status{
    margin-top:25px;
    font-size:16px;
    opacity:0.8;
    max-width:400px;
    text-align:center;
}

</style>
</head>
<body>

<h1>Clinical AI Hair Specialist</h1>

<div id="halo-container">
    <div id="halo"></div>
</div>

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

<div id="status">Tap Halo to Begin Consultation</div>

<script>

let mediaRecorder;
let audioChunks=[];
let analyser;
let silenceTimer;
const SILENCE_THRESHOLD = 20;
const SILENCE_TIME = 1500;

const halo=document.getElementById("halo");
const status=document.getElementById("status");
const languageSelect=document.getElementById("language");

halo.onclick=async()=>{

    if(halo.classList.contains("recording")){
        mediaRecorder.stop();
        return;
    }

    const stream=await navigator.mediaDevices.getUserMedia({audio:true});
    const audioContext=new AudioContext();
    const source=audioContext.createMediaStreamSource(stream);
    analyser=audioContext.createAnalyser();
    source.connect(analyser);
    analyser.fftSize=256;

    mediaRecorder=new MediaRecorder(stream);
    audioChunks=[];

    monitorSilence();

    mediaRecorder.ondataavailable=e=>{
        audioChunks.push(e.data);
    };

    mediaRecorder.onstop=async()=>{
        halo.classList.remove("recording");
        halo.classList.add("processing");
        status.innerText="Analyzing...";

        const blob=new Blob(audioChunks,{type:"audio/webm"});
        const formData=new FormData();
        formData.append("audio",blob);
        formData.append("language",languageSelect.value);

        const response=await fetch("/process",{method:"POST",body:formData});
        const data=await response.json();

        status.innerText=data.text;

        const audio=new Audio("data:audio/mp3;base64,"+data.audio);
        audio.play();

        halo.classList.remove("processing");
    };

    mediaRecorder.start();
    halo.classList.add("recording");
    status.innerText="Listening...";
};

function monitorSilence(){
    const bufferLength=analyser.frequencyBinCount;
    const dataArray=new Uint8Array(bufferLength);

    function detect(){
        analyser.getByteFrequencyData(dataArray);
        let avg=dataArray.reduce((a,b)=>a+b)/bufferLength;

        halo.style.boxShadow="0 0 "+(avg*2)+"px rgba(0,140,255,0.4)";

        if(avg<SILENCE_THRESHOLD){
            if(!silenceTimer){
                silenceTimer=setTimeout(()=>{
                    mediaRecorder.stop();
                },SILENCE_TIME);
            }
        } else{
            clearTimeout(silenceTimer);
            silenceTimer=null;
        }

        if(mediaRecorder.state==="recording"){
            requestAnimationFrame(detect);
        }
    }

    detect();
}

</script>

</body>
</html>
"""
    return render_template_string(html)


@app.route("/process", methods=["POST"])
def process_audio():
    audio_file=request.files["audio"]
    language=request.form.get("language","en")

    with tempfile.NamedTemporaryFile(delete=False,suffix=".webm") as tmp:
        audio_file.save(tmp.name)

        with open(tmp.name,"rb") as f:
            transcript=client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )

    user_text=transcript.text

    completion=client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role":"system",
                "content":"""
You are an elite clinical salon hair expert.

Rules:
- Do NOT greet.
- Immediately provide a hair solution.
- Recommend a professional product solution.
- If unrelated to hair reply:
"I am a Professional Salon Hair Expert here to recommend advanced hair solutions available through our company support."
"""
            },
            {"role":"user","content":user_text}
        ]
    )

    reply_text=completion.choices[0].message.content

    # Emotion-aware adjustment
    voice="alloy"
    if "damage" in reply_text.lower():
        voice="verse"

    speech=client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice=voice,
        input=reply_text
    )

    audio_bytes=speech.read()
    encoded=base64.b64encode(audio_bytes).decode("utf-8")

    return jsonify({"text":reply_text,"audio":encoded})


if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
