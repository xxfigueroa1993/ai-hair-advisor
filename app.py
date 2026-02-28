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

/* ONE SINGLE TRANSPARENT GLOWING ORB */
.halo{
    width:280px;
    height:280px;
    border-radius:50%;
    cursor:pointer;
    background:rgba(255,255,255,0.03);
    backdrop-filter:blur(30px);
    transition:
        box-shadow 4s ease,
        transform 2s ease;
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
let timers=[];

// COLORS
const idle=[0,255,200];
const gold=[255,210,80];
const teal=[0,255,255];

// ================================
// APPLY SUPER SOFT HALO GLOW
// ================================

function applyGlow(rgb,intensity=0.5){

    halo.style.boxShadow=
        `
        0 0 60px rgba(${rgb[0]},${rgb[1]},${rgb[2]},${intensity}),
        0 0 120px rgba(${rgb[0]},${rgb[1]},${rgb[2]},${intensity*0.5}),
        0 0 200px rgba(${rgb[0]},${rgb[1]},${rgb[2]},${intensity*0.3})
        `;
}

// ================================
// WHOLE ORB PULSE
// ================================

function pulseLoop(){
    if(state==="idle"){
        let scale=1+Math.sin(Date.now()*0.001)*0.05;
        halo.style.transform=`scale(${scale})`;
    }
    requestAnimationFrame(pulseLoop);
}

// ================================
// VERY SLOW SYNCHRONIZED SOUND
// ================================

function playSlowTone(targetFreq){

    const ctx=new (window.AudioContext||window.webkitAudioContext)();
    const osc=ctx.createOscillator();
    const gain=ctx.createGain();

    osc.type="sine";

    osc.frequency.setValueAtTime(targetFreq+100,ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(targetFreq,ctx.currentTime+2.5);

    gain.gain.setValueAtTime(0.15,ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+3);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime+3);
}

// ================================
// RESET TO WEBSITE OPEN STATE
// ================================

function resetToIdle(){

    timers.forEach(t=>clearTimeout(t));
    timers=[];

    state="idle";

    // SUPER SLOW fade back
    applyGlow(idle,0.6);
    playSlowTone(200);

    setTimeout(()=>{
        locked=false; // unlock only AFTER fade completes
    },4000);

    responseBox.innerText="Tap and describe your hair concern.";
}

// ================================
// CLICK HANDLER
// ================================

halo.addEventListener("click",()=>{

    if(locked) return;

    locked=true;
    state="transition";

    // SLOW GOLD TRANSITION
    applyGlow(gold,0.7);
    playSlowTone(260);

    timers.push(setTimeout(()=>{

        // SLOW TEAL TRANSITION
        state="thinking";
        applyGlow(teal,0.85);
        playSlowTone(320);

        timers.push(setTimeout(()=>{

            resetToIdle();

        },4500));

    },4500));
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
