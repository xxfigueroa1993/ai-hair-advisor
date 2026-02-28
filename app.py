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
let noSpeechTimer=null;
let transcript="";
let speaking=false;

// =====================
// DEEP BREATHING PULSE
// =====================

function pulse(){
    let intensity=0.05;
    let speed=0.0012;

    if(state==="listening") intensity=0.085;
    if(state==="speaking") intensity=0.11;

    let scale=1+Math.sin(Date.now()*speed)*intensity;
    halo.style.transform=`scale(${scale})`;

    requestAnimationFrame(pulse);
}

// =====================
// PRODUCT ENGINE
// =====================

function chooseProduct(text){

text=text.toLowerCase().trim();

if(text.length<12) return null;

if(text.includes("under 16") && text.includes("color")){
return "For clients under sixteen experiencing pigment changes, we strongly recommend consulting a licensed medical professional before cosmetic treatment.";
}

const issues={
dry:{
name:"Laciador",
desc:"Dry hair indicates cuticle dehydration. Laciador restores moisture balance and smoothness.",
price:"$48"
},
oily:{
name:"Gotero",
desc:"Oily scalp imbalance requires lightweight regulation. Gotero balances sebum without stripping hydration.",
price:"$42"
},
damaged:{
name:"Formula Exclusiva",
desc:"Structural damage affects protein bonds. Formula Exclusiva rebuilds strength and elasticity.",
price:"$65"
},
fall:{
name:"Formula Exclusiva",
desc:"Shedding and breakage require strengthening at the root level. Formula Exclusiva supports healthier cycles.",
price:"$65"
},
color:{
name:"Gotika",
desc:"Color fading occurs from oxidation and UV exposure. Gotika restores vibrancy and pigment longevity.",
price:"$54"
}
};

for(let key in issues){
if(text.includes(key)){
let p=issues[key];
return p.name+". "+p.desc+" Professional price point: "+p.price+".";
}
}

return null;
}

// =====================
// VOICE SELECTION
// =====================

function getBestVoice(){
let voices=speechSynthesis.getVoices();

let preferred=
voices.find(v=>v.name.includes("Google UK English Female")) ||
voices.find(v=>v.name.includes("Samantha")) ||
voices.find(v=>v.name.toLowerCase().includes("female"));

return preferred || voices[0];
}

function speak(text){

speechSynthesis.cancel();

const utter=new SpeechSynthesisUtterance(text);
utter.voice=getBestVoice();
utter.rate=0.9;
utter.pitch=1.05;
utter.volume=1;

state="speaking";
speaking=true;

speechSynthesis.speak(utter);

utter.onend=()=>{
speaking=false;
state="idle";
responseBox.innerText="Tap and describe your hair concern.";
};
}

// =====================
// LISTENING SYSTEM
// =====================

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
clearTimeout(noSpeechTimer);

let interim="";

for(let i=event.resultIndex;i<event.results.length;i++){
if(event.results[i].isFinal){
transcript+=event.results[i][0].transcript+" ";
}else{
interim+=event.results[i][0].transcript;
}
}

silenceTimer=setTimeout(()=>{
recognition.stop();
handleFinalTranscript(transcript.trim());
},2500);

};

recognition.start();

// 3.5s full silence fallback
noSpeechTimer=setTimeout(()=>{
if(transcript.trim().length<5){
recognition.stop();
speak("I didn’t hear anything. Could you please describe your specific hair concern?");
}
},3500);
}

// =====================
// PROCESS FINAL SPEECH
// =====================

function handleFinalTranscript(text){

if(!text || text.length<10){
speak("I didn’t catch that clearly. Could you describe a specific hair concern?");
return;
}

responseBox.innerText="Analyzing...";

setTimeout(()=>{

const result=chooseProduct(text);

if(!result){
speak("I didn’t catch a specific hair issue. Could you clarify whether it's dryness, oiliness, damage, color fading, or shedding?");
return;
}

responseBox.innerText=result;
speak(result);

},3000);
}

// =====================
// CLICK HANDLER
// =====================

halo.addEventListener("click",()=>{

if(state==="listening"){
recognition.stop();
state="idle";
responseBox.innerText="Tap and describe your hair concern.";
return;
}

if(state==="speaking"){
speechSynthesis.cancel();
state="idle";
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
