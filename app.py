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
    width:210px;
    height:210px;
    border-radius:50%;
    cursor:pointer;
    transition:background 3s ease, box-shadow 3s ease, transform 0.1s linear;
    background:radial-gradient(circle at center,
        rgba(0,255,200,0.35) 0%,
        rgba(0,255,200,0.18) 50%,
        rgba(0,255,200,0.08) 75%,
        transparent 95%);
    box-shadow:0 0 70px rgba(0,255,200,0.35);
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
<div id="response">Tap the ring and ask about your hair.</div>

<script>

const halo = document.getElementById("halo");

let state="idle";
let silenceTimer=null;
let mediaRecorder=null;
let stream=null;
let audioElement=null;
let analyser=null;
let animationFrame=null;

const SILENCE_DELAY=2300;
const SILENCE_THRESHOLD=6;

/* =====================================
   COLOR STATES
=====================================*/

function setIdleColor(){
    halo.style.background=`radial-gradient(circle at center,
        rgba(0,255,200,0.35) 0%,
        rgba(0,255,200,0.18) 50%,
        rgba(0,255,200,0.08) 75%,
        transparent 95%)`;
}

function setGold(){
    halo.style.background=`radial-gradient(circle at center,
        rgba(255,210,0,0.55) 0%,
        rgba(255,170,0,0.35) 50%,
        rgba(255,140,0,0.15) 75%,
        transparent 95%)`;
}

function setThinkingBase(){
    halo.style.background=`radial-gradient(circle at center,
        rgba(0,255,255,0.35) 0%,
        rgba(0,220,255,0.2) 50%,
        rgba(0,180,255,0.1) 75%,
        transparent 95%)`;
}

function setSpeakingColor(){
    halo.style.background=`radial-gradient(circle at center,
        rgba(0,255,255,0.6) 0%,
        rgba(0,220,255,0.4) 50%,
        rgba(0,180,255,0.2) 75%,
        transparent 95%)`;
}

/* =====================================
   IDLE PULSE
=====================================*/

function idlePulse(){
    if(state!=="idle") return;
    let scale=1+Math.sin(Date.now()*0.002)*0.03;
    halo.style.transform=`scale(${scale})`;
    animationFrame=requestAnimationFrame(idlePulse);
}

/* =====================================
   REACTIVE PULSE
=====================================*/

function reactivePulse(){
    if(!analyser) return;

    const data=new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(data);

    let sum=0;
    for(let i=0;i<data.length;i++) sum+=data[i];
    let volume=sum/data.length;

    let scale=1+(volume/300);
    halo.style.transform=`scale(${scale})`;

    animationFrame=requestAnimationFrame(reactivePulse);
}

/* =====================================
   CLICK SOUND
=====================================*/

function playClick(){
    const ctx=new (window.AudioContext||window.webkitAudioContext)();
    const osc=ctx.createOscillator();
    const gain=ctx.createGain();

    osc.type="sine";
    osc.frequency.setValueAtTime(320,ctx.currentTime);
    osc.frequency.linearRampToValueAtTime(600,ctx.currentTime+0.8);

    gain.gain.setValueAtTime(0.0001,ctx.currentTime);
    gain.gain.linearRampToValueAtTime(0.3,ctx.currentTime+0.4);
    gain.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+1.3);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime+1.3);
}

/* =====================================
   FINISH SHIMMER SOUND
=====================================*/

function playEndTone(){
    const ctx=new (window.AudioContext||window.webkitAudioContext)();
    const osc1=ctx.createOscillator();
    const osc2=ctx.createOscillator();
    const gain=ctx.createGain();

    osc1.frequency.setValueAtTime(520,ctx.currentTime);
    osc2.frequency.setValueAtTime(780,ctx.currentTime);

    gain.gain.setValueAtTime(0.25,ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.0001,ctx.currentTime+2.5);

    osc1.connect(gain);
    osc2.connect(gain);
    gain.connect(ctx.destination);

    osc1.start();
    osc2.start();
    osc1.stop(ctx.currentTime+2.5);
    osc2.stop(ctx.currentTime+2.5);
}

