import os
import tempfile
import base64
from flask import Flask, request, jsonify
from openai import OpenAI

os.environ["PYTHONUNBUFFERED"] = "1"

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# =====================================================
# PRODUCT SYSTEM (4 PRODUCTS ONLY)
# =====================================================

SYSTEM_PROMPT = """
You are a luxury AI hair advisor.

You ONLY recommend one of these 4 products:
- Laciador ($34.99)
- Gotero ($29.99)
- Volumizer ($39.99)
- Formula Exclusiva ($49.99)

Rules:
• Frizz / Dry / Damage → Laciador
• Oily / Greasy → Gotero
• Thin / Flat / Falling Out → Volumizer
• Multiple problems OR All-in-one → Formula Exclusiva

IMPORTANT:
- NEVER invent product names.
- ALWAYS include the price.
- ALWAYS respond in the SAME language as the user.
- If unclear, guide them politely in their language:
  Suggest keywords like Frizz, Dry, Oily, Falling Out, or All-in-One.
- Tone must feel premium and confident.
"""

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
    width:240px;
    height:240px;
    border-radius:50%;
    cursor:pointer;
    transform:scale(1);
    background:radial-gradient(circle at center,
        rgba(0,255,200,0.4) 0%,
        rgba(0,255,200,0.2) 50%,
        rgba(0,255,200,0.1) 75%,
        transparent 95%);
    box-shadow:0 0 80px rgba(0,255,200,0.4);
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
let analyser, mediaRecorder, stream;
let silenceTimer;

const SILENCE_DELAY=2000;
const SILENCE_THRESHOLD=6;

const idleColor=[0,255,200];
const gold=[255,200,0];
const teal=[0,255,255];

function setColor(rgb,intensity=0.4){
    halo.style.background=`radial-gradient(circle at center,
        rgba(${rgb[0]},${rgb[1]},${rgb[2]},${intensity}) 0%,
        rgba(${rgb[0]},${rgb[1]},${rgb[2]},${intensity*0.5}) 50%,
        rgba(${rgb[0]},${rgb[1]},${rgb[2]},${intensity*0.2}) 75%,
        transparent 95%)`;
    halo.style.boxShadow=`0 0 ${80+intensity*120}px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.6)`;
}

function idlePulse(){
    if(state!=="idle")return;
    let scale=1+Math.sin(Date.now()*0.002)*0.03;
    halo.style.transform=`scale(${scale})`;
    requestAnimationFrame(idlePulse);
}
idlePulse();

/* =========================
   PREMIUM CLICK SOUND
========================= */
function playClickSound(){
    const ctx=new(window.AudioContext||window.webkitAudioContext)();
    const osc=ctx.createOscillator();
    const gain=ctx.createGain();

    osc.type="sine";
    osc.frequency.setValueAtTime(520,ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(780,ctx.currentTime+0.6);

    gain.gain.setValueAtTime(0.0001,ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.3,ctx.currentTime+0.4);
    gain.gain.exponentialRampToValueAtTime(0.0001,ctx.currentTime+1.2);

    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime+1.2);
}

/* =========================
   PREMIUM OUTRO SOUND
========================= */
function playOutroSound(){
    const ctx=new(window.AudioContext||window.webkitAudioContext)();
    const osc=ctx.createOscillator();
    const gain=ctx.createGain();

    osc.type="triangle";
    osc.frequency.setValueAtTime(640,ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(320,ctx.currentTime+1.8);

    gain.gain.setValueAtTime(0.25,ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.0001,ctx.currentTime+2.2);

    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime+2.2);
}

/* ========================= */

halo.addEventListener("click",()=>{
    if(state!=="idle")return;
    playClickSound();
    startRecording();
});

async function startRecording(){
    state="listening";
    setColor(gold,0.7);

    stream=await navigator.mediaDevices.getUserMedia({audio:true});
    const ctx=new(window.AudioContext||window.webkitAudioContext)();
    analyser=ctx.createAnalyser();
    analyser.fftSize=256;
    const source=ctx.createMediaStreamSource(stream);
    source.connect(analyser);

    mediaRecorder=new MediaRecorder(stream);
    let chunks=[];
    mediaRecorder.ondataavailable=e=>chunks.push(e.data);

    mediaRecorder.onstop=async()=>{
        state="thinking";
        setColor(teal,0.9);

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
    const audio=new Audio("data:audio/mp3;base64,"+base64Audio);
    audio.play();

    audio.onended=()=>{
        playOutroSound();
        state="idle";
        setColor(idleColor,0.4);
        idlePulse();
    };
}
</script>
</body>
</html>
"""

# =====================================================
# VOICE ENDPOINT
# =====================================================

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

    user_text=transcript.strip()

    completion=client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":SYSTEM_PROMPT},
            {"role":"user","content":user_text}
        ]
    )

    ai_message=completion.choices[0].message.content
    return speak(ai_message)

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
