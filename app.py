import os
import tempfile
import base64
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

PRODUCTS = {
    "Laciador": "$34.99",
    "Gotero": "$29.99",
    "Volumizer": "$39.99",
    "Formula Exclusiva": "$49.99"
}

def route_product(text):
    t = text.lower()

    if any(x in t for x in ["event","party","wedding","date","sleek","smooth","frizz","bounce","bouncy"]):
        return "Laciador"

    if any(x in t for x in ["oily","greasy"]):
        return "Gotero"

    if any(x in t for x in ["thin","thinning","hair loss","bald","falling out"]):
        return "Volumizer"

    return "Formula Exclusiva"


@app.route("/")
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<title>AI Halo</title>
<style>
body{
margin:0;height:100vh;
display:flex;justify-content:center;
align-items:center;background:#000;
flex-direction:column;font-family:Arial;
color:white;
}

.halo{
width:260px;height:260px;
border-radius:50%;
cursor:pointer;
position:relative;
backdrop-filter: blur(30px);
}

#response{
margin-top:40px;
width:70%;
text-align:center;
font-size:18px;
}
</style>
</head>
<body>

<div id="halo" class="halo"></div>
<div id="response">Tap to speak.</div>

<script>

const halo=document.getElementById("halo");

let state="idle";
let audioElement=null;
let speakLock=false;
let silenceTimer=null;

let current=[0,255,200];
let target=[0,255,200];
let intensity=0.5;
let targetIntensity=0.5;
let pulse=1;
let pulseTarget=1;

function lerp(a,b,t){return a+(b-a)*t;}

function animate(){

    for(let i=0;i<3;i++)
        current[i]=lerp(current[i],target[i],0.05);

    intensity=lerp(intensity,targetIntensity,0.05);
    pulse=lerp(pulse,pulseTarget,0.15);

    halo.style.background=
    `
    radial-gradient(circle at center,
        rgba(${current[0]},${current[1]},${current[2]},${intensity}) 0%,
        rgba(${current[0]},${current[1]},${current[2]},${intensity*0.6}) 35%,
        rgba(${current[0]},${current[1]},${current[2]},${intensity*0.25}) 55%,
        transparent 75%)
    `;

    halo.style.boxShadow=
    `
    0 0 80px rgba(${current[0]},${current[1]},${current[2]},${intensity*0.6}),
    0 0 140px rgba(${current[0]},${current[1]},${current[2]},${intensity*0.4})
    `;

    halo.style.transform=`scale(${pulse})`;

    requestAnimationFrame(animate);
}
animate();

function smoothReset(){
    state="idle";
    target=[0,255,200];
    targetIntensity=0.5;
    pulseTarget=1;
}

function hardAudioStop(){
    if(audioElement){
        audioElement.pause();
        audioElement.src="";
        audioElement=null;
    }
    speakLock=false;
}

halo.addEventListener("click",()=>{

    hardAudioStop();
    smoothReset();

    if(state==="idle"){
        startListening();
    }
});

async function startListening(){

    state="listening";
    target=[255,200,0];
    targetIntensity=1.1;

    const stream=await navigator.mediaDevices.getUserMedia({audio:true});
    const audioCtx=new AudioContext();
    const analyser=audioCtx.createAnalyser();
    analyser.fftSize=256;
    const src=audioCtx.createMediaStreamSource(stream);
    src.connect(analyser);

    const recorder=new MediaRecorder(stream);
    let chunks=[];
    recorder.ondataavailable=e=>chunks.push(e.data);

    recorder.onstop=async()=>{

        state="thinking";
        target=[0,255,255];
        targetIntensity=1.1;

        stream.getTracks().forEach(t=>t.stop());

        const blob=new Blob(chunks,{type:"audio/webm"});
        const form=new FormData();
        form.append("audio",blob);

        const res=await fetch("/voice",{method:"POST",body:form});
        const data=await res.json();

        document.getElementById("response").innerText=data.text;
        speakAI(data.audio);
    };

    recorder.start();

    function detect(){

        if(state!=="listening") return;

        const data=new Uint8Array(analyser.frequencyBinCount);
        analyser.getByteFrequencyData(data);
        let volume=data.reduce((a,b)=>a+b)/data.length;

        pulseTarget=1+volume/120;

        if(volume<5){
            if(!silenceTimer){
                silenceTimer=setTimeout(()=>{
                    target=[0,255,255]; // GOLD -> TEAL fade
                    recorder.stop();
                },2000);
            }
        }else{
            clearTimeout(silenceTimer);
            silenceTimer=null;
        }

        requestAnimationFrame(detect);
    }

    detect();
}

function speakAI(b64){

    if(speakLock) return;
    speakLock=true;

    state="speaking";

    audioElement=new Audio("data:audio/mp3;base64,"+b64);

    const ctx=new AudioContext();
    const src=ctx.createMediaElementSource(audioElement);
    const analyser=ctx.createAnalyser();
    analyser.fftSize=256;
    src.connect(analyser);
    analyser.connect(ctx.destination);

    audioElement.play();

    function react(){
        if(state!=="speaking") return;
        const data=new Uint8Array(analyser.frequencyBinCount);
        analyser.getByteFrequencyData(data);
        let volume=data.reduce((a,b)=>a+b)/data.length;
        pulseTarget=1+volume/130;
        requestAnimationFrame(react);
    }

    react();

    audioElement.onended=()=>{
        speakLock=false;
        smoothReset();
    };
}

</script>
</body>
</html>
"""

@app.route("/voice", methods=["POST"])
def voice():
    file=request.files["audio"]

    with tempfile.NamedTemporaryFile(delete=False,suffix=".webm") as temp:
        file.save(temp.name)
        path=temp.name

    with open(path,"rb") as audio_file:
        transcript=client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text"
        )

    msg=f"We recommend {route_product(transcript)} for your needs."

    speech=client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=msg
    )

    audio_bytes=speech.read()

    return jsonify({
        "text":msg,
        "audio":base64.b64encode(audio_bytes).decode("utf-8")
    })


if __name__=="__main__":
    app.run(host="0.0.0.0",port=10000)
