import os
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>AI Hair Orb</title>
<style>
body{
    margin:0;
    background:#000;
    display:flex;
    justify-content:center;
    align-items:center;
    height:100vh;
    overflow:hidden;
}

.orb{
    width:220px;
    height:220px;
    border-radius:50%;
    background: radial-gradient(circle at center,
        rgba(255,215,0,0.18) 0%,
        rgba(255,215,0,0.08) 40%,
        rgba(0,0,0,0.9) 70%);
    box-shadow:
        0 0 60px rgba(255,215,0,0.25),
        0 0 120px rgba(255,215,0,0.15);
    animation: idlePulse 3s infinite ease-in-out;
    transition: all 0.3s ease;
    cursor:pointer;
}

@keyframes idlePulse{
    0%{transform:scale(1);}
    50%{transform:scale(1.05);}
    100%{transform:scale(1);}
}

.listening{ animation:listeningPulse .8s infinite ease-in-out; }
@keyframes listeningPulse{
    0%{transform:scale(1);}
    50%{transform:scale(1.12);}
    100%{transform:scale(1);}
}

.speaking{ animation:speakingPulse 1s infinite ease-in-out; }
@keyframes speakingPulse{
    0%{transform:scale(1);}
    50%{transform:scale(1.15);}
    100%{transform:scale(1);}
}
</style>
</head>
<body>

<div class="orb" id="orb"></div>

<script>

const orb = document.getElementById("orb")

let recognition = null
let silenceTimer = null
let analyzingTimer = null
let transcriptFinal = ""
let isListening = false
let isSpeaking = false

function fullReset(){
    if(recognition){
        recognition.onresult = null
        recognition.stop()
        recognition = null
    }

    speechSynthesis.cancel()

    clearTimeout(silenceTimer)
    clearTimeout(analyzingTimer)

    transcriptFinal = ""
    isListening = false
    isSpeaking = false

    orb.classList.remove("listening")
    orb.classList.remove("speaking")
}

function startListening(){

    recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)()
    recognition.continuous = true
    recognition.interimResults = true
    recognition.lang = "en-US"

    recognition.onresult = (event)=>{
        clearTimeout(silenceTimer)

        transcriptFinal = Array.from(event.results)
            .map(r => r[0].transcript)
            .join("")

        silenceTimer = setTimeout(()=>{
            recognition.stop()
            recognition = null
            startAnalyzing(transcriptFinal)
        },2500)  // 2.5 second silence detection
    }

    recognition.start()
    isListening = true
    orb.classList.add("listening")
}

function startAnalyzing(text){
    orb.classList.remove("listening")

    analyzingTimer = setTimeout(()=>{
        fetch("/ask",{
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({message:text})
        })
        .then(res=>res.json())
        .then(data=>speakResponse(data.reply))
    },3000)  // 3 second analyzing delay
}

function speakResponse(text){

    const utter = new SpeechSynthesisUtterance(text)

    utter.pitch = 1.2
    utter.rate = 1
    utter.volume = 1

    utter.onstart = ()=>{
        isSpeaking = true
        orb.classList.add("speaking")
    }

    utter.onend = ()=>{
        isSpeaking = false
        orb.classList.remove("speaking")
    }

    speechSynthesis.speak(utter)
}

orb.addEventListener("click", ()=>{
    if(isListening || isSpeaking){
        fullReset()
        return
    }
    startListening()
})

</script>

</body>
</html>
"""

@app.route("/")
def home():
    return HTML_PAGE


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    user_message = data.get("message","")

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role":"system","content":"You are a confident, bright-toned professional salon hair expert."},
                {"role":"user","content":user_message}
            ]
        )
        return jsonify({"reply":response.choices[0].message.content})
    except Exception:
        return jsonify({"reply":"I'm experiencing a temporary connection issue. Please try again."})


if __name__ == "__main__":
    port = int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0", port=port)
