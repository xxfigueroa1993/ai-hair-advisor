import os
import tempfile
import base64
from flask import Flask, request, jsonify
from openai import OpenAI

os.environ["PYTHONUNBUFFERED"] = "1"

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# =========================
# SYSTEM PROMPT (UNCHANGED)
# =========================

def build_system_prompt(language):
    return f"""
You are a luxury AI hair advisor.

You ONLY recommend one of these 4 products:
- Laciador ($34.99)
- Gotero ($29.99)
- Volumizer ($39.99)
- Formula Exclusiva ($49.99)

Interpretation:
• Event / styling / sleek look → Laciador
• Oily → Gotero
• Thin / falling out → Volumizer
• Multiple issues → Formula Exclusiva

Always:
- Include price
- Respond strictly in {language}
- Keep tone premium and emotionally supportive
"""

# =========================
# FRONTEND
# =========================

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
    background:#000;
    font-family:Arial;
    color:white;
}
select{
    position:absolute;
    top:20px;
    right:20px;
    padding:8px;
    background:#111;
    color:white;
    border:1px solid #444;
}
.halo{
    width:240px;
    height:240px;
    border-radius:50%;
    cursor:pointer;
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

<select id="language">
<option value="English">English</option>
<option value="Spanish">Spanish</option>
<option value="French">French</option>
<option value="Portuguese">Portuguese</option>
<option value="Arabic">Arabic</option>
<option value="German">German</option>
</select>

<div id="halo" class="halo"></div>
<div id="response">Tap the ring and describe your hair concern.</div>

<script>

const halo = document.getElementById("halo");
const languageSelect = document.getElementById("language");

let state = "idle";
let analyser, mediaRecorder, stream;
let silenceTimer;

const SILENCE_DELAY = 2000;
const SILENCE_THRESHOLD = 6;

const idleColor = [0,255,200];
const gold = [255,200,0];
const teal = [0,255,255];

let currentColor = [...idleColor];
let targetColor = [...idleColor];

let currentIntensity = 0.15;
let targetIntensity = 0.15;

// TRUE RGB INTERPOLATION
function lerp(a,b,t){
    return a + (b - a) * t;
}

function animateVisual(){
    // Smooth intensity
    currentIntensity = lerp(currentIntensity, targetIntensity, 0.03);

    // Smooth RGB
    for(let i=0;i<3;i++){
        currentColor[i] = lerp(currentColor[i], targetColor[i], 0.03);
    }

    halo.style.background = `radial-gradient(circle at center,
        rgba(${currentColor[0]},${currentColor[1]},${currentColor[2]},${currentIntensity}) 0%,
        rgba(${currentColor[0]},${currentColor[1]},${currentColor[2]},${currentIntensity*0.5}) 50%,
        transparent 90%)`;

    halo.style.boxShadow = `0 0 ${40 + currentIntensity*160}px rgba(${currentColor[0]},${currentColor[1]},${currentColor[2]},0.7)`;

    requestAnimationFrame(animateVisual);
}
animateVisual();

function transitionTo(color, intensity){
    targetColor = [...color];
    targetIntensity = intensity;
}

/* =========================
   INTRO SOUND
========================= */
function playIntroSound(){
    const ctx=new(window.AudioContext||window.webkitAudioContext)();
    const osc=ctx.createOscillator();
    const gain=ctx.createGain();

    osc.type="sine";
    osc.frequency.setValueAtTime(500,ctx.currentTime);
    osc.frequency.linearRampToValueAtTime(750,ctx.currentTime+1.0);

    gain.gain.setValueAtTime(0.0001,ctx.currentTime);
    gain.gain.linearRampToValueAtTime(0.3,ctx.currentTime+1.0);
    gain.gain.linearRampToValueAtTime(0.0001,ctx.currentTime+1.8);

    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime+1.8);
}

/* =========================
   OUTRO SOUND
========================= */
function playOutroSound(){
    const ctx=new(window.AudioContext||window.webkitAudioContext)();
    const osc=ctx.createOscillator();
    const gain=ctx.createGain();

    osc.type="triangle";
    osc.frequency.setValueAtTime(650,ctx.currentTime);
    osc.frequency.linearRampToValueAtTime(280,ctx.currentTime+2.2);

    gain.gain.setValueAtTime(0.25,ctx.currentTime);
    gain.gain.linearRampToValueAtTime(0.0001,ctx.currentTime+2.5);

    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime+2.5);
}

halo.addEventListener("click",()=>{
    if(state!=="idle")return;
    playIntroSound();
    startRecording();
});

async function startRecording(){
    state="listening";
    transitionTo(gold, 1.0);

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
        transitionTo(teal, 1.1);

        const blob=new Blob(chunks,{type:"audio/webm"});
        const form=new FormData();
        form.append("audio",blob);
        form.append("language",languageSelect.value);

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
        transitionTo(idleColor, 0.15);
        state="idle";
    };
}

</script>
</body>
</html>
"""

# =========================
# BACKEND
# =========================

@app.route("/voice",methods=["POST"])
def voice():
    language=request.form.get("language","English")

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

    completion=client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":build_system_prompt(language)},
            {"role":"user","content":transcript.strip()}
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
