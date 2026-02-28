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

/* TRANSPARENT GLASS ORB */
.halo{
    width:300px;
    height:300px;
    border-radius:50%;
    cursor:pointer;
    backdrop-filter:blur(45px);
    background:rgba(255,255,255,0.04);
    transition:transform 2s ease;
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
    <div id="halo" class="halo"></div>
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

// =================================
// COLOR INTERPOLATION (REAL GLOW)
// =================================

function lerp(a,b,t){ return a+(b-a)*t; }

function animateColor(targetColor,duration=6000,onComplete=null){

    if(activeAnimation) cancelAnimationFrame(activeAnimation);

    const startColor=[...currentColor];
    const startTime=performance.now();

    function step(now){
        let progress=(now-startTime)/duration;
        if(progress>1) progress=1;

        let r=Math.floor(lerp(startColor[0],targetColor[0],progress));
        let g=Math.floor(lerp(startColor[1],targetColor[1],progress));
        let b=Math.floor(lerp(startColor[2],targetColor[2],progress));

        // TRUE GLOW (layered shadows)
        halo.style.boxShadow = `
            0 0 80px rgba(${r},${g},${b},0.6),
            0 0 160px rgba(${r},${g},${b},0.45),
            0 0 260px rgba(${r},${g},${b},0.3)
        `;

        // Glass center glow
        halo.style.background = `
            radial-gradient(circle at center,
                rgba(${r},${g},${b},0.18) 0%,
                rgba(${r},${g},${b},0.12) 40%,
                rgba(${r},${g},${b},0.08) 70%,
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

// =================================
// PULSE ENTIRE ORB
// =================================

function pulse(){
    if(state==="idle"){
        let scale=1+Math.sin(Date.now()*0.001)*0.05;
        halo.style.transform=`scale(${scale})`;
    }
    requestAnimationFrame(pulse);
}

// =================================
// SOUND (NO OVERLAP)
// =================================

function playTone(startFreq,endFreq,duration=6){

    if(currentOsc){
        currentOsc.stop();
        currentOsc=null;
    }

    const ctx=new (window.AudioContext||window.webkitAudioContext)();
    const osc=ctx.createOscillator();
    const gain=ctx.createGain();

    osc.type="sine";

    osc.frequency.setValueAtTime(startFreq,ctx.currentTime);
    osc.frequency.linearRampToValueAtTime(endFreq,ctx.currentTime+duration);

    gain.gain.setValueAtTime(0.12,ctx.currentTime);
    gain.gain.linearRampToValueAtTime(0.001,ctx.currentTime+duration);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime+duration);

    currentOsc=osc;
}

// =================================
// RESET (INSTANT START)
// =================================

function resetToIdle(){

    state="resetting";
    locked=true;

    playTone(260,200,6);

    animateColor([0,255,200],6000,()=>{
        state="idle";
        locked=false;
        responseBox.innerText="Tap and describe your hair concern.";
    });
}

// =================================
// CLICK HANDLER
// =================================

halo.addEventListener("click",()=>{

    if(state==="transition" || state==="thinking"){
        resetToIdle();
        return;
    }

    if(locked) return;

    locked=true;
    state="transition";
    responseBox.innerText="Listening...";

    playTone(200,260,6);

    animateColor([255,210,80],6000,()=>{

        state="thinking";
        responseBox.innerText="Analyzing...";

        playTone(260,340,6);

        animateColor([0,255,255],6000,()=>{
            resetToIdle();
        });

    });
});

// INIT
animateColor([0,255,200],1);
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
