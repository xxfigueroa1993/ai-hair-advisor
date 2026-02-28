import os
import tempfile
import base64
from flask import Flask, request, jsonify
from openai import OpenAI

os.environ["PYTHONUNBUFFERED"] = "1"

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# =====================================================
# FRONTEND (FULL INLINE – NOTHING MISSING)
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
let analyser=null;
let silenceTimer=null;
const SILENCE_DELAY=2000;
const SILENCE_THRESHOLD=6;

function idlePulse(){
    if(state!=="idle")return;
    let scale=1+Math.sin(Date.now()*0.002)*0.03;
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
    stream=await navigator.mediaDevices.getUserMedia({audio:true});
    const audioCtx=new(window.AudioContext||window.webkitAudioContext)();
    analyser=audioCtx.createAnalyser();
    analyser.fftSize=256;
    const source=audioCtx.createMediaStreamSource(stream);
    source.connect(analyser);

    mediaRecorder=new MediaRecorder(stream);
    let chunks=[];
    mediaRecorder.ondataavailable=e=>chunks.push(e.data);

    mediaRecorder.onstop=async()=>{
        state="thinking";
        const blob=new Blob(chunks,{type:"audio/webm"});
        const form=new FormData();
        form.append("audio",blob);

        const res=await fetch("/voice",{method:"POST",body:form});
        const data=await res.json();
        document.getElementById("response").innerText=data.text;

        const audio=new Audio("data:audio/mp3;base64,"+data.audio);
        audio.play();
        audio.onended=()=>{state="idle"; idlePulse();}
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
</script>
</body>
</html>
"""


# =====================================================
# 4 PRODUCT DATABASE ONLY
# =====================================================

PRODUCTS = {
    "Laciador": {
        "price": 34.99,
        "keywords": ["frizz","frizzy","dry","damaged","tangle","tangly","split","puffy"]
    },
    "Gotero": {
        "price": 29.99,
        "keywords": ["oily","greasy","itchy","oil","buildup"]
    },
    "Volumizer": {
        "price": 39.99,
        "keywords": ["flat","thin","no volume","falling","falling out","hair loss","not bouncy"]
    },
    "Formula Exclusiva": {
        "price": 49.99,
        "keywords": ["all in one","all-in-one","everything","complete care","full repair","all problems"]
    }
}

def match_product(text):
    text=text.lower()

    # All-in-one first
    for kw in PRODUCTS["Formula Exclusiva"]["keywords"]:
        if kw in text:
            return "Formula Exclusiva"

    matches=[]
    for product,data in PRODUCTS.items():
        if product=="Formula Exclusiva":
            continue
        for kw in data["keywords"]:
            if kw in text:
                matches.append(product)

    if len(set(matches))>1:
        return "Formula Exclusiva"

    if matches:
        return matches[0]

    return None


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
    product=match_product(user_text)

    if product:
        price=PRODUCTS[product]["price"]
        message=f"I recommend {product}. It is perfect for your concern. The price is ${price}."
    else:
        message=(
            "I didn’t quite understand. "
            "You can say things like Frizz, Dry, Oily, Falling Out, "
            "or ask for an All-In-One solution."
        )

    return speak(message)


# =====================================================
# TEXT TO SPEECH
# =====================================================

def speak(message):
    speech=client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=message
    )
    audio_bytes=speech.read()
    audio_base64=base64.b64encode(audio_bytes).decode("utf-8")
    return jsonify({"text":message,"audio":audio_base64})


# =====================================================
# RUN SERVER
# =====================================================

if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
