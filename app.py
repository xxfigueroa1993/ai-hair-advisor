import os
import tempfile
import base64
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# =====================================================
# STRICT PRODUCT ROUTING (NO BOUNCE -> VOLUMIZER)
# =====================================================

PRODUCTS = {
    "Laciador": "$34.99",
    "Gotero": "$29.99",
    "Volumizer": "$39.99",
    "Formula Exclusiva": "$49.99"
}

def route_product(text):
    t = text.lower()

    # STYLING / BOUNCE / EVENT
    if any(x in t for x in [
        "event","party","wedding","date","style","styler",
        "sleek","smooth","frizz","bounce","bouncy"
    ]):
        return "Laciador"

    # OILY
    if any(x in t for x in ["oily","greasy"]):
        return "Gotero"

    # THIN ONLY (VERY STRICT)
    if any(x in t for x in [
        "thin","thinning","falling out","hair loss","bald"
    ]):
        return "Volumizer"

    # MULTIPLE
    if any(x in t for x in [
        "everything","all in one","multiple"
    ]):
        return "Formula Exclusiva"

    return "Formula Exclusiva"


def build_prompt(language):
    return f"""
You are a luxury AI hair advisor.

Only recommend one:
- Laciador ($34.99)
- Gotero ($29.99)
- Volumizer ($39.99)
- Formula Exclusiva ($49.99)

Always include price.
Always respond in {language}.
Premium supportive tone.
"""


# =====================================================
# FRONTEND
# =====================================================

@app.route("/")
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<title>AI Hair Advisor</title>
<style>
body{
margin:0;height:100vh;display:flex;
justify-content:center;align-items:center;
flex-direction:column;background:#000;
font-family:Arial;color:white;
}

select{
position:absolute;top:20px;right:20px;
padding:8px;background:#111;color:white;
border:none;
}

.halo{
width:260px;height:260px;
border-radius:50%;
cursor:pointer;
}

#response{
margin-top:40px;width:70%;
text-align:center;font-size:18px;
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
<div id="response">
Tap the ring and describe your hair concern.
</div>

<script>

const halo = document.getElementById("halo");
const languageSelect = document.getElementById("language");

let state = "idle";
let analyser, mediaRecorder, stream, audioCtx;
let silenceTimer;
let audioElement;

const SILENCE_DELAY = 2000;
const SILENCE_THRESHOLD = 6;

const idleColor = [0,255,200];
const gold = [255,200,0];
const teal = [0,255,255];

let color = [...idleColor];
let targetColor = [...idleColor];
let intensity = 0.45;
let targetIntensity = 0.45;
let pulseScale = 1;
let pulseTarget = 1;

// ======================
// ANIMATION ENGINE
// ======================

function lerp(a,b,t){ return a+(b-a)*t; }

function animate(){
    intensity = lerp(intensity,targetIntensity,0.08);
    pulseScale = lerp(pulseScale,pulseTarget,0.2);

    for(let i=0;i<3;i++){
        color[i]=lerp(color[i],targetColor[i],0.08);
    }

    halo.style.background=
    `radial-gradient(circle,
        rgba(${color[0]},${color[1]},${color[2]},${intensity}) 0%,
        rgba(${color[0]},${color[1]},${color[2]},${intensity*0.5}) 60%,
        transparent 100%)`;

    halo.style.transform=`scale(${pulseScale})`;

    requestAnimationFrame(animate);
}
animate();

// ======================
// RESET FUNCTION
// ======================

function hardReset(){
    if(mediaRecorder && mediaRecorder.state==="recording"){
        mediaRecorder.stop();
    }

    if(stream){
        stream.getTracks().forEach(t=>t.stop());
    }

    if(audioElement){
        audioElement.pause();
        audioElement=null;
    }

    state="idle";
    targetColor=[...idleColor];
    targetIntensity=0.45;
    pulseTarget=1;
}

// ======================
// CLICK
// ======================

halo.addEventListener("click",()=>{
    hardReset();
    startRecording();
});

// ======================
// START RECORDING
// ======================

async function startRecording(){

    state="listening";
    targetColor=[...gold];
    targetIntensity=1.0;

    audioCtx=new(window.AudioContext||window.webkitAudioContext)();
    stream=await navigator.mediaDevices.getUserMedia({audio:true});
    analyser=audioCtx.createAnalyser();
    analyser.fftSize=256;

    const source=audioCtx.createMediaStreamSource(stream);
    source.connect(analyser);

    mediaRecorder=new MediaRecorder(stream);
    let chunks=[];
    mediaRecorder.ondataavailable=e=>chunks.push(e.data);

    mediaRecorder.onstop=async()=>{
        stream.getTracks().forEach(t=>t.stop());
        audioCtx.close();

        state="thinking";
        targetColor=[...teal];
        targetIntensity=1.1;

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
    detectVoice();
}

// ======================
// VOICE REACTION
// ======================

function detectVoice(){
    if(state!=="listening") return;

    const data=new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(data);
    let sum=0;
    for(let i=0;i<data.length;i++) sum+=data[i];
    let volume=sum/data.length;

    pulseTarget=1 + volume/100; // deep pulse

    if(volume < SILENCE_THRESHOLD){
        if(!silenceTimer){
            silenceTimer=setTimeout(()=>{
                targetColor=[...teal]; // GUARANTEED GOLD->TEAL
                mediaRecorder.stop();
            }, SILENCE_DELAY);
        }
    } else {
        if(silenceTimer){ clearTimeout(silenceTimer); silenceTimer=null; }
    }

    requestAnimationFrame(detectVoice);
}

// ======================
// AI SPEECH
// ======================

function speakAI(b64){
    state="speaking";
    audioElement=new Audio("data:audio/mp3;base64,"+b64);

    const ctx=new(window.AudioContext||window.webkitAudioContext)();
    const src=ctx.createMediaElementSource(audioElement);
    const analyser2=ctx.createAnalyser();
    analyser2.fftSize=256;
    src.connect(analyser2);
    analyser2.connect(ctx.destination);

    audioElement.play();

    function react(){
        if(state!=="speaking") return;
        const data=new Uint8Array(analyser2.frequencyBinCount);
        analyser2.getByteFrequencyData(data);
        let sum=0;
        for(let i=0;i<data.length;i++) sum+=data[i];
        let volume=sum/data.length;
        pulseTarget=1 + volume/110;
        requestAnimationFrame(react);
    }
    react();

    audioElement.onended=()=>{
        state="idle";
        targetColor=[...idleColor]; // no dark fade
        targetIntensity=0.45;
        pulseTarget=1;
    };
}

</script>
</body>
</html>
"""

# =====================================================
# BACKEND
# =====================================================

@app.route("/voice", methods=["POST"])
def voice():
    language = request.form.get("language","English")
    file = request.files["audio"]

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
    product=route_product(text)
    price=PRODUCTS[product]

    completion=client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[
            {"role":"system","content":build_prompt(language)},
            {"role":"assistant","content":f"Recommend {product} ({price}) in a premium supportive tone."},
            {"role":"user","content":text}
        ]
    )

    return speak(completion.choices[0].message.content)


def speak(msg):
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
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
