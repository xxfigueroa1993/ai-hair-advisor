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
    width:360px;
    height:360px;
    display:flex;
    justify-content:center;
    align-items:center;
}

/* MASSIVE BLURRED OUTER HALO */
.outerGlow{
    position:absolute;
    width:360px;
    height:360px;
    border-radius:50%;
    pointer-events:none;
    filter:blur(110px);
    opacity:0.9;
    transition:background 2.8s ease;
}

/* TRUE THICK RING (transparent inside) */
.ring{
    position:absolute;
    width:300px;
    height:300px;
    border-radius:50%;
    pointer-events:none;
    transition:box-shadow 2.8s ease;
}

/* GLASS INNER ORB */
.halo{
    width:220px;
    height:220px;
    border-radius:50%;
    cursor:pointer;
    backdrop-filter:blur(25px);
    background:rgba(255,255,255,0.05);
    transition:transform 0.3s ease;
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
    <div id="outerGlow" class="outerGlow"></div>
    <div id="ring" class="ring"></div>
    <div id="halo" class="halo"></div>
</div>

<div id="response">Tap and describe your hair concern.</div>

<script>

const halo=document.getElementById("halo");
const ring=document.getElementById("ring");
const outerGlow=document.getElementById("outerGlow");
const responseBox=document.getElementById("response");

let state="idle";
let locked=false;
let phaseTimer1=null;
let phaseTimer2=null;

// COLORS
const idle=[0,255,200];
const gold=[255,210,80];
const teal=[0,255,255];

// =================================
// APPLY GLOW TO THICK RING
// =================================

function applyGlow(rgb,intensity=0.6){

    ring.style.boxShadow=
        `0 0 0 25px rgba(${rgb[0]},${rgb[1]},${rgb[2]},${intensity})`;

    outerGlow.style.background=
        `radial-gradient(circle,
            rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.7) 0%,
            rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.4) 40%,
            transparent 80%)`;
}

// =================================
// IDLE PULSE
// =================================

function pulseLoop(){
    if(state==="idle"){
        let scale=1+Math.sin(Date.now()*0.0018)*0.05;
        halo.style.transform=`scale(${scale})`;
    }else{
        halo.style.transform="scale(1)";
    }
    requestAnimationFrame(pulseLoop);
}

// =================================
// SLOWER LUXURY CLICK SOUND
// =================================

function playClick(){
    const ctx=new (window.AudioContext||window.webkitAudioContext)();
    const osc=ctx.createOscillator();
    const gain=ctx.createGain();

    osc.type="sine";
    osc.frequency.setValueAtTime(300,ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(180,ctx.currentTime+0.35);

    gain.gain.setValueAtTime(0.12,ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+0.4);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime+0.4);
}

// =================================
// HARD RESET → THEN SLOW FADE TO IDLE
// =================================

function resetToIdle(){

    clearTimeout(phaseTimer1);
    clearTimeout(phaseTimer2);

    locked=false;
    state="idle";

    // Immediately stop pulse jump
    halo.style.transform="scale(1)";

    // Slow fade back to idle color
    applyGlow(idle,0.6);

    responseBox.innerText="Tap and describe your hair concern.";
}

// =================================
// CLICK HANDLER
// =================================

halo.addEventListener("click",()=>{

    playClick();

    // SECOND CLICK → FORCE RESET
    if(locked){
        resetToIdle();
        return;
    }

    locked=true;
    state="listening";
    applyGlow(gold,0.75);

    phaseTimer1=setTimeout(()=>{
        state="thinking";
        applyGlow(teal,0.85);

        phaseTimer2=setTimeout(()=>{
            resetToIdle();
        },3500);

    },2500);
});

// INIT
applyGlow(idle,0.6);
pulseLoop();

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
