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
<meta name="viewport" content="width=device-width, initial-scale=1">

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

#continentSelect{
    position:absolute;
    top:20px;
    right:20px;
    padding:8px;
    font-size:14px;
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

<select id="continentSelect">
<option>North America</option>
<option>South America</option>
<option>Europe</option>
<option>Africa</option>
<option>Asia</option>
<option>Australia</option>
<option>Antarctica</option>
</select>

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
let recognition=null;
let silenceTimer=null;
let transcript="";

const FADE_DURATION=1750;

// ==========================
// PRODUCT ENGINE (FROM SECOND FILE)
// ==========================

function chooseProduct(text){

text=text.toLowerCase();

let ageUnder16 = text.includes("under 16") || text.includes("15") || text.includes("14");

if(ageUnder16 && text.includes("loss") && text.includes("color")){
    return "For individuals under 16 experiencing sudden color loss, we recommend consulting a medical professional before using any treatment.";
}

if(text.includes("dry"))
return "Laciador. Dry hair lacks moisture retention. Laciador replenishes hydration while smoothing the hair cuticle for long-lasting manageability.";

if(text.includes("oily"))
return "Gotero. Excess oil production requires lightweight control. Gotero balances scalp oils without stripping essential hydration.";

if(text.includes("damaged"))
return "Formula Exclusiva. Damage typically affects the protein structure of the hair shaft. Formula Exclusiva restores strength, elasticity, and shine.";

if(text.includes("tangly"))
return "Laciador. Tangles are caused by raised cuticles and friction. Laciador smooths and detangles while improving comb-through efficiency.";

if(text.includes("falling"))
return "Formula Exclusiva. Hair shedding concerns require strengthening and scalp stimulation. Formula Exclusiva supports healthier growth cycles.";

if(text.includes("not bouncy"))
return "Gotero. Lack of bounce often indicates product buildup or imbalance. Gotero provides structure and lightweight lift.";

if(text.includes("loss") || text.includes("color"))
return "Gotika. Color fading results from oxidation and cuticle wear. Gotika enhances vibrancy while protecting pigment longevity.";

return "Formula Exclusiva. Based on professional salon diagnostics, your concern indicates a need for structural restoration and moisture balance.";
}

// ==========================
// COLOR ENGINE (UNCHANGED)
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
// PULSE (UNCHANGED)
// ==========================

function pulse(){
    if(state==="idle"){
        let scale=1+Math.sin(Date.now()*0.0012)*0.04;
        halo.style.transform=`scale(${scale})`;
    }
    requestAnimationFrame(pulse);
}

// ==========================
// SOUNDS (UNCHANGED)
// ==========================

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

function playCompletionSound(){

    const ctx=new (window.AudioContext||window.webkitAudioContext)();

    const osc=ctx.createOscillator();
    const gain=ctx.createGain();

    osc.type="triangle";

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
// SPEAK
// ==========================

function speak(text){

    speechSynthesis.cancel();

    const utterance=new SpeechSynthesisUtterance(text);
    utterance.rate=0.95;
    utterance.pitch=1.0;
    utterance.volume=1.0;

    speechSynthesis.speak(utterance);

    utterance.onend=()=>{
        playCompletionSound();
        setTimeout(resetToIdle,400);
    };
}

// ==========================
// RESET (NO SOUND)
// ==========================

function resetToIdle(){
    state="resetting";
    locked=true;

    if(recognition){
        recognition.stop();
        recognition=null;
    }

    animateColor([0,255,200],()=>{
        state="idle";
        locked=false;
        responseBox.innerText="Tap and describe your hair concern.";
    });
}

// ==========================
// SPEECH RECOGNITION (2.5s silence)
// ==========================

function startListening(){

const SpeechRecognition =
window.SpeechRecognition || window.webkitSpeechRecognition;

recognition=new SpeechRecognition();
recognition.continuous=true;
recognition.interimResults=true;
recognition.lang="en-US";

transcript="";

recognition.onresult=function(event){

clearTimeout(silenceTimer);

for(let i=event.resultIndex;i<event.results.length;i++){
if(event.results[i].isFinal){
transcript+=event.results[i][0].transcript+" ";
}
}

silenceTimer=setTimeout(()=>{
recognition.stop();
startThinking(transcript.trim());
},2500); // 2.5 second silence AFTER speaking

};

recognition.start();
}

// ==========================
// THINKING (3 second delay preserved)
// ==========================

function startThinking(text){

state="thinking";
responseBox.innerText="Analyzing...";

setTimeout(()=>{

animateColor([0,255,255],()=>{

const reply = text
? chooseProduct(text)
: "I didn’t hear you. Can you please share your hair concerns for a recommendation?";

responseBox.innerText=reply;
speak(reply);

});

},3000); // original 3 second delay
}

// ==========================
// CLICK
// ==========================

halo.addEventListener("click",()=>{

if(state==="thinking" || state==="transition"){
resetToIdle();
return;
}

if(locked) return;

locked=true;
state="transition";
responseBox.innerText="Listening...";

playClickSound();

animateColor([255,210,80],()=>{
startListening();
locked=false;
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
