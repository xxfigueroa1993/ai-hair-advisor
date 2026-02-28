import os
import tempfile
import base64
from flask import Flask, request, jsonify
from openai import OpenAI

os.environ["PYTHONUNBUFFERED"] = "1"

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# =====================================================
# FRONTEND
# =====================================================

@app.route("/", methods=["GET"])
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<title>AI Hair Advisor</title>
<style>
body{
    margin:0;
    height:100vh;
    display:flex;
    justify-content:center;
    align-items:center;
    flex-direction:column;
    background:radial-gradient(circle at center,#0b1114 0%,#000 100%);
    font-family:Arial;
    color:white;
}
.halo{
    width:220px;
    height:220px;
    border-radius:50%;
    cursor:pointer;
    background:radial-gradient(circle at center,
        rgba(0,255,200,0.35) 0%,
        rgba(0,255,200,0.18) 50%,
        rgba(0,255,200,0.08) 75%,
        transparent 95%);
    box-shadow:0 0 80px rgba(0,255,200,0.35);
    transform:scale(1);
    transition:box-shadow 0.1s linear;
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
<div id="response">Tap the ring and describe your hair concern.</div>

<script>

const halo=document.getElementById("halo");
let state="idle";
let mediaRecorder=null;
let stream=null;
let silenceTimer=null;
let analyser=null;
let audioCtx=null;
let aiAnalyser=null;
let audioElement=null;

const SILENCE_DELAY=2300;
const SILENCE_THRESHOLD=6;

// -----------------------------------------------------
// COLOR ENGINE
// -----------------------------------------------------

function lerp(a,b,t){return a+(b-a)*t;}

function fade(from,to,duration){
    let start=null;
    function step(ts){
        if(!start)start=ts;
        let p=(ts-start)/duration;
        if(p>1)p=1;
        let r=lerp(from.r,to.r,p);
        let g=lerp(from.g,to.g,p);
        let b=lerp(from.b,to.b,p);
        let a=lerp(from.a,to.a,p);
        halo.style.background=`radial-gradient(circle at center,
            rgba(${r},${g},${b},${a}) 0%,
            rgba(${r},${g},${b},${a*0.5}) 50%,
            rgba(${r},${g},${b},${a*0.2}) 75%,
            transparent 95%)`;
        if(p<1)requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
}

const idleColor={r:0,g:255,b:200,a:0.35};
const goldColor={r:255,g:200,b:0,a:0.6};
const brightTeal={r:0,g:255,b:255,a:0.95};

// -----------------------------------------------------
// AUDIO REACTIVE PULSE
// -----------------------------------------------------

function reactivePulse(analyserNode){
    if(!analyserNode) return;

    const data = new Uint8Array(analyserNode.frequencyBinCount);
    analyserNode.getByteFrequencyData(data);

    let sum=0;
    for(let i=0;i<data.length;i++) sum+=data[i];
    let volume = sum/data.length;

    let intensity = Math.min(volume/120,1);
    let scale = 1 + intensity*0.25;
    let glow = 80 + intensity*120;

    halo.style.transform = `scale(${scale})`;
    halo.style.boxShadow = `0 0 ${glow}px rgba(0,255,255,0.6)`;

    if(state==="listening" || state==="speaking"){
        requestAnimationFrame(()=>reactivePulse(analyserNode));
    }
}

function idlePulse(){
    if(state!=="idle") return;
    let scale=1+Math.sin(Date.now()*0.002)*0.03;
    halo.style.transform=`scale(${scale})`;
    requestAnimationFrame(idlePulse);
}

// -----------------------------------------------------
// SOUNDS
// -----------------------------------------------------

function playClick(){
    const ctx=new (window.AudioContext||window.webkitAudioContext)();
    const osc=ctx.createOscillator();
    const gain=ctx.createGain();
    osc.frequency.setValueAtTime(320,ctx.currentTime);
    osc.frequency.linearRampToValueAtTime(600,ctx.currentTime+0.8);
    gain.gain.setValueAtTime(0.0001,ctx.currentTime);
    gain.gain.linearRampToValueAtTime(0.3,ctx.currentTime+0.4);
    gain.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+1.3);
    osc.connect(gain);gain.connect(ctx.destination);
    osc.start();osc.stop(ctx.currentTime+1.3);
}

function playEndTone(){
    const ctx=new (window.AudioContext||window.webkitAudioContext)();
    const osc=ctx.createOscillator();
    const gain=ctx.createGain();
    osc.type="triangle";
    osc.frequency.setValueAtTime(900,ctx.currentTime);
    osc.frequency.linearRampToValueAtTime(250,ctx.currentTime+2.5);
    gain.gain.setValueAtTime(0.3,ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.0001,ctx.currentTime+2.5);
    osc.connect(gain);gain.connect(ctx.destination);
    osc.start();osc.stop(ctx.currentTime+2.5);
}

// -----------------------------------------------------
// STATES
// -----------------------------------------------------

function fullReset(){
    state="idle";
    fade(brightTeal,idleColor,4000);
    idlePulse();
}

halo.addEventListener("click",()=>{
    playClick();
    if(state!=="idle"){fullReset();return;}
    startRecording();
});

async function startRecording(){
    state="listening";
    fade(idleColor,goldColor,5000);

    stream=await navigator.mediaDevices.getUserMedia({audio:true});
    audioCtx=new (window.AudioContext||window.webkitAudioContext)();
    analyser=audioCtx.createAnalyser();
    analyser.fftSize=256;
    const source=audioCtx.createMediaStreamSource(stream);
    source.connect(analyser);

    mediaRecorder=new MediaRecorder(stream);
    let chunks=[];

    mediaRecorder.ondataavailable=e=>chunks.push(e.data);

    mediaRecorder.onstop=async()=>{
        state="thinking";
        fade(goldColor,brightTeal,5000);

        const blob=new Blob(chunks,{type:"audio/webm"});
        const form=new FormData();
        form.append("audio",blob);

        const res=await fetch("/voice",{method:"POST",body:form});
        const data=await res.json();
        document.getElementById("response").innerText=data.text;

        speakAI(data.audio);
    };

    mediaRecorder.start();
    reactivePulse(analyser);
    detectSilence();
}

function detectSilence(){
    if(!analyser)return;
    const data=new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(data);
    let sum=0;
    for(let i=0;i<data.length;i++)sum+=data[i];
    let volume=sum/data.length;

    if(volume<SILENCE_THRESHOLD){
        if(!silenceTimer){
            silenceTimer=setTimeout(()=>{
                if(mediaRecorder && mediaRecorder.state==="recording"){
                    mediaRecorder.stop();
                }
            },SILENCE_DELAY);
        }
    }else{
        if(silenceTimer){clearTimeout(silenceTimer);silenceTimer=null;}
    }

    if(state==="listening")requestAnimationFrame(detectSilence);
}

function speakAI(base64Audio){
    state="speaking";
    audioElement=new Audio("data:audio/mp3;base64,"+base64Audio);

    const ctx=new (window.AudioContext||window.webkitAudioContext)();
    const source=ctx.createMediaElementSource(audioElement);
    aiAnalyser=ctx.createAnalyser();
    aiAnalyser.fftSize=256;
    source.connect(aiAnalyser);
    aiAnalyser.connect(ctx.destination);

    audioElement.play();
    reactivePulse(aiAnalyser);

    audioElement.onended=()=>{
        playEndTone();
        setTimeout(()=>{fullReset();},3000);
    };
}

idlePulse();

</script>
</body>
</html>
"""

# =====================================================
# PRODUCTS
# =====================================================

PRODUCTS = {
    "Laciador": {"price":34.99,"tags":["dry","damaged","tangly","frizzy","split","dull"]},
    "Gotero": {"price":29.99,"tags":["oily","flat","itchy"]},
    "Volumizer": {"price":39.99,"tags":["flat","not bouncy","falling","thin"]},
    "Color Protect": {"price":36.99,"tags":["color","lost color","fade","dull"]}
}

def match_product(text):
    text=text.lower()
    for name,data in PRODUCTS.items():
        for tag in data["tags"]:
            if tag in text:
                return name,data["price"]
    return None,None

@app.route("/voice",methods=["POST"])
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

    product,price=match_product(transcript)
    if not product:
        return speak("Tell me more about your hair so I can recommend the right product.")

    message=f"I recommend {product}. It directly targets your concern. The price is ${price}."
    return speak(message)

def speak(message):
    speech=client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=message
    )
    audio_bytes=speech.read()
    audio_base64=base64.b64encode(audio_bytes).decode("utf-8")
    return jsonify({"text":message,"audio":audio_base64})

if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
