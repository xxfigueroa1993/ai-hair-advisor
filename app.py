from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI
import os, tempfile, base64

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

h1{
    margin-bottom:50px;
    font-weight:600;
}

#sphere{
    width:220px;
    height:220px;
    border-radius:50%;
    background:radial-gradient(circle at 30% 30%,white,#cfe6fb);
    box-shadow:0 0 40px rgba(0,140,255,0.25);
    transition:transform .08s linear, box-shadow .08s linear;
    cursor:pointer;
}

#sphere.recording{
    box-shadow:0 0 60px rgba(255,0,0,0.35);
}

#sphere.processing{
    box-shadow:0 0 70px rgba(0,140,255,0.5);
}

select{
    margin-top:40px;
    padding:10px 14px;
    border-radius:8px;
    border:1px solid #cde0f5;
    background:white;
}

#status{
    margin-top:40px;
    max-width:420px;
    text-align:center;
    font-size:15px;
    opacity:0.85;
}
</style>
</head>
<body>

<h1>Clinical AI Hair Specialist</h1>

<div id="sphere"></div>

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

<div id="status">Tap Sphere to Begin Consultation</div>

<script>

let mediaRecorder;
let audioChunks=[];
let analyser;
let silenceTimer=null;
let audioContext;
let recordingStartTime=0;

const sphere=document.getElementById("sphere");
const status=document.getElementById("status");
const language=document.getElementById("language");

const SILENCE_THRESHOLD = 22;
const SILENCE_TIME = 2200;
const MIN_RECORD_TIME = 800;

let currentScale=1;

sphere.onclick = async ()=>{

    if(sphere.classList.contains("recording")){
        mediaRecorder.stop();
        return;
    }

    const stream = await navigator.mediaDevices.getUserMedia({audio:true});
    audioContext = new AudioContext();
    const source = audioContext.createMediaStreamSource(stream);

    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);

    mediaRecorder = new MediaRecorder(stream);
    audioChunks=[];
    silenceTimer=null;
    recordingStartTime=Date.now();

    mediaRecorder.ondataavailable=e=>audioChunks.push(e.data);

    mediaRecorder.onstop = async ()=>{

        stream.getTracks().forEach(track=>track.stop());
        audioContext.close();

        sphere.classList.remove("recording");
        sphere.classList.add("processing");
        status.innerText="Analyzing...";

        const blob=new Blob(audioChunks,{type:"audio/webm"});
        const formData=new FormData();
        formData.append("audio",blob);
        formData.append("language",language.value);

        const response=await fetch("/process",{method:"POST",body:formData});
        const data=await response.json();

        status.innerText=data.text;

        const audio=new Audio("data:audio/mp3;base64,"+data.audio);
        syncVoicePulse(audio);
        audio.play();

        sphere.classList.remove("processing");
    };

    mediaRecorder.start();
    sphere.classList.add("recording");
    status.innerText="Listening...";

    monitorMic();
};

function monitorMic(){
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    function detect(){
        if(!mediaRecorder || mediaRecorder.state!=="recording") return;

        analyser.getByteFrequencyData(dataArray);
        let avg=dataArray.reduce((a,b)=>a+b)/bufferLength;

        updateScale(avg/180);

        if(avg < SILENCE_THRESHOLD){

            if(!silenceTimer && Date.now()-recordingStartTime > MIN_RECORD_TIME){
                silenceTimer=setTimeout(()=>{
                    if(mediaRecorder.state==="recording"){
                        mediaRecorder.stop();
                    }
                },SILENCE_TIME);
            }

        }else{
            clearTimeout(silenceTimer);
            silenceTimer=null;
        }

        requestAnimationFrame(detect);
    }
    detect();
}

function syncVoicePulse(audio){

    const ctx=new AudioContext();
    const src=ctx.createMediaElementSource(audio);
    const analyserVoice=ctx.createAnalyser();
    analyserVoice.fftSize=256;

    src.connect(analyserVoice);
    analyserVoice.connect(ctx.destination);

    const bufferLength=analyserVoice.frequencyBinCount;
    const dataArray=new Uint8Array(bufferLength);

    function pulse(){
        analyserVoice.getByteFrequencyData(dataArray);
        let avg=dataArray.reduce((a,b)=>a+b)/bufferLength;
        updateScale(avg/250);

        if(!audio.paused){
            requestAnimationFrame(pulse);
        }
    }
    pulse();
}

function updateScale(intensity){
    currentScale = 1 + intensity;
    sphere.style.transform = "scale("+currentScale+")";
    sphere.style.boxShadow = "0 0 "+(40 + intensity*120)+"px rgba(0,140,255,0.35)";
}

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
        reply_text = "Please describe your hair concern clearly so I can recommend a clinical solution."
    else:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role":"system",
                    "content":"""
You are an elite clinical salon hair expert.

Do not greet.
Provide direct hair solutions.
Recommend a professional product.
Only redirect if clearly unrelated to hair care.
"""
                },
                {"role":"user","content":user_text}
            ]
        )
        reply_text = completion.choices[0].message.content

    speech=client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=reply_text
    )

    audio_bytes=speech.read()
    encoded=base64.b64encode(audio_bytes).decode("utf-8")

    return jsonify({"text":reply_text,"audio":encoded})


if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
