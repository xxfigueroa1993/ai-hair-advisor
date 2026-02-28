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

#languageSelect{
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
    transition:transform 0.4s ease;
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

<select id="languageSelect">
<option>English</option>
<option>Spanish</option>
<option>French</option>
<option>Arabic</option>
<option>Mandarin</option>
<option>Hindi</option>
<option>Portuguese</option>
</select>

<div class="wrapper">
<div id="halo"></div>
</div>

<div id="response">Tap and describe your hair concern.</div>

<script>

const halo=document.getElementById("halo");
const responseBox=document.getElementById("response");

let state="idle";
let recognition=null;
let silenceTimer=null;
let transcript="";
let lastSpeechTime=0;

// ==========================
// DEEPER PULSE ENGINE
// ==========================

function pulse(){
    let speed=0.0012;
    let intensity=0.06;

    if(state==="listening") intensity=0.09;
    if(state==="speaking") intensity=0.11;

    let scale=1+Math.sin(Date.now()*speed)*intensity;
    halo.style.transform=`scale(${scale})`;

    requestAnimationFrame(pulse);
}

// ==========================
// PRODUCT ENGINE
// ==========================

function chooseProduct(text){

text=text.toLowerCase();

const vague = text.length < 8;

if(vague){
return null;
}

if(text.includes("under 16") && text.includes("color")){
return "For individuals under sixteen experiencing pigment changes, we recommend consulting a licensed medical professional before cosmetic treatment.";
}

if(text.includes("dry"))
return "Laciador. Dry hair indicates moisture depletion within the cuticle layer. Laciador restores hydration balance and improves elasticity. Price point: $48 professional size.";

if(text.includes("oily"))
return "Gotero. Oily scalp imbalance requires lightweight regulation. Gotero balances sebum production without stripping protective lipids. Price point: $42 professional size.";

if(text.includes("damaged"))
return "Formula Exclusiva. Structural damage affects internal protein bonds. Formula Exclusiva rebuilds strength, resilience, and shine. Price point: $65 professional treatment.";

if(text.includes("fall"))
return "Formula Exclusiva. Shedding and breakage require bond reinforcement and scalp support. Formula Exclusiva strengthens the growth cycle. Price point: $65 professional treatment.";

if(text.includes("color"))
return "Gotika. Color fading results from oxidation and cuticle wear. Gotika restores vibrancy and enhances pigment longevity. Price point: $54 professional size.";

return null;
}

// ==========================
// VOICE (BRIGHTER SELECTION)
// ==========================

function speak(text){

speechSynthesis.cancel();

const utter=new SpeechSynthesisUtterance(text);
utter.rate=0.92;
utter.pitch=1.08;
utter.volume=1;

let voices=speechSynthesis.getVoices();

let preferred = voices.find(v =>
v.name.includes("Samantha") ||
v.name.includes("Google UK English Female") ||
v.name.toLowerCase().includes("female")
);

if(preferred) utter.voice=preferred;

state="speaking";
speechSynthesis.speak(utter);

utter.onend=()=>{
state="idle";
responseBox.innerText="Tap and describe your hair concern.";
};

}

// ==========================
// LISTENING
// ==========================

function startListening(){

const SpeechRecognition =
window.SpeechRecognition || window.webkitSpeechRecognition;

recognition=new SpeechRecognition();
recognition.continuous=true;
recognition.interimResults=true;
recognition.lang="en-US";

transcript="";
state="listening";
responseBox.innerText="Listening...";

recognition.onresult=function(event){

clearTimeout(silenceTimer);

for(let i=event.resultIndex;i<event.results.length;i++){
if(event.results[i].isFinal){
transcript+=event.results[i][0].transcript+" ";
}
}

silenceTimer=setTimeout(()=>{
recognition.stop();
processSpeech(transcript.trim());
},2500);

};

recognition.start();

// 3.5 sec fallback if nothing meaningful
setTimeout(()=>{
if(state==="listening" && transcript.length<5){
recognition.stop();
speak("I didn’t hear anything. Could you please describe your specific hair concern?");
}
},3500);

}

// ==========================
// PROCESS SPEECH
// ==========================

function processSpeech(text){

if(!text || text.length<5){
speak("I didn’t catch that clearly. Could you describe a specific hair problem?");
return;
}

responseBox.innerText="Analyzing...";

setTimeout(()=>{

const reply=chooseProduct(text);

if(!reply){
speak("I didn’t catch that clearly. Could you describe a specific hair problem?");
return;
}

responseBox.innerText=reply;
speak(reply);

},3000);

}

// ==========================
// CLICK
// ==========================

halo.addEventListener("click",()=>{

if(state==="listening"){
recognition.stop();
state="idle";
responseBox.innerText="Tap and describe your hair concern.";
return;
}

startListening();

});

pulse();

</script>
</body>
</html>
"""

if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
