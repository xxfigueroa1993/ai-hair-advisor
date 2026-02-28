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
    width:200px;
    height:200px;
    border-radius:50%;
    cursor:pointer;
    transition:all 0.8s ease;
    background:radial-gradient(circle at center,
        rgba(0,255,200,0.35) 0%,
        rgba(0,255,200,0.2) 50%,
        rgba(0,255,200,0.08) 75%,
        transparent 95%);
    box-shadow:0 0 60px rgba(0,255,200,0.35);
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
let state = "idle";
let silenceTimer = null;
let mediaRecorder = null;
let stream = null;
let audioElement = null;

const SILENCE_DELAY = 2300;
const SILENCE_THRESHOLD = 6;

let audioContext;
let analyser;
let dataArray;

/* ================================
   COLOR STATES
================================ */

function setIdle(){
    state="idle";
    halo.style.background=`radial-gradient(circle at center,
        rgba(0,255,200,0.35) 0%,
        rgba(0,255,200,0.2) 50%,
        rgba(0,255,200,0.08) 75%,
        transparent 95%)`;
}

function setGold(){
    halo.style.background=`radial-gradient(circle at center,
        rgba(255,200,0,0.45) 0%,
        rgba(255,170,0,0.3) 50%,
        rgba(255,140,0,0.1) 75%,
        transparent 95%)`;
}

function setThinking(){
    halo.style.background=`radial-gradient(circle at center,
        rgba(0,255,255,0.6) 0%,
        rgba(0,220,255,0.4) 50%,
        rgba(0,180,255,0.2) 75%,
        transparent 95%)`;
}

/* ================================
   CLICK SOUND (SLOW FADE IN)
================================ */

function playClick(){
    const ctx = new (window.AudioContext||window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type="sine";
    osc.frequency.setValueAtTime(380,ctx.currentTime);
    osc.frequency.linearRampToValueAtTime(720,ctx.currentTime+0.4);

    gain.gain.setValueAtTime(0.0001,ctx.currentTime);
    gain.gain.linearRampToValueAtTime(0.3,ctx.currentTime+0.15);
    gain.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+0.6);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime+0.6);
}

/* ================================
   FULL RESET
================================ */

function resetAll(){

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

    state="idle";
    setIdle();
}

/* ================================
   CLICK HANDLER
================================ */

halo.addEventListener("click",()=>{

    playClick();

    if(state!=="idle"){
        resetAll();
        return;
    }

    startRecording();
});

/* ================================
   RECORD
================================ */

async function startRecording(){

    state="listening";
    setGold();

    stream = await navigator.mediaDevices.getUserMedia({audio:true});
    audioContext = new (window.AudioContext||window.webkitAudioContext)();
    analyser = audioContext.createAnalyser();
    analyser.fftSize=256;

    const source = audioContext.createMediaStreamSource(stream);
    source.connect(analyser);
    dataArray = new Uint8Array(analyser.frequencyBinCount);

    mediaRecorder = new MediaRecorder(stream);
    let chunks=[];

    mediaRecorder.ondataavailable=e=>chunks.push(e.data);

    mediaRecorder.onstop=async()=>{

        state="thinking";
        setThinking();

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

/* ================================
   SILENCE DETECTION
================================ */

function detectSilence(){

    if(!analyser) return;

    analyser.getByteFrequencyData(dataArray);

    let sum=0;
    for(let i=0;i<dataArray.length;i++) sum+=dataArray[i];
    let volume=sum/dataArray.length;

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

/* ================================
   AI SPEAK
================================ */

function speakAI(base64Audio){

    state="speaking";

    audioElement=new Audio("data:audio/mp3;base64,"+base64Audio);
    audioElement.play();

    audioElement.onended=()=>{
        setTimeout(()=>{
            setIdle();
            state="idle";
        },600);
    };
}

setIdle();

</script>
</body>
</html>
"""

# =====================================================
# BACKEND
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
            return speak("I’m sorry, I didn’t quite catch that. Could you repeat?")

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
            return speak("I’m sorry, I didn’t quite catch that. Could you repeat your hair concern?")

        product=choose_product(text)

        if not product:
            return speak("Please tell me if your hair is dry or oily so I can help.")

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
