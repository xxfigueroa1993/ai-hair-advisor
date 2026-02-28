import os
from flask import Flask

os.environ["PYTHONUNBUFFERED"] = "1"
app = Flask(__name__)

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
    overflow:hidden;
}

.wrapper{
    width:420px;
    height:420px;
    display:flex;
    justify-content:center;
    align-items:center;
}

#halo{
    width:300px;
    height:300px;
    border-radius:50%;
    cursor:pointer;
    backdrop-filter:blur(60px);
    background:rgba(0,255,200,0.22);
    transition:transform 1.2s ease;
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

<div class="wrapper">
    <div id="halo"></div>
</div>

<div id="response">Tap and describe your hair concern.</div>

<script>

const halo = document.getElementById("halo");
const responseBox = document.getElementById("response");

let state="idle";
let locked=false;
let currentColor=[0,255,200];
let recognition=null;
let silenceTimer=null;

const FADE_DURATION=1750;

// ================= COLOR =================

function lerp(a,b,t){ return a+(b-a)*t; }

function animateColor(target,onComplete=null){

    const start=[...currentColor];
    const startTime=performance.now();

    function step(now){
        let progress=(now-startTime)/FADE_DURATION;
        if(progress>1) progress=1;

        let r=Math.floor(lerp(start[0],target[0],progress));
        let g=Math.floor(lerp(start[1],target[1],progress));
        let b=Math.floor(lerp(start[2],target[2],progress));

        halo.style.boxShadow=`
            0 0 100px rgba(${r},${g},${b},0.55),
            0 0 220px rgba(${r},${g},${b},0.35),
            0 0 320px rgba(${r},${g},${b},0.25)
        `;

        halo.style.background=`
            radial-gradient(circle,
                rgba(${r},${g},${b},0.32) 0%,
                rgba(${r},${g},${b},0.22) 50%,
                rgba(${r},${g},${b},0.15) 75%,
                rgba(${r},${g},${b},0.10) 100%)
        `;

        currentColor=[r,g,b];

        if(progress<1){
            requestAnimationFrame(step);
        }else if(onComplete){
            onComplete();
        }
    }

    requestAnimationFrame(step);
}

// ================= PULSE =================

function pulse(){
    if(state==="idle"){
        let scale=1+Math.sin(Date.now()*0.0012)*0.04;
        halo.style.transform=`scale(${scale})`;
    }
    requestAnimationFrame(pulse);
}

// ================= SPEECH =================

function setupRecognition(){

    const SpeechRecognition =
        window.SpeechRecognition || window.webkitSpeechRecognition;

    if(!SpeechRecognition){
        alert("Speech recognition not supported in this browser.");
        return;
    }

    recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    let finalTranscript="";

    recognition.onresult = function(event){

        let interim="";
        for(let i=event.resultIndex;i<event.results.length;i++){
            if(event.results[i].isFinal){
                finalTranscript += event.results[i][0].transcript;
            }else{
                interim += event.results[i][0].transcript;
            }
        }

        responseBox.innerText = finalTranscript + interim;

        clearTimeout(silenceTimer);

        silenceTimer = setTimeout(()=>{
            recognition.stop();
            processSpeech(finalTranscript.trim());
        },2000); // 2 seconds silence detection
    };

    recognition.onerror = function(){
        recognition.stop();
        resetToIdle();
    };

}

// ================= PROCESS SPEECH =================

function processSpeech(text){

    if(!text){
        speak("I didn’t hear you. Please tell me your hair concerns.");
        return;
    }

    state="thinking";
    responseBox.innerText="Analyzing...";
    animateColor([0,255,255]);

    setTimeout(()=>{
        const reply = generateResponse(text);
        responseBox.innerText = reply;
        speak(reply);
    },1000);
}

function generateResponse(text){

    text = text.toLowerCase();

    if(text.includes("dry"))
        return "It sounds like you're dealing with dryness. I recommend deep hydration treatments and sulfate-free products.";

    if(text.includes("frizz"))
        return "For frizz control, I suggest smoothing serums and humidity-protection styling products.";

    if(text.includes("damage"))
        return "Hair damage requires protein repair treatments and minimal heat styling.";

    return "Thank you for sharing. Based on your concerns, I recommend a balanced strengthening and hydration routine.";
}

// ================= VOICE OUTPUT =================

function speak(text){

    const utter=new SpeechSynthesisUtterance(text);
    utter.rate=0.95;
    utter.pitch=1;

    speechSynthesis.cancel();
    speechSynthesis.speak(utter);

    utter.onend=function(){
        setTimeout(()=>{
            resetToIdle();
        },400);
    };
}

// ================= RESET =================

function resetToIdle(){
    state="idle";
    locked=false;
    responseBox.innerText="Tap and describe your hair concern.";
    animateColor([0,255,200]);
}

// ================= CLICK =================

halo.addEventListener("click",()=>{

    if(state!=="idle"){
        recognition?.stop();
        resetToIdle();
        return;
    }

    locked=true;
    state="listening";
    responseBox.innerText="Listening...";

    animateColor([255,210,80],()=>{
        setupRecognition();
        recognition.start();
    });
});

// INIT
animateColor([0,255,200]);
pulse();

</script>
</body>
</html>
"""

if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
