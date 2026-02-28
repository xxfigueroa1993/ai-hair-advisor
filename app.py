import os
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
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
width:380px;
height:380px;
display:flex;
justify-content:center;
align-items:center;
}

#halo{
width:280px;
height:280px;
border-radius:50%;
cursor:pointer;
transition:transform 0.05s linear;
}

#response{
margin-top:30px;
width:75%;
text-align:center;
font-size:18px;
}

#langBox{
position:absolute;
top:18px;
right:22px;
}

#langSelect{
background:rgba(0,0,0,0.7);
color:white;
border:1px solid rgba(255,255,255,0.3);
padding:7px 10px;
border-radius:8px;
font-size:13px;
cursor:pointer;
}
</style>
</head>
<body>

<div id="langBox">
<select id="langSelect">
<option value="en-US">English</option>
<option value="es-ES">Español</option>
<option value="pt-BR">Português</option>
<option value="fr-FR">Français</option>
<option value="de-DE">Deutsch</option>
<option value="ar-SA">العربية</option>
<option value="zh-CN">中文</option>
<option value="hi-IN">हिन्दी</option>
</select>
</div>

<div class="wrapper">
<div id="halo"></div>
</div>

<div id="response">Tap and describe your hair concern.</div>

<script>

const halo=document.getElementById("halo");
const responseBox=document.getElementById("response");
const langSelect=document.getElementById("langSelect");

let selectedLang="en-US";
let premiumEnglishVoice=null;
let selectedVoice=null;

let state="idle";
let recognition=null;
let transcript="";
let silenceTimer=null;

/* ================= LOAD VOICES ================= */

function loadVoices(){
return new Promise(resolve=>{
let voices=speechSynthesis.getVoices();
if(!voices.length){
speechSynthesis.onvoiceschanged=()=>{
resolve(speechSynthesis.getVoices());
};
}else{
resolve(voices);
}
});
}

async function initVoices(){
let voices=await loadVoices();

/* Lock premium US English voice */
premiumEnglishVoice =
voices.find(v=>v.name.includes("Google US English")) ||
voices.find(v=>v.name.includes("Jenny")) ||
voices.find(v=>v.lang==="en-US");

updateVoiceSelection();
}

function updateVoiceSelection(){
let voices=speechSynthesis.getVoices();

if(selectedLang==="en-US"){
selectedVoice=premiumEnglishVoice;
return;
}

selectedVoice=
voices.find(v=>v.lang===selectedLang) ||
voices.find(v=>v.lang.startsWith(selectedLang.split("-")[0])) ||
premiumEnglishVoice;
}

/* ================= LANGUAGE CHANGE ================= */

langSelect.addEventListener("change",()=>{
selectedLang=langSelect.value;
updateVoiceSelection();
});

/* ================= SPEAK ================= */

function speak(text){
state="speaking";

let utter=new SpeechSynthesisUtterance(text);
utter.lang=selectedLang;
utter.voice=selectedVoice;
utter.rate=0.92;
utter.pitch=1.02;

speechSynthesis.cancel();
speechSynthesis.speak(utter);

utter.onend=()=>{
state="idle";
};
}

/* ================= TRANSLATION LAYER ================= */

function translate(text){

const translations={
"es-ES":{
"complete":"Formula Exclusiva es tu solución completa todo en uno. Precio: $65.",
"damage":"Formula Exclusiva fortalece y reconstruye el cabello. Precio: $65.",
"default":"Describe sequedad, grasa, daño o color."
},
"pt-BR":{
"complete":"Formula Exclusiva é sua solução completa tudo em um. Preço: $65.",
"damage":"Formula Exclusiva fortalece e reconstrói o cabelo. Preço: $65.",
"default":"Descreva ressecamento, oleosidade, danos ou cor."
}
};

if(selectedLang==="en-US") return null;

if(translations[selectedLang]){
return translations[selectedLang];
}

return null;
}

/* ================= PRODUCT LOGIC ================= */

function chooseProduct(text){

text=text.toLowerCase();

let translation=translate(text);

if(/all.?in.?one|complete|everything/.test(text)){
if(translation) return translation.complete;
return "Formula Exclusiva is your complete all-in-one restoration solution. Price: $65.";
}

if(/damage|weak|break/.test(text)){
if(translation) return translation.damage;
return "Formula Exclusiva strengthens and rebuilds hair integrity. Price: $65.";
}

if(translation) return translation.default;

return "Please describe dryness, oiliness, damage, or color concerns.";
}

/* ================= LISTEN ================= */

function startListening(){

const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
recognition=new SpeechRecognition();
recognition.lang=selectedLang;
recognition.continuous=true;
recognition.interimResults=false;

recognition.onresult=function(event){

transcript=event.results[0][0].transcript;
recognition.stop();
processTranscript(transcript);
};

recognition.start();
}

/* ================= PROCESS ================= */

function processTranscript(text){
let result=chooseProduct(text);
responseBox.innerText=result;
speak(result);
}

/* ================= CLICK ================= */

halo.addEventListener("click",()=>{
if(state==="idle"){
startListening();
}else{
speechSynthesis.cancel();
if(recognition) recognition.stop();
state="idle";
}
});

/* INIT */
initVoices();

</script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
