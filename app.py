import os
from flask import Flask, jsonify

os.environ["PYTHONUNBUFFERED"] = "1"

app = Flask(__name__)

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

.wrapper{
    position:relative;
    width:340px;
    height:340px;
    display:flex;
    justify-content:center;
    align-items:center;
}

/* Thick luxury outer halo */
.outerGlow{
    position:absolute;
    width:340px;
    height:340px;
    border-radius:50%;
    pointer-events:none;
    filter:blur(90px);
    opacity:0.9;
    transition:background 2.5s ease;
}

/* Inner glass orb */
.halo{
    width:260px;
    height:260px;
    border-radius:50%;
    cursor:pointer;
    backdrop-filter:blur(25px);
    transition:background 2.5s ease, transform 0.3s ease;
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
    <div id="halo" class="halo"></div>
</div>

<div id="response">Tap and describe your hair concern.</div>

<script>

const halo=document.getElementById("halo");
const outerGlow=document.getElementById("outerGlow");
const responseBox=document.getElementById("response");

let state="idle";
let locked=false;

// COLORS
const idle=[0,255,200];
const gold=[255,210,80];
const teal=[0,255,255];

// ==============================================
// APPLY GLOW
// ==============================================

function applyGlow(rgb,intensity=0.5){

    halo.style.background=`
    radial-gradient(circle at center,
        rgba(${rgb[0]},${rgb[1]},${rgb[2]},${intensity}) 0%,
        rgba(${rgb[0]},${rgb[1]},${rgb[2]},${intensity*0.5}) 50%,
        transparent 100%)`;

    outerGlow.style.background=`
    radial-gradient(circle,
        rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.65) 0%,
        rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.35) 45%,
        transparent 80%)`;
}

// ==============================================
// IDLE PULSE LOOP
// ==============================================

function pulseLoop(){
    if(state==="idle"){
        let scale=1+Math.sin(Date.now()*0.002)*0.04;
        halo.style.transform=`scale(${scale})`;
    } else {
        halo.style.transform="scale(1)";
    }
    requestAnimationFrame(pulseLoop);
}

// ==============================================
// CLICK SOUND (Web Audio - reliable)
// ==============================================

function playClick(){
    const ctx=new (window.AudioContext||window.webkitAudioContext)();
    const osc=ctx.createOscillator();
    const gain=ctx.createGain();
    osc.type="sine";
    osc.frequency.value=520;
    gain.gain.value=0.08;

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime+0.07);
}

// ==============================================
// FULL RESET TO WEBSITE-OPEN STATE
// ==============================================

function resetToIdle(){
    state="idle";
    locked=false;
    applyGlow(idle,0.4);
    responseBox.innerText="Tap and describe your hair concern.";
}

// ==============================================
// CLICK HANDLER
// ==============================================

halo.addEventListener("click",()=>{

    playClick();

    if(!locked){

        locked=true;
        state="listening";
        applyGlow(gold,0.75);

        // Simulate AI cycle
        setTimeout(()=>{
            state="thinking";
            applyGlow(teal,0.85);

            setTimeout(()=>{
                resetToIdle();
            },3000);

        },2000);

    } else {
        // Second click forces full reset
        resetToIdle();
    }
});

// INIT STATE
applyGlow(idle,0.4);
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
