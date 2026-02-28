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
    transition:transform 0.2s ease;
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
let transcript="";
let silenceTimer=null;
let noSpeechTimer=null;

// ==========================
// COLOR ENGINE (unchanged style)
// ==========================

function setGlow(r,g,b){
halo.style.boxShadow=`
0 0 100px rgba(${r},${g},${b},0.55),
0 0 220px rgba(${r},${g},${b},0.35),
0 0 320px rgba(${r},${g},${b},0.25)
`;

halo.style.background=`
radial-gradient(circle at center,
rgba(${r},${g},${b},0.32) 0%,
rgba(${r},${g},${b},0.22) 50%,
rgba(${r},${g},${b},0.15) 75%,
rgba(${r},${g},${b},0.10) 100%)
`;
}

setGlow(0,255,200);

// ==========================
// PULSE ENGINE (reactive)
// ==========================

function pulse(){
let intensity=0;

if(state==="idle") intensity=0.04;
if(state==="listening") intensity=0.08;
if(state==="speaking") intensity=0.10;

let scale=1+Math.sin(Date.now()*0.002)*intensity;
halo.style.transform=`scale(${scale})`;

requestAnimationFrame(pulse);
}

pulse();

// ==========================
// PRODUCT LOGIC (expanded intelligence)
// ==========================

function chooseProduct(text){

text=text.toLowerCase();

let problems=0;
let dry = /(dry|frizz|rough|brittle|coarse|no moisture|split ends)/.test(text);
let damaged = /(damaged|break|weak|burned|overprocessed|heat damage)/.test(text);
let tangly = /(tangle|knot|hard to brush|snag|matted)/.test(text);
let color = /(color fade|fading|lost color|dull color|brassy|discolor)/.test(text);
let oily = /(oily|greasy|oil buildup|shiny scalp|too much oil)/.test(text);
let flat = /(flat|no bounce|lifeless|no volume)/.test(text);
let falling = /(falling|shedding|hair loss|thinning)/.test(text);

[dry,damaged,tangly,color,oily,flat,falling].forEach(v=>{if(v) problems++;});

if(problems===0) return null;

if(damaged || falling || problems>=3){
return "Formula Exclusiva is an all-in-one natural professional salon hair treatment that restores strength, elasticity, moisture balance, and scalp health. It is ideal for multi-problem or structurally weakened hair. Price: $65.";
}

if(color){
return "Gotika is an all-natural professional hair color treatment designed to restore vibrancy, tone correction, and long-lasting pigment protection. Price: $54.";
}

if(oily && problems>=2){
return "Formula Exclusiva balances scalp oil while repairing underlying structural stress. Price: $65.";
}

if(oily){
return "Gotero is an all-natural professional hair gel that regulates excess oil production and supports scalp clarity without stripping hydration. Price: $42.";
}

if(tangly && problems>=2){
return "Gotero smooths texture while reinforcing resilience in combination problem hair. Price: $42.";
}

if(tangly){
return "Laciador is an all-natural professional hair styler that improves smoothness, manageability, and detangling while restoring bounce. Price: $48.";
}

if(dry && problems>=2){
return "Formula Exclusiva deeply rehydrates and rebuilds dry multi-concern hair. Price: $65.";
}

if(dry){
return "Laciador is an all-natural professional hair styler that restores moisture, softness, and healthy bounce to dry hair. Price: $48.";
}

if(flat){
return "Laciador enhances body, softness, and natural movement for hair lacking bounce. Price: $48.";
}

return null;
}

// ==========================
// SPEECH
// ==========================

function speak(text){

speechSynthesis.cancel();

const utter=new SpeechSynthesisUtterance(text);
utter.rate=0.95;
utter.pitch=1.02;

state="speaking";
setGlow(0,200,255);

speechSynthesis.speak(utter);

utter.onend=()=>{
setGlow(0,255,200);
state="idle";
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

transcript="";
state="listening";
setGlow(255,210,80);

recognition.onresult=function(event){

clearTimeout(silenceTimer);
clearTimeout(noSpeechTimer);

for(let i=event.resultIndex;i<event.results.length;i++){
if(event.results[i].isFinal){
transcript+=event.results[i][0].transcript+" ";
}
}

silenceTimer=setTimeout(()=>{
recognition.stop();
processTranscript(transcript.trim());
},2500);

};

recognition.start();

noSpeechTimer=setTimeout(()=>{
if(transcript.trim().length<5){
recognition.stop();
speak("I didn’t hear anything. Could you describe your hair concern?");
}
},3500);

}

// ==========================
// PROCESS
// ==========================

function processTranscript(text){

if(!text || text.length<8){
speak("I didn’t catch that clearly. Could you be more specific with your hair concern?");
return;
}

responseBox.innerText="Analyzing...";

setTimeout(()=>{

let result=chooseProduct(text);

if(!result){
speak("I didn’t detect a clear hair concern. Could you describe dryness, oiliness, damage, tangling, color loss, volume issues, or shedding?");
return;
}

responseBox.innerText=result;
speak(result);

},1200);
}

// ==========================
// CLICK
// ==========================

halo.addEventListener("click",()=>{

if(state==="listening"){
recognition.stop();
state="idle";
setGlow(0,255,200);
return;
}

if(state==="speaking"){
speechSynthesis.cancel();
state="idle";
setGlow(0,255,200);
return;
}

startListening();

});

</script>
</body>
</html>
"""

if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
