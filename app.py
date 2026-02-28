import os
import tempfile
import base64
from flask import Flask, request, jsonify
from openai import OpenAI

os.environ["PYTHONUNBUFFERED"] = "1"

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# =====================================================
# STRONGER SYSTEM PROMPT
# =====================================================

def build_system_prompt(language):
    return f"""
You are a luxury AI hair advisor.

You MUST follow this decision hierarchy strictly.

PRODUCT LOGIC (in priority order):

1️⃣ DRY / DULL / GLOW / SHINE / SLEEK / FRIZZ / EVENT / STYLING
→ Primary recommendation: Laciador ($34.99)

2️⃣ OILY / GREASY SCALP
→ Primary recommendation: Gotero ($29.99)

3️⃣ THIN / FLAT / FALLING OUT / HAIR LOSS
→ Primary recommendation: Volumizer ($39.99)

4️⃣ RESTORATIVE / DAMAGE REPAIR / MULTIPLE PROBLEMS / ALL-IN-ONE
→ Primary recommendation: Formula Exclusiva ($49.99)

Rules:

• If user mentions dry hair → ALWAYS Laciador.
• If user mentions glow or shine → ALWAYS Laciador.
• If user mentions curls needing bounce → Laciador primary, optionally suggest Formula Exclusiva as secondary nourishment.
• If multiple distinct problems → Formula Exclusiva primary.
• Never confuse glow with volume.
• Never confuse restorative with volumizing.
• Always include price.
• Always respond strictly in {language}.
• Tone must feel premium, confident, and luxurious.
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
<title>Luxury Hair AI</title>
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
    transition:background 3s ease, box-shadow 3s ease, transform 3s ease;
    background:radial-gradient(circle at center,
        rgba(0,255,200,0.4) 0%,
        rgba(0,255,200,0.2) 50%,
        rgba(0,255,200,0.1) 75%,
        transparent 95%);
    box-shadow:0 0 120px rgba(0,255,200,0.5);
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

const halo=document.getElementById("halo");
const languageSelect=document.getElementById("language");

let state="idle";
let analyser, mediaRecorder, stream;
let silenceTimer;
let audioElement=null;

const idleColor=[0,255,200];
const gold=[255,200,0];
const teal=[0,255,255];

function setColor(rgb,intensity=0.5){
    halo.style.background=`radial-gradient(circle at center,
        rgba(${rgb[0]},${rgb[1]},${rgb[2]},${intensity}) 0%,
        rgba(${rgb[0]},${rgb[1]},${rgb[2]},${intensity*0.6}) 50%,
        rgba(${rgb[0]},${rgb[1]},${rgb[2]},${intensity*0.3}) 75%,
        transparent 95%)`;
    halo.style.boxShadow=`0 0 ${140+intensity*200}px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.7)`;
}

function idlePulse(){
    if(state!=="idle") return;
    let scale=1+Math.sin(Date.now()*0.0015)*0.02;
    halo.style.transform=`scale(${scale})`;
    requestAnimationFrame(idlePulse);
}
idlePulse();

halo.addEventListener("click",()=>{
    if(state!=="idle") return;
    startRecording();
});

async function startRecording(){

    state="listening";
    setColor(gold,0.9);

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
        setColor(teal,0.8);

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
    for(let i=0;i<data.length;i++) sum+=data[i];
    let volume=sum/data.length;

    if(volume<6){
        if(!silenceTimer){
            silenceTimer=setTimeout(()=>{
                if(mediaRecorder && mediaRecorder.state==="recording"){
                    mediaRecorder.stop();
                }
            },2000);
        }
    }else{
        clearTimeout(silenceTimer);
        silenceTimer=null;
    }

    if(state==="listening") requestAnimationFrame(detectSilence);
}

function speakAI(base64Audio){

    state="speaking";
    setColor(teal,1.0);

    audioElement=new Audio("data:audio/mp3;base64,"+base64Audio);
    audioElement.volume=0;

    audioElement.play();

    // Slow fade in
    let fadeIn=setInterval(()=>{
        if(audioElement.volume<1){
            audioElement.volume+=0.05;
        }else{
            clearInterval(fadeIn);
        }
    },100);

    audioElement.onended=()=>{
        // Fade out
        let fadeOut=setInterval(()=>{
            if(audioElement.volume>0.05){
                audioElement.volume-=0.05;
            }else{
                clearInterval(fadeOut);
                state="idle";
                setColor(idleColor,0.5);
                idlePulse();
            }
        },100);
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

    user_text=transcript.strip()
    os.remove(path)

    completion=client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":build_system_prompt(language)},
            {"role":"user","content":user_text}
        ],
        temperature=0.3
    )

    ai_message=completion.choices[0].message.content

    speech=client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=ai_message
    )

    audio_bytes=speech.read()
    audio_base64=base64.b64encode(audio_bytes).decode("utf-8")

    return jsonify({"text":ai_message,"audio":audio_base64})


if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
