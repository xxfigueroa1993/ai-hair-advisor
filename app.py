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
    width:380px;
    height:380px;
    display:flex;
    justify-content:center;
    align-items:center;
}

.halo{
    width:300px;
    height:300px;
    border-radius:50%;
    cursor:pointer;
    backdrop-filter:blur(40px);
    background:rgba(255,255,255,0.03);
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
let animationFrame=null;

// INITIAL COLOR (IDLE)
let currentColor=[0,255,200];

// ===============================
// TRUE SMOOTH COLOR INTERPOLATION
// ===============================

function lerp(a,b,t){ return a+(b-a)*t; }

function animateColor(targetColor,duration=8000,callback=null){

    const startColor=[...currentColor];
    const startTime=performance.now();

    function step(now){
        let progress=(now-startTime)/duration;
        if(progress>1) progress=1;

        let r=Math.floor(lerp(startColor[0],targetColor[0],progress));
        let g=Math.floor(lerp(startColor[1],targetColor[1],progress));
        let b=Math.floor(lerp(startColor[2],targetColor[2],progress));

        halo.style.background=`
            radial-gradient(circle at center,
                rgba(${r},${g},${b},0.6) 0%,
                rgba(${r},${g},${b},0.4) 40%,
                rgba(${r},${g},${b},0.2) 65%,
                transparent 85%)
        `;

        currentColor=[r,g,b];

        if(progress<1){
            requestAnimationFrame(step);
        }else{
            if(callback) callback();
        }
    }

    requestAnimationFrame(step);
}

// ===============================
// FULL ORB PULSE
// ===============================

function pulse(){
    if(state==="idle"){
        let scale=1+Math.sin(Date.now()*0.0009)*0.06;
        halo.style.transform=`scale(${scale})`;
    }
    requestAnimationFrame(pulse);
}

// ===============================
// ULTRA SLOW SYNCHRONIZED SOUND
// ===============================

function playUltraSlowTone(startFreq,endFreq,duration=6){

    const ctx=new (window.AudioContext||window.webkitAudioContext)();
    const osc=ctx.createOscillator();
    const gain=ctx.createGain();

    osc.type="sine";

    osc.frequency.setValueAtTime(startFreq,ctx.currentTime);
    osc.frequency.linearRampToValueAtTime(endFreq,ctx.currentTime+duration);

    gain.gain.setValueAtTime(0.15,ctx.currentTime);
    gain.gain.linearRampToValueAtTime(0.001,ctx.currentTime+duration);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime+duration);
}

// ===============================
// RESET TO TRUE WEBSITE STATE
// ===============================

function resetToIdle(){

    state="resetting";

    playUltraSlowTone(260,180,8);

    animateColor([0,255,200],8000,()=>{
        state="idle";
        locked=false;
        responseBox.innerText="Tap and describe your hair concern.";
    });
}

// ===============================
// CLICK HANDLER
// ===============================

halo.addEventListener("click",()=>{

    if(locked) return;
    locked=true;
    state="transition";

    responseBox.innerText="Listening...";

    // GOLD VERY SLOW
    playUltraSlowTone(200,260,8);

    animateColor([255,210,80],8000,()=>{

        responseBox.innerText="Analyzing...";

        // TEAL VERY SLOW
        playUltraSlowTone(260,330,8);

        animateColor([0,255,255],8000,()=>{

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
