from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI
import os, tempfile, base64

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route("/")
def index():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Clinical AI Hair Specialist</title>

<style>
body{
    margin:0;
    background:linear-gradient(to bottom,#f7fbff,#eaf4fc);
    display:flex;
    flex-direction:column;
    justify-content:center;
    align-items:center;
    height:100vh;
    font-family:Arial;
    color:#1a2b3c;
}

h1{
    font-weight:600;
    margin-bottom:40px;
}

#scene{
    perspective:1000px;
}

#halo-wrapper{
    width:260px;
    height:260px;
    position:relative;
    transform-style:preserve-3d;
}

.ring{
    position:absolute;
    width:100%;
    height:100%;
    border-radius:50%;
    border:5px solid rgba(0,140,255,0.25);
    box-shadow:0 0 30px rgba(0,140,255,0.2);
    transition:all .15s linear;
}

#ring-outer{
    transform:rotateX(60deg);
}

#ring-inner{
    transform:rotateY(60deg);
    border-color:rgba(0,180,255,0.4);
}

#center-core{
    position:absolute;
    width:60%;
    height:60%;
    border-radius:50%;
    top:20%;
    left:20%;
    background:radial-gradient(circle,white,#dcefff);
    box-shadow:0 0 40px rgba(0,140,255,0.3);
}

.recording .ring{
    border-color:rgba(255,0,0,0.5);
    box-shadow:0 0 50px rgba(255,0,0,0.3);
}

.processing .ring{
    animation:spin 3s linear infinite;
}

@keyframes spin{
    from{ transform:rotateY(0deg); }
    to{ transform:rotateY(360deg); }
}

select{
    margin-top:30px;
    padding:10px 15px;
    border-radius:8px;
    border:1px solid #cde0f5;
    background:white;
}

#status{
    margin-top:30px;
    max-width:420px;
    text-align:center;
    font-size:15px;
    opacity:0.85;
}
</style>
</head>
<body>

<h1>Clinical AI Hair Specialist</h1>

<div id="scene">
    <div id="halo-wrapper">
        <div id="ring-outer" class="ring"></div>
        <div id="ring-inner" class="ring"></div>
        <div id="center-core"></div>
    </div>
</div>

<select id="language">
<option value="en">English</option>
<option value="es">Spanish</option>
<option value="fr">French</option>
<option value="de">German</option>
<option value="pt">Portuguese</option>
<option value="it">Italian</option>
<option value="zh">Chinese</option>
<option value="ar">Arabic</option>
</select>

<div id="status">Tap Halo to Begin Consultation</div>

<script>

let mediaRecorder;
let audioChunks=[];
let analyser;
let silenceTimer;
let audioContext;

const wrapper=document.getElementById("halo-wrapper");
const outer=document.getElementById("ring-outer");
const inner=document.getElementById("ring-inner");
const status=document.getElementById("status");
const language=document.getElementById("language");

const SILENCE_THRESHOLD = 15;
const SILENCE_TIME = 1500;

wrapper.onclick = async ()=>{

    if(wrapper.classList.contains("recording")){
        mediaRecorder.stop();
        return;
    }

    silenceTimer=null;

    const stream = await navigator.mediaDevices.getUserMedia({audio:true});
    audioContext = new AudioContext();
    const source = audioContext.createMediaStreamSource(stream);

    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);

    mediaRecorder = new MediaRecorder(stream);
    audioChunks=[];

    mediaRecorder.ondataavailable=e=>audioChunks.push(e.data);

    mediaRecorder.onstop = async ()=>{

        stream.getTracks().forEach(track=>track.stop());
        audioContext.close();

        wrapper.classList.remove("recording");
        wrapper.classList.add("processing");
        status.innerText="Analyzing...";

        const blob=new Blob(audioChunks,{type:"audio/webm"});
        const formData=new FormData();
        formData.append("audio",blob);
        formData.append("language",language.value);

        const response=await fetch("/process",{method:"POST",body:formData});
        const data=await response.json();

        status.innerText=data.text;

        const audio=new Audio("data:audio/mp3;base64,"+data.audio);

        syncVoicePulse(audio);

        audio.play();
        wrapper.classList.remove("processing");
    };

    mediaRecorder.start();
    wrapper.classList.add("recording");
    status.innerText="Listening...";

    monitorMic();
};

function monitorMic(){
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    function detect(){
        if(!mediaRecorder || mediaRecorder.state!=="recording") return;

        analyser.getByteFrequencyData(dataArray);
        let avg=dataArray.reduce((a,b)=>a+b)/bufferLength;

        let scale = 1 + avg/200;
        outer.style.transform="rotateX(60deg) scale("+scale+")";
        inner.style.transform="rotateY(60deg) scale("+scale+")";

        if(avg<SILENCE_THRESHOLD){
            if(!silenceTimer){
                silenceTimer=setTimeout(()=>{
                    if(mediaRecorder.state==="recording"){
                        mediaRecorder.stop();
                    }
                },SILENCE_TIME);
            }
        }else{
            clearTimeout(silenceTimer);
            silenceTimer=null;
        }

        requestAnimationFrame(detect);
    }
    detect();
}

function syncVoicePulse(audio){

    const ctx=new AudioContext();
    const src=ctx.createMediaElementSource(audio);
    const analyserVoice=ctx.createAnalyser();
    analyserVoice.fftSize=256;

    src.connect(analyserVoice);
    analyserVoice.connect(ctx.destination);

    const bufferLength=analyserVoice.frequencyBinCount;
    const dataArray=new Uint8Array(bufferLength);

    function pulse(){
        analyserVoice.getByteFrequencyData(dataArray);
        let avg=dataArray.reduce((a,b)=>a+b)/bufferLength;
        let scale=1+avg/300;

        outer.style.transform="rotateX(60deg) scale("+scale+")";
        inner.style.transform="rotateY(60deg) scale("+scale+")";

        if(!audio.paused){
            requestAnimationFrame(pulse);
        }
    }
    pulse();
}

</script>
</body>
</html>
""")


@app.route("/process", methods=["POST"])
def process_audio():

    audio_file = request.files["audio"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        audio_file.save(tmp.name)

        with open(tmp.name, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )

    user_text = transcript.text.strip()

    if not user_text:
        reply_text = "Please describe your hair concern clearly so I can recommend a clinical solution."
    else:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role":"system",
                    "content":"""
You are an elite clinical salon hair expert.

Do not greet.
Provide direct hair solutions.
Recommend a professional product.
If clearly unrelated to hair, politely redirect to hair consultation.
"""
                },
                {"role":"user","content":user_text}
            ]
        )
        reply_text = completion.choices[0].message.content

    voice="alloy"
    if any(word in reply_text.lower() for word in ["damage","breakage","loss"]):
        voice="verse"

    speech=client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice=voice,
        input=reply_text
    )

    audio_bytes=speech.read()
    encoded=base64.b64encode(audio_bytes).decode("utf-8")

    return jsonify({"text":reply_text,"audio":encoded})


if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
