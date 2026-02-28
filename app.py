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

def build_system_prompt(language):
    return f"""
You are a luxury AI hair advisor.

Follow this strict hierarchy:

1. Dry / Glow / Shine / Frizz / Sleek / Event → Laciador ($34.99)
2. Oily / Greasy → Gotero ($29.99)
3. Thin / Falling out / Flat → Volumizer ($39.99)
4. Restorative / Damage / Multiple problems → Formula Exclusiva ($49.99)

Rules:
- Glow NEVER equals volume.
- Restorative NEVER equals volumizing.
- Dry hair ALWAYS → Laciador.
- Always include price.
- Respond only in {language}.
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
    background:#000;
    font-family:Arial;
    color:white;
}
.halo{
    width:240px;
    height:240px;
    border-radius:50%;
    cursor:pointer;
    transition:all 2.5s ease;
    background:radial-gradient(circle,
        rgba(0,255,200,0.5) 0%,
        rgba(0,255,200,0.25) 60%,
        rgba(0,255,200,0.1) 80%,
        transparent 95%);
    box-shadow:0 0 140px rgba(0,255,200,0.6);
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
<div id="response">Tap and describe your concern.</div>

<script>

const halo = document.getElementById("halo");
const responseBox = document.getElementById("response");

let state = "idle";
let stream = null;
let recorder = null;
let audioEl = null;
let analyser = null;
let silenceTimer = null;
let fetchController = null;

const idleColor = [0,255,200];
const gold = [255,200,0];
const teal = [0,255,255];

function setColor(rgb,intensity=0.6){
    halo.style.background=`radial-gradient(circle,
        rgba(${rgb[0]},${rgb[1]},${rgb[2]},${intensity}) 0%,
        rgba(${rgb[0]},${rgb[1]},${rgb[2]},${intensity*0.5}) 60%,
        rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.1) 85%,
        transparent 100%)`;
    halo.style.boxShadow=`0 0 180px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.7)`;
}

function hardReset(){

    state="idle";

    if(fetchController){
        fetchController.abort();
        fetchController=null;
    }

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

    setColor(idleColor,0.6);
}

halo.addEventListener("click",()=>{

    if(state==="idle"){
        startRecording();
    }else{
        hardReset();
    }
});

async function startRecording(){

    hardReset();
    state="listening";
    setColor(gold,0.9);

    stream = await navigator.mediaDevices.getUserMedia({audio:true});

    recorder = new MediaRecorder(stream);
    let chunks=[];

    recorder.ondataavailable=e=>chunks.push(e.data);

    recorder.onstop=async()=>{

        state="thinking";
        setColor(teal,0.8);

        const blob=new Blob(chunks,{type:"audio/webm"});
        const form=new FormData();
        form.append("audio",blob);

        fetchController = new AbortController();

        const res=await fetch("/voice",{
            method:"POST",
            body:form,
            signal:fetchController.signal
        });

        const data=await res.json();

        responseBox.innerText=data.text;

        speak(data.audio);
    };

    recorder.start();
    detectSilence();
}

function detectSilence(){

    const ctx=new AudioContext();
    analyser=ctx.createAnalyser();
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
    setColor(teal,1);

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

        # Ignore accidental noise like "you're welcome"
        if len(user_text.split()) < 3:
            return jsonify({
                "text":"I didn't quite catch that. Please describe your hair concern.",
                "audio":""
            })

        completion=client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role":"system","content":build_system_prompt("English")},
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
        return jsonify({
            "text":"Please try again.",
            "audio":""
        })


if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
