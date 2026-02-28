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

/* ==================================================
   MANUAL COLOR FADE ENGINE (Ultra Smooth)
==================================================*/

function lerp(a,b,t){ return a+(b-a)*t; }

function fadeGradient(from,to,duration,callback){
    let start=null;

    function animate(timestamp){
        if(!start) start=timestamp;
        let progress=(timestamp-start)/duration;
        if(progress>1) progress=1;

        let r=lerp(from.r,to.r,progress);
        let g=lerp(from.g,to.g,progress);
        let b=lerp(from.b,to.b,progress);
        let a=lerp(from.a,to.a,progress);

        halo.style.background=`radial-gradient(circle at center,
            rgba(${r},${g},${b},${a}) 0%,
            rgba(${r},${g},${b},${a*0.5}) 50%,
            rgba(${r},${g},${b},${a*0.2}) 75%,
            transparent 95%)`;

        if(progress<1){
            requestAnimationFrame(animate);
        }else{
            if(callback) callback();
        }
    }
    requestAnimationFrame(animate);
}

const idleColor={r:0,g:255,b:200,a:0.35};
const goldColor={r:255,g:200,b:0,a:0.6};
const brightTeal={r:0,g:255,b:255,a:0.85};

/* ==================================================
   IDLE PULSE
==================================================*/

function idlePulse(){
    if(state!=="idle") return;
    let scale=1+Math.sin(Date.now()*0.002)*0.03;
    halo.style.transform=`scale(${scale})`;
    animationFrame=requestAnimationFrame(idlePulse);
}

/* ==================================================
   CLICK SOUND (unchanged, you liked it)
==================================================*/

function playClick(){
    const ctx=new (window.AudioContext||window.webkitAudioContext)();
    const osc=ctx.createOscillator();
    const gain=ctx.createGain();

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

/* ==================================================
   NEW FINISH SOUND (Soft Bloom)
==================================================*/

function playEndTone(){
    const ctx=new (window.AudioContext||window.webkitAudioContext)();
    const osc=ctx.createOscillator();
    const gain=ctx.createGain();

    osc.type="triangle";
    osc.frequency.setValueAtTime(400,ctx.currentTime);
    osc.frequency.linearRampToValueAtTime(520,ctx.currentTime+1.2);

    gain.gain.setValueAtTime(0.3,ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.0001,ctx.currentTime+3);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime+3);
}

/* ==================================================
   RESET
==================================================*/

function fullReset(){
    cancelAnimationFrame(animationFrame);

    if(silenceTimer) clearTimeout(silenceTimer);
    if(mediaRecorder && mediaRecorder.state!=="inactive") mediaRecorder.stop();
    if(stream) stream.getTracks().forEach(t=>t.stop());
    if(audioElement) audioElement.pause();

    state="idle";
    fadeGradient(brightTeal,idleColor,3000,()=>{
        idlePulse();
    });
}

/* ==================================================
   CLICK HANDLER
==================================================*/

halo.addEventListener("click",()=>{
    playClick();
    if(state!=="idle"){
        fullReset();
        return;
    }
    startRecording();
});

/* ==================================================
   RECORD
==================================================*/

async function startRecording(){

    state="listening";

    // 5 SECOND GOLD FADE IN
    fadeGradient(idleColor,goldColor,5000);

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

        // 5 SECOND GOLD → BRIGHT TEAL
        fadeGradient(goldColor,brightTeal,5000);

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
                if(mediaRecorder.state==="recording"){
                    mediaRecorder.stop();
                }
            },SILENCE_DELAY);
        }
    }else{
        if(silenceTimer) clearTimeout(silenceTimer);
    }

    if(state==="listening")
        requestAnimationFrame(detectSilence);
}

/* ==================================================
   AI SPEAK
==================================================*/

function speakAI(base64Audio){

    state="speaking";
    audioElement=new Audio("data:audio/mp3;base64,"+base64Audio);
    audioElement.play();

    audioElement.onended=()=>{
        playEndTone();
        setTimeout(()=>{
            fullReset();
        },3000);
    };
}

idlePulse();

</script>
</body>
</html>
"""

# =====================================================
# EXPANDED HAIR KNOWLEDGE
# =====================================================

HAIR_DATABASE = {
    "dry": "Your hair may be lacking moisture and natural oils.",
    "damaged": "Damage is often caused by heat styling or chemical treatments.",
    "tangly": "Tangles usually mean dryness or cuticle roughness.",
    "lost color": "Color fading can happen from UV exposure and washing.",
    "oily": "Excess oil comes from overactive sebaceous glands.",
    "not bouncy": "Flat hair often needs lightweight nourishment.",
    "falling out": "Hair shedding can result from stress or scalp imbalance.",
    "frizzy": "Frizz is caused by moisture imbalance.",
    "flat": "Flatness may mean buildup or lack of volume support.",
    "dull": "Dull hair often lacks proper hydration and shine protection.",
    "split ends": "Split ends are signs of structural damage.",
    "itchy": "Itchiness can signal scalp imbalance."
}

@app.route("/voice",methods=["POST"])
def voice():
    try:
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

        text=transcript.lower()

        response=""

        for key,val in HAIR_DATABASE.items():
            if key in text:
                response=f"I understand. {val} I recommend using our advanced repair formula designed specifically for this concern. It restores balance, improves texture, and promotes healthy shine."
                break

        if response=="":
            response="Tell me more about your hair concern so I can recommend the right solution."

        return speak(response)

    except:
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
