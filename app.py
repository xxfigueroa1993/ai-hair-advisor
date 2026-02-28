import os
import tempfile
import base64
from flask import Flask, request, jsonify
from openai import OpenAI

os.environ["PYTHONUNBUFFERED"] = "1"

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# =====================================================
# SYSTEM PROMPT
# =====================================================

def build_system_prompt():
    return """
You are a luxury AI hair advisor.

Strict hierarchy:

Dry / Glow / Shine / Sleek / Frizz / Event → Laciador ($34.99)
Oily / Greasy → Gotero ($29.99)
Thin / Flat / Falling out → Volumizer ($39.99)
Restorative / Damage / Multiple issues → Formula Exclusiva ($49.99)

Rules:
- Glow NEVER means volume.
- Restorative NEVER means volumizing.
- Dry hair ALWAYS Laciador.
- Always include price.
- Premium luxury tone.
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
<title>Luxury Hair AI</title>
<style>
body{
    margin:0;
    height:100vh;
    display:flex;
    justify-content:center;
    align-items:center;
    flex-direction:column;
    background:#05080a;
    font-family:Arial;
    color:white;
}

.halo{
    width:260px;
    height:260px;
    border-radius:50%;
    cursor:pointer;
    backdrop-filter:blur(25px);
    transition:all 3s ease;
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
<div id="response">Tap and describe your hair concern.</div>

<script>

const halo = document.getElementById("halo");
const responseBox = document.getElementById("response");

let stream=null;
let recorder=null;
let audioEl=null;
let silenceTimer=null;
let state="idle";

const idle=[0,255,200];
const gold=[255,210,80];
const teal=[0,255,255];

function glassGlow(rgb,intensity=0.4){

    halo.style.background=`
    radial-gradient(circle at center,
        rgba(${rgb[0]},${rgb[1]},${rgb[2]},${intensity}) 0%,
        rgba(${rgb[0]},${rgb[1]},${rgb[2]},${intensity*0.5}) 40%,
        rgba(${rgb[0]},${rgb[1]},${rgb[2]},${intensity*0.2}) 70%,
        rgba(255,255,255,0.05) 85%,
        transparent 100%)`;

    halo.style.boxShadow=`
    0 0 160px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.5),
    0 0 300px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.3)`;
}

function idlePulse(){
    if(state!=="idle") return;
    let scale=1+Math.sin(Date.now()*0.0015)*0.025;
    halo.style.transform=`scale(${scale})`;
    requestAnimationFrame(idlePulse);
}

function hardReset(){

    if(audioEl){
        audioEl.pause();
        audioEl=null;
    }

    if(recorder){
        try{ recorder.stop(); }catch{}
        recorder=null;
    }

    if(stream){
        stream.getTracks().forEach(t=>t.stop());
        stream=null;
    }

    silenceTimer=null;
    state="idle";

    glassGlow(idle,0.4);
    idlePulse();
}

halo.addEventListener("click",()=>{

    // Always start fresh — no toggle behavior
    hardReset();
    startListening();
});

async function startListening(){

    state="listening";
    glassGlow(gold,0.7);

    stream=await navigator.mediaDevices.getUserMedia({audio:true});
    recorder=new MediaRecorder(stream);
    let chunks=[];

    recorder.ondataavailable=e=>chunks.push(e.data);

    recorder.onstop=async()=>{

        state="thinking";
        glassGlow(teal,0.7);

        const blob=new Blob(chunks,{type:"audio/webm"});
        const form=new FormData();
        form.append("audio",blob);

        const res=await fetch("/voice",{method:"POST",body:form});
        const data=await res.json();

        responseBox.innerText=data.text;
        speak(data.audio);
    };

    recorder.start();
    detectSilence();
}

function detectSilence(){

    const ctx=new AudioContext();
    const analyser=ctx.createAnalyser();
    const src=ctx.createMediaStreamSource(stream);
    src.connect(analyser);
    analyser.fftSize=256;

    function loop(){

        if(state!=="listening") return;

        const data=new Uint8Array(analyser.frequencyBinCount);
        analyser.getByteFrequencyData(data);
        const volume=data.reduce((a,b)=>a+b)/data.length;

        if(volume<5){
            if(!silenceTimer){
                silenceTimer=setTimeout(()=>{
                    if(recorder && recorder.state==="recording"){
                        recorder.stop();
                    }
                },2000);
            }
        }else{
            clearTimeout(silenceTimer);
            silenceTimer=null;
        }

        requestAnimationFrame(loop);
    }

    loop();
}

function speak(b64){

    state="speaking";
    glassGlow(teal,0.9);

    if(!b64){
        hardReset();
        return;
    }

    audioEl=new Audio("data:audio/mp3;base64,"+b64);
    audioEl.volume=0;
    audioEl.play();

    let fadeIn=setInterval(()=>{
        if(audioEl.volume<1){
            audioEl.volume+=0.05;
        }else{
            clearInterval(fadeIn);
        }
    },100);

    audioEl.onended=()=>{
        let fadeOut=setInterval(()=>{
            if(audioEl.volume>0.05){
                audioEl.volume-=0.05;
            }else{
                clearInterval(fadeOut);
                hardReset();
            }
        },100);
    };
}

// Initialize
glassGlow(idle,0.4);
idlePulse();

</script>
</body>
</html>
"""

# =====================================================
# VOICE ENDPOINT
# =====================================================

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

        os.remove(path)

        user_text=transcript.strip()

        if len(user_text.split()) < 3:
            return jsonify({
                "text":"Please describe your hair concern.",
                "audio":""
            })

        completion=client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role":"system","content":build_system_prompt()},
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

    except Exception:
        return jsonify({"text":"Please try again.","audio":""})


if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