/* =====================================
   RESET
=====================================*/

function fullReset(){

    cancelAnimationFrame(animationFrame);

    if(silenceTimer){
        clearTimeout(silenceTimer);
        silenceTimer=null;
    }

    if(mediaRecorder && mediaRecorder.state!=="inactive"){
        mediaRecorder.stop();
    }

    if(stream){
        stream.getTracks().forEach(t=>t.stop());
        stream=null;
    }

    if(audioElement){
        audioElement.pause();
        audioElement=null;
    }

    analyser=null;
    state="idle";
    halo.style.transform="scale(1)";
    setIdleColor();
    idlePulse();
}

/* =====================================
   CLICK HANDLER
=====================================*/

halo.addEventListener("click",()=>{
    playClick();

    if(state!=="idle"){
        fullReset();
        return;
    }

    startRecording();
});

/* =====================================
   RECORD
=====================================*/

async function startRecording(){

    state="listening";
    setGold();

    stream=await navigator.mediaDevices.getUserMedia({audio:true});
    const audioContext=new (window.AudioContext||window.webkitAudioContext)();
    analyser=audioContext.createAnalyser();
    analyser.fftSize=256;

    const source=audioContext.createMediaStreamSource(stream);
    source.connect(analyser);

    mediaRecorder=new MediaRecorder(stream);
    let chunks=[];

    mediaRecorder.ondataavailable=e=>chunks.push(e.data);

    mediaRecorder.onstop=async()=>{
        state="thinking";

        // Immediately morph gold → teal (NO GAP)
        setThinkingBase();

        const blob=new Blob(chunks,{type:"audio/webm"});
        const form=new FormData();
        form.append("audio",blob);

        const res=await fetch("/voice",{method:"POST",body:form});
        const data=await res.json();

        document.getElementById("response").innerText=data.text;

        speakAI(data.audio);
    };

    mediaRecorder.start();
    detectSilence();
    reactivePulse();
}

function detectSilence(){

    const data=new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(data);

    let sum=0;
    for(let i=0;i<data.length;i++) sum+=data[i];
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
        if(silenceTimer){
            clearTimeout(silenceTimer);
            silenceTimer=null;
        }
    }

    if(state==="listening")
        requestAnimationFrame(detectSilence);
}

/* =====================================
   AI SPEAK
=====================================*/

function speakAI(base64Audio){

    state="speaking";

    setSpeakingColor();

    audioElement=new Audio("data:audio/mp3;base64,"+base64Audio);

    const audioContext=new (window.AudioContext||window.webkitAudioContext)();
    analyser=audioContext.createAnalyser();
    analyser.fftSize=256;

    const sourceNode=audioContext.createMediaElementSource(audioElement);
    sourceNode.connect(analyser);
    analyser.connect(audioContext.destination);

    audioElement.play();
    reactivePulse();

    audioElement.onended=()=>{
        playEndTone();

        setTimeout(()=>{
            fullReset();
        },2500);
    };
}

setIdleColor();
idlePulse();

</script>
</body>
</html>
"""
# =====================================================
# BACKEND (unchanged)
# =====================================================

PRODUCTS={
    "Laciador":{"description":"It deeply hydrates dry hair and restores softness.","price":34.99},
    "Gotero":{"description":"It balances oily scalp while keeping hair fresh.","price":29.99}
}

def choose_product(text):
    text=text.lower()
    if "dry" in text: return "Laciador"
    if "oily" in text: return "Gotero"
    return None

@app.route("/voice",methods=["POST"])
def voice():
    try:
        if "audio" not in request.files:
            return speak("I didn’t quite catch that. Could you repeat?")

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

        text=transcript.strip()

        if not text or len(text)<2:
            return speak("I didn’t quite catch that. Could you repeat your hair concern?")

        product=choose_product(text)

        if not product:
            return speak("Please tell me if your hair is dry or oily.")

        info=PRODUCTS[product]
        message=f"I recommend {product}. {info['description']} With tax and shipping you're looking at ${info['price']}."

        return speak(message)

    except Exception:
        return speak("Something went wrong. Please try again.")

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
