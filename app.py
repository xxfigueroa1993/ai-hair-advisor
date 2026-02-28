import os
from flask import Flask, jsonify

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

const halo=document.getElementById("halo");
const responseBox=document.getElementById("response");

let state="idle";
let locked=false;
let currentColor=[0,255,200];
let activeAnimation=null;
let currentOsc=null;

const FADE_DURATION=1750;

// ==========================
// COLOR FADE
// ==========================

function lerp(a,b,t){ return a+(b-a)*t; }

function animateColor(targetColor,onComplete=null){

    if(activeAnimation) cancelAnimationFrame(activeAnimation);

    const startColor=[...currentColor];
    const startTime=performance.now();

    function step(now){
        let progress=(now-startTime)/FADE_DURATION;
        if(progress>1) progress=1;

        let r=Math.floor(lerp(startColor[0],targetColor[0],progress));
        let g=Math.floor(lerp(startColor[1],targetColor[1],progress));
        let b=Math.floor(lerp(startColor[2],targetColor[2],progress));

        halo.style.boxShadow = `
            0 0 100px rgba(${r},${g},${b},0.55),
            0 0 220px rgba(${r},${g},${b},0.35),
            0 0 320px rgba(${r},${g},${b},0.25)
        `;

        halo.style.background = `
            radial-gradient(circle at center,
                rgba(${r},${g},${b},0.32) 0%,
                rgba(${r},${g},${b},0.22) 50%,
                rgba(${r},${g},${b},0.15) 75%,
                rgba(${r},${g},${b},0.10) 100%)
        `;

        currentColor=[r,g,b];

        if(progress<1){
            activeAnimation=requestAnimationFrame(step);
        }else{
            activeAnimation=null;
            if(onComplete) onComplete();
        }
    }

    activeAnimation=requestAnimationFrame(step);
}

// ==========================
// PULSE
// ==========================

function pulse(){
    if(state==="idle"){
        let scale=1+Math.sin(Date.now()*0.0012)*0.04;
        halo.style.transform=`scale(${scale})`;
    }
    requestAnimationFrame(pulse);
}

// ==========================
// SOUNDS
// ==========================

// Click sound (unchanged)
function playClickSound(){

    if(currentOsc){
        currentOsc.stop();
        currentOsc=null;
    }

    const ctx=new (window.AudioContext||window.webkitAudioContext)();
    const osc=ctx.createOscillator();
    const gain=ctx.createGain();

    osc.type="sine";
    osc.frequency.setValueAtTime(220,ctx.currentTime);
    osc.frequency.linearRampToValueAtTime(300,ctx.currentTime+1.75);

    gain.gain.setValueAtTime(0.12,ctx.currentTime);
    gain.gain.linearRampToValueAtTime(0.001,ctx.currentTime+1.75);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime+1.75);

    currentOsc=osc;
}

// Totally different AI completion sound
function playCompletionSound(){

    const ctx=new (window.AudioContext||window.webkitAudioContext)();

    const osc=ctx.createOscillator();
    const gain=ctx.createGain();

    osc.type="triangle";   // different waveform

    osc.frequency.setValueAtTime(600,ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(1200,ctx.currentTime+0.4);

    gain.gain.setValueAtTime(0.15,ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+0.6);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime+0.6);
}

// ==========================
// VOICE RESPONSE
// ==========================

function speak(text){

    const utterance=new SpeechSynthesisUtterance(text);
    utterance.rate=0.95;
    utterance.pitch=1.0;
    utterance.volume=1.0;

    speechSynthesis.cancel();
    speechSynthesis.speak(utterance);

    utterance.onend=()=>{
        playCompletionSound();
        setTimeout(resetToIdle,400);
    };
}

// ==========================
// RESET
// ==========================

function resetToIdle(){

    state="resetting";
    locked=true;

    animateColor([0,255,200],()=>{
        state="idle";
        locked=false;
        responseBox.innerText="Tap and describe your hair concern.";
    });
}

// ==========================
// CLICK
// ==========================

halo.addEventListener("click",()=>{

    if(state==="transition" || state==="thinking"){
        resetToIdle();
        return;
    }

    if(locked) return;

    locked=true;
    state="transition";
    responseBox.innerText="Listening...";

    playClickSound();

    animateColor([255,210,80],()=>{

        // 3 second silence before analyzing
        setTimeout(()=>{

            state="thinking";
            responseBox.innerText="Analyzing...";

            animateColor([0,255,255],()=>{

                const aiText="I didn’t hear you. Can you please share your hair concerns for a recommendation?";
                responseBox.innerText=aiText;

                speak(aiText);

            });

        },3000); // 3 second delay

    });

});

// INIT
animateColor([0,255,200]);
pulse();

</script>
</body>
</html>
"""

@app.route("/voice",methods=["POST"])
def voice():
    return jsonify({"text":"Voice endpoint active.","audio":""})

if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
