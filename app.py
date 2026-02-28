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
    position:relative;
    width:420px;
    height:420px;
    display:flex;
    justify-content:center;
    align-items:center;
}

.halo{
    width:300px;
    height:300px;
    border-radius:50%;
    cursor:pointer;
    backdrop-filter:blur(60px);
    background:rgba(255,255,255,0.04);
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

const FADE_DURATION=1750; // 1.3x faster

// ==========================
// COLOR INTERPOLATION
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
            0 0 80px rgba(${r},${g},${b},0.45),
            0 0 160px rgba(${r},${g},${b},0.35),
            0 0 260px rgba(${r},${g},${b},0.25)
        `;

        /* Inner glow now 3x MORE transparent */
        halo.style.background = `
            radial-gradient(circle at center,
                rgba(${r},${g},${b},0.10) 0%,
                rgba(${r},${g},${b},0.07) 45%,
                rgba(${r},${g},${b},0.04) 75%,
                rgba(255,255,255,0.03) 100%)
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
        let scale=1+Math.sin(Date.now()*0.0012)*0.05;
        halo.style.transform=`scale(${scale})`;
    }
    requestAnimationFrame(pulse);
}

// ==========================
// SOUND (Controlled)
// ==========================

function playTone(startFreq,endFreq){

    if(currentOsc){
        currentOsc.stop();
        currentOsc=null;
    }

    const ctx=new (window.AudioContext||window.webkitAudioContext)();
    const osc=ctx.createOscillator();
    const gain=ctx.createGain();

    osc.type="sine";

    osc.frequency.setValueAtTime(startFreq,ctx.currentTime);
    osc.frequency.linearRampToValueAtTime(endFreq,ctx.currentTime+FADE_DURATION/1000);

    gain.gain.setValueAtTime(0.12,ctx.currentTime);
    gain.gain.linearRampToValueAtTime(0.001,ctx.currentTime+FADE_DURATION/1000);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime+FADE_DURATION/1000);

    currentOsc=osc;
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
// CLICK HANDLER
// ==========================

halo.addEventListener("click",()=>{

    // SECOND CLICK → RESET ONLY (NO SOUND)
    if(state==="transition" || state==="thinking"){
        resetToIdle();
        return;
    }

    if(locked) return;

    locked=true;
    state="transition";
    responseBox.innerText="Listening...";

    // Sound #1 (only on first click)
    playTone(220,300);

    animateColor([255,210,80],()=>{

        state="thinking";
        responseBox.innerText="Analyzing...";

        animateColor([0,255,255],()=>{

            // Simulate AI finished speaking
            setTimeout(()=>{

                responseBox.innerText=
                "I didn’t hear you. Can you please share your hair concerns for a recommendation?";

                // Sound #2 only when AI finishes
                playTone(380,240);

                setTimeout(()=>{
                    resetToIdle();
                },500);

            },800);

        });

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
