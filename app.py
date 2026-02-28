import os
import tempfile
import base64
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# ----------------------------
# PRODUCT DATABASE
# ----------------------------

PRODUCTS = {
    "Laciador": {
        "price": "$34.99",
        "description": "Delivers a sleek, smooth finish with frizz control and elegant shine."
    },
    "Gotero": {
        "price": "$29.99",
        "description": "Balances excess oil while nourishing the scalp for a fresh, clean feel."
    },
    "Volumizer": {
        "price": "$39.99",
        "description": "Boosts thickness and restores body to thinning or fine hair."
    },
    "Formula Exclusiva": {
        "price": "$49.99",
        "description": "Our premium all-in-one restorative formula for complete hair revival."
    }
}


def route_product(text):
    t = text.lower()

    if any(x in t for x in ["event","party","wedding","date","sleek","smooth","frizz","bounce","bouncy"]):
        return "Laciador"

    if any(x in t for x in ["oily","greasy"]):
        return "Gotero"

    if any(x in t for x in ["thin","thinning","hair loss","bald","falling out"]):
        return "Volumizer"

    return "Formula Exclusiva"


# ----------------------------
# FRONTEND
# ----------------------------

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
flex-direction:column;font-family:Arial;
color:white;
overflow:hidden;
}

.halo{
width:260px;height:260px;
border-radius:50%;
cursor:pointer;
position:relative;
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

const halo=document.getElementById("halo");

let state="idle";
let audioElement=null;
let silenceTimer=null;
let streamRef=null;
let recorderRef=null;

let current=[0,255,200];
let target=[0,255,200];
let intensity=0.7;
let targetIntensity=0.7;
let pulse=1;
let pulseTarget=1.05;  // default idle pulse

function lerp(a,b,t){return a+(b-a)*t;}

function animate(){

    for(let i=0;i<3;i++)
        current[i]=lerp(current[i],target[i],0.05);

    intensity=lerp(intensity,targetIntensity,0.05);
    pulse=lerp(pulse,pulseTarget,0.1);

    // Thick smooth glow (NO border)
    halo.style.background =
    `radial-gradient(circle,
        rgba(${current[0]},${current[1]},${current[2]},${intensity}) 0%,
        rgba(${current[0]},${current[1]},${current[2]},${intensity*0.6}) 50%,
        rgba(${current[0]},${current[1]},${current[2]},${intensity*0.2}) 80%,
        rgba(${current[0]},${current[1]},${current[2]},0) 100%)`;

    halo.style.boxShadow =
    `0 0 120px rgba(${current[0]},${current[1]},${current[2]},${intensity*0.6}),
     0 0 240px rgba(${current[0]},${current[1]},${current[2]},${intensity*0.4})`;

    halo.style.transform=`scale(${pulse})`;

    requestAnimationFrame(animate);
}
animate();


function resetState(){

    state="idle";
    target=[0,255,200];
    targetIntensity=0.7;
    pulseTarget=1.05;

    if(audioElement){
        audioElement.pause();
        audioElement=null;
    }

    if(streamRef){
        streamRef.getTracks().forEach(t=>t.stop());
        streamRef=null;
    }

    silenceTimer=null;
}


halo.addEventListener("click",()=>{

    resetState();

    if(state==="idle"){
        startListening();
    }
});


async function startListening(){

    try{

        state="listening";
        target=[255,200,0];
        targetIntensity=1.2;
        pulseTarget=1.1;

        streamRef=await navigator.mediaDevices.getUserMedia({audio:true});

        const audioCtx=new AudioContext();
        const analyser=audioCtx.createAnalyser();
        analyser.fftSize=256;
        const src=audioCtx.createMediaStreamSource(streamRef);
        src.connect(analyser);

        recorderRef=new MediaRecorder(streamRef);
        let chunks=[];

        recorderRef.ondataavailable=e=>chunks.push(e.data);

        recorderRef.onstop=async()=>{

            state="thinking";
            target=[0,255,255];

            const blob=new Blob(chunks,{type:"audio/webm"});
            const form=new FormData();
            form.append("audio",blob);

            const res=await fetch("/voice",{method:"POST",body:form});
            const data=await res.json();

            document.getElementById("response").innerText=data.text;
            speakAI(data.audio);
        };

        recorderRef.start();

        function detect(){

            if(state!=="listening") return;

            const data=new Uint8Array(analyser.frequencyBinCount);
            analyser.getByteFrequencyData(data);
            let volume=data.reduce((a,b)=>a+b)/data.length;

            pulseTarget=1+volume/120;

            if(volume<5){
                if(!silenceTimer){
                    silenceTimer=setTimeout(()=>{
                        recorderRef.stop();
                    },2000);
                }
            }else{
                clearTimeout(silenceTimer);
                silenceTimer=null;
            }

            requestAnimationFrame(detect);
        }

        detect();

    }catch(e){
        console.log(e);
        resetState();
    }
}


function speakAI(b64){

    state="speaking";
    target=[120,255,255];
    pulseTarget=1.1;

    audioElement=new Audio("data:audio/mp3;base64,"+b64);
    audioElement.play();

    audioElement.onended=()=>{
        resetState();
    };
}

</script>
</body>
</html>
"""


# ----------------------------
# VOICE ROUTE
# ----------------------------

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

        os.remove(path)  # CLEANUP FIX

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

    except Exception as e:
        return jsonify({
            "text":"Sorry, something went wrong. Please try again.",
            "audio":""
        })


if __name__=="__main__":
    app.run(host="0.0.0.0",port=10000)
