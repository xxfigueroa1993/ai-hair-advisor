import os
import tempfile
import base64
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# ------------------------
# PRODUCTS
# ------------------------

PRODUCTS = {
    "Laciador": {
        "price": "$34.99",
        "description": "Provides a sleek, smooth finish with long-lasting frizz control."
    },
    "Gotero": {
        "price": "$29.99",
        "description": "Balances oil production while refreshing and nourishing the scalp."
    },
    "Volumizer": {
        "price": "$39.99",
        "description": "Restores fullness and thickness to thinning or fine hair."
    },
    "Formula Exclusiva": {
        "price": "$49.99",
        "description": "Our premium all-in-one restorative treatment for total hair revival."
    }
}


def route_product(text):
    t = text.lower()

    if any(x in t for x in ["event","party","wedding","date","sleek","smooth","frizz"]):
        return "Laciador"

    if any(x in t for x in ["oily","greasy"]):
        return "Gotero"

    if any(x in t for x in ["thin","thinning","hair loss","bald"]):
        return "Volumizer"

    return "Formula Exclusiva"


# ------------------------
# FRONTEND
# ------------------------

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
flex-direction:column;
font-family:Arial;
color:white;
overflow:hidden;
}

.halo{
width:260px;height:260px;
border-radius:50%;
cursor:pointer;
}

#response{
margin-top:40px;
width:70%;
text-align:center;
font-size:18px;
line-height:1.6;
}
</style>
</head>
<body>

<div id="halo" class="halo"></div>
<div id="response">Tap to speak.</div>

<script>

const halo = document.getElementById("halo");
const responseText = document.getElementById("response");

let state = "idle";
let audioEl = null;
let mediaRecorder = null;
let stream = null;
let silenceTimeout = null;

let baseColor = [0,255,200];
let currentColor = [...baseColor];
let targetColor = [...baseColor];

let pulse = 1;
let targetPulse = 1.02;
let glowIntensity = 0.6;
let targetGlow = 0.6;

const fadeSpeed = 0.02; // slower smoothing

// ---------- SOUND FX ----------

const clickSound = new Audio("https://assets.mixkit.co/sfx/preview/mixkit-modern-click-box-check-1120.mp3");
const fadeSound = new Audio("https://assets.mixkit.co/sfx/preview/mixkit-interface-click-1126.mp3");

function playClick(){
    clickSound.currentTime = 0;
    clickSound.volume = 0.4;
    clickSound.play();
}

function playFade(){
    fadeSound.currentTime = 0;
    fadeSound.volume = 0.3;
    fadeSound.play();
}

// ---------- ANIMATION LOOP ----------

function lerp(a,b,t){ return a+(b-a)*t; }

function animate(){

    for(let i=0;i<3;i++)
        currentColor[i] = lerp(currentColor[i], targetColor[i], fadeSpeed);

    pulse = lerp(pulse, targetPulse, fadeSpeed);
    glowIntensity = lerp(glowIntensity, targetGlow, fadeSpeed);

    // thick smooth halo (no visible ring)
    halo.style.background = `
    radial-gradient(circle,
        rgba(${currentColor[0]},${currentColor[1]},${currentColor[2]},${glowIntensity}) 0%,
        rgba(${currentColor[0]},${currentColor[1]},${currentColor[2]},${glowIntensity*0.7}) 40%,
        rgba(${currentColor[0]},${currentColor[1]},${currentColor[2]},${glowIntensity*0.4}) 70%,
        rgba(${currentColor[0]},${currentColor[1]},${currentColor[2]},0) 100%)`;

    halo.style.boxShadow = `
    0 0 160px rgba(${currentColor[0]},${currentColor[1]},${currentColor[2]},${glowIntensity*0.7}),
    0 0 260px rgba(${currentColor[0]},${currentColor[1]},${currentColor[2]},${glowIntensity*0.5})`;

    halo.style.transform = `scale(${pulse})`;

    requestAnimationFrame(animate);
}
animate();

// ---------- STATE MANAGEMENT ----------

function resetToIdle(){

    state="idle";

    targetColor=[...baseColor];
    targetPulse=1.02;
    targetGlow=0.6;

    if(audioEl){
        audioEl.pause();
        audioEl=null;
    }

    if(stream){
        stream.getTracks().forEach(t=>t.stop());
        stream=null;
    }

    silenceTimeout=null;
}

// ---------- CLICK ----------

halo.addEventListener("click",()=>{

    playClick();

    if(state==="idle"){
        startListening();
    }else{
        resetToIdle();
    }
});

// ---------- LISTEN ----------

async function startListening(){

    resetToIdle();

    state="listening";

    targetColor=[255,200,0];
    targetGlow=1.0;
    targetPulse=1.05;

    stream = await navigator.mediaDevices.getUserMedia({audio:true});
    mediaRecorder = new MediaRecorder(stream);
    let chunks=[];

    mediaRecorder.ondataavailable=e=>chunks.push(e.data);

    mediaRecorder.onstop=async()=>{

        playFade();

        state="thinking";
        targetColor=[0,255,255];
        targetGlow=1.1;

        const blob=new Blob(chunks,{type:"audio/webm"});
        const form=new FormData();
        form.append("audio",blob);

        const res=await fetch("/voice",{method:"POST",body:form});
        const data=await res.json();

        responseText.innerText=data.text;

        speak(data.audio);
    };

    mediaRecorder.start();

    detectSilence();
}

// ---------- SILENCE DETECT ----------

function detectSilence(){

    const audioCtx=new AudioContext();
    const analyser=audioCtx.createAnalyser();
    const src=audioCtx.createMediaStreamSource(stream);
    src.connect(analyser);

    analyser.fftSize=256;

    function check(){

        if(state!=="listening") return;

        const data=new Uint8Array(analyser.frequencyBinCount);
        analyser.getByteFrequencyData(data);
        const volume=data.reduce((a,b)=>a+b)/data.length;

        if(volume<5){
            if(!silenceTimeout){
                silenceTimeout=setTimeout(()=>{
                    mediaRecorder.stop();
                },1500);
            }
        }else{
            clearTimeout(silenceTimeout);
            silenceTimeout=null;
        }

        requestAnimationFrame(check);
    }

    check();
}

// ---------- SPEAK ----------

function speak(b64){

    state="speaking";

    targetColor=[120,255,255];
    targetGlow=1.2;
    targetPulse=1.06;

    audioEl=new Audio("data:audio/mp3;base64,"+b64);
    audioEl.play();

    audioEl.onended=()=>{
        resetToIdle();
    };
}

</script>
</body>
</html>
"""

# ------------------------
# VOICE ROUTE
# ------------------------

@app.route("/voice", methods=["POST"])
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

        os.remove(path)

        product_name=route_product(transcript)
        product=PRODUCTS[product_name]

        msg=f"""
Based on what you described, I recommend {product_name}.
{product['description']}
The price is {product['price']}.
""".strip()

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

    except Exception:
        return jsonify({
            "text":"Something went wrong. Please try again.",
            "audio":""
        })


if __name__=="__main__":
    app.run(host="0.0.0.0",port=10000)
