import os
import tempfile
import base64
from flask import Flask, request, jsonify
from openai import OpenAI

os.environ["PYTHONUNBUFFERED"] = "1"

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# =========================
# AI LOGIC (UNCHANGED)
# =========================

def build_system_prompt(language):
    return f"""
You are a luxury AI hair advisor.

You ONLY recommend one of these 4 products:
- Laciador ($34.99)
- Gotero ($29.99)
- Volumizer ($39.99)
- Formula Exclusiva ($49.99)

Event / styling / sleek → Laciador
Oily → Gotero
Thin / falling out → Volumizer
Multiple issues → Formula Exclusiva

Always include price.
Always respond in {language}.
Tone must feel premium and emotionally supportive.
"""

# =========================
# FRONTEND
# =========================

@app.route("/")
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

let state="idle";
let analyser, mediaRecorder, stream;
let silenceTimer;
let audioElement;

const SILENCE_DELAY=2000;
const SILENCE_THRESHOLD=6;

const idleColor=[0,255,200];
const gold=[255,200,0];
const teal=[0,255,255];

let color=[...idleColor];
let intensity=0.25;
let targetColor=[...idleColor];
let targetIntensity=0.25;

function lerp(a,b,t){ return a+(b-a)*t; }

// Smooth but LIGHT animation
function animate(){
    intensity=lerp(intensity,targetIntensity,0.01); // very slow build

    for(let i=0;i<3;i++){
        color[i]=lerp(color[i],targetColor[i],0.01);
    }

    halo.style.background=`radial-gradient(circle at center,
        rgba(${color[0]},${color[1]},${color[2]},${intensity}) 0%,
        rgba(${color[0]},${color[1]},${color[2]},${intensity*0.5}) 60%,
        rgba(${color[0]},${color[1]},${color[2]},${intensity*0.2}) 85%,
        transparent 100%)`;

    halo.style.boxShadow=`0 0 ${60+intensity*200}px rgba(${color[0]},${color[1]},${color[2]},0.7)`;

    requestAnimationFrame(animate);
}
animate();

function transitionTo(newColor,newIntensity){
    targetColor=[...newColor];
    targetIntensity=newIntensity;
}

// =========================
// IDLE BREATHING PULSE
// =========================
function idlePulse(){
    if(state==="idle"){
        targetIntensity=0.25 + Math.sin(Date.now()*0.002)*0.05;
    }
    requestAnimationFrame(idlePulse);
}
idlePulse();

// =========================
// INTRO SOUND
// =========================
function playIntro(){
    const ctx=new(window.AudioContext||window.webkitAudioContext)();
    const o=ctx.createOscillator();
    const g=ctx.createGain();
    o.type="sine";
    o.frequency.setValueAtTime(450,ctx.currentTime);
    o.frequency.linearRampToValueAtTime(700,ctx.currentTime+2.5);
    g.gain.setValueAtTime(0.0001,ctx.currentTime);
    g.gain.linearRampToValueAtTime(0.25,ctx.currentTime+2);
    g.gain.linearRampToValueAtTime(0.0001,ctx.currentTime+3.5);
    o.connect(g); g.connect(ctx.destination);
    o.start(); o.stop(ctx.currentTime+3.5);
}

// =========================
// OUTRO SOUND
// =========================
function playOutro(){
    const ctx=new(window.AudioContext||window.webkitAudioContext)();
    const o=ctx.createOscillator();
    const g=ctx.createGain();
    o.type="triangle";
    o.frequency.setValueAtTime(650,ctx.currentTime);
    o.frequency.linearRampToValueAtTime(200,ctx.currentTime+3.5);
    g.gain.setValueAtTime(0.3,ctx.currentTime);
    g.gain.linearRampToValueAtTime(0.0001,ctx.currentTime+4);
    o.connect(g); g.connect(ctx.destination);
    o.start(); o.stop(ctx.currentTime+4);
}

halo.addEventListener("click",()=>{
    if(state!=="idle")return;
    playIntro();
    startRecording();
});

async function startRecording(){
    state="listening";
    transitionTo(gold,0.9);

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
        stream.getTracks().forEach(t=>t.stop()); // STOP MIC IMMEDIATELY

        state="thinking";
        transitionTo(teal,1.1);

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

// =========================
// VOICE REACTIVE PULSE
// =========================
function detectSilence(){
    if(!analyser)return;

    const data=new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(data);
    let sum=0;
    for(let i=0;i<data.length;i++)sum+=data[i];
    let volume=sum/data.length;

    targetIntensity=0.8 + volume/150; // reactive pulse

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

// =========================
// AI SPEECH REACTIVE
// =========================
function speakAI(base64Audio){
    state="speaking";
    audioElement=new Audio("data:audio/mp3;base64,"+base64Audio);

    const ctx=new(window.AudioContext||window.webkitAudioContext)();
    const source=ctx.createMediaElementSource(audioElement);
    const analyser2=ctx.createAnalyser();
    analyser2.fftSize=256;
    source.connect(analyser2);
    analyser2.connect(ctx.destination);

    audioElement.play();

    function react(){
        if(state!=="speaking")return;
        const data=new Uint8Array(analyser2.frequencyBinCount);
        analyser2.getByteFrequencyData(data);
        let sum=0;
        for(let i=0;i<data.length;i++)sum+=data[i];
        let volume=sum/data.length;
        targetIntensity=1 + volume/180;
        requestAnimationFrame(react);
    }
    react();

    audioElement.onended=()=>{
        playOutro();
        transitionTo(idleColor,0.3);
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
