import os
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ============================================================
# PRODUCT SYSTEM (Layered – Does NOT interfere with orb)
# ============================================================

PRODUCTS = {
    "Formula Exclusiva": "An advanced all-in-one natural professional salon treatment designed to rebuild internal structure, repair damage, and restore elasticity and brilliance.",
    "Laciador": "A precision natural smoothing styler that deeply hydrates, eliminates dryness, and enhances manageability without weight.",
    "Gotero": "A lightweight natural gel system engineered for oil balance, bounce restoration, and controlled structure.",
    "Gotika": "A botanical-based color revitalizing treatment that restores vibrancy, shine, and reflective luminosity."
}

def choose_product(issue: str, age: int):
    issue = issue.lower()

    if age < 16 and "color" in issue:
        return "MEDICAL"

    if "dry" in issue:
        return "Laciador"
    if "oily" in issue:
        return "Gotero"
    if "damaged" in issue:
        return "Formula Exclusiva"
    if "tangly" in issue:
        return "Formula Exclusiva"
    if "fall" in issue:
        return "Formula Exclusiva"
    if "not bouncy" in issue:
        return "Gotero"
    if "color" in issue:
        return "Gotika"

    return "Formula Exclusiva"  # guaranteed fallback


# ============================================================
# HTML (ORIGINAL STABLE ORB ARCHITECTURE RESTORED)
# ============================================================

HTML = """
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
    flex-direction:column;
    justify-content:center;
    align-items:center;
    height:100vh;
    overflow:hidden;
    font-family:Arial;
    color:white;
}

select{
    margin-bottom:25px;
    padding:10px;
    background:black;
    color:gold;
    border:1px solid gold;
}

/* ===== ORB BASE (YOUR PERFECT TRANSPARENCY) ===== */
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
    transition: all 0.2s ease;
    cursor:pointer;
}

/* Deep idle pulse */
@keyframes idlePulse{
    0%{transform:scale(1);}
    50%{transform:scale(1.05);}
    100%{transform:scale(1);}
}

/* Listening pulse */
.listening{
    animation:listeningPulse .8s infinite ease-in-out;
}
@keyframes listeningPulse{
    0%{transform:scale(1);}
    50%{transform:scale(1.12);}
    100%{transform:scale(1);}
}

/* Speaking pulse */
.speaking{
    animation:speakingPulse 1s infinite ease-in-out;
}
@keyframes speakingPulse{
    0%{transform:scale(1);}
    50%{transform:scale(1.15);}
    100%{transform:scale(1);}
}
</style>
</head>
<body>

<select id="continent">
<option>Asia</option>
<option>Africa</option>
<option>North America</option>
<option>South America</option>
<option>Europe</option>
<option>Australia</option>
<option>Antarctica</option>
</select>

<div class="orb" id="orb"></div>

<audio id="clickSound" src="/static/click.mp3"></audio>
<audio id="completeSound" src="/static/complete.mp3"></audio>

<script>

const orb = document.getElementById("orb")
const clickSound = document.getElementById("clickSound")
const completeSound = document.getElementById("completeSound")

let recognition=null
let silenceTimer=null
let analyzeTimer=null
let transcript=""
let listening=false
let speaking=false

// ===== HARD RESET =====
function resetAll(){
    if(recognition){
        recognition.stop()
        recognition=null
    }
    speechSynthesis.cancel()
    clearTimeout(silenceTimer)
    clearTimeout(analyzeTimer)
    transcript=""
    listening=false
    speaking=false
    orb.classList.remove("listening","speaking")
}

// ===== START LISTENING =====
function startListening(){
    recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)()
    recognition.continuous=true
    recognition.interimResults=true

    recognition.onresult=(e)=>{
        clearTimeout(silenceTimer)

        transcript = Array.from(e.results)
            .map(r=>r[0].transcript)
            .join("")

        silenceTimer=setTimeout(()=>{
            recognition.stop()
            analyze(transcript)
        },2500)   // 2.5 second silence
    }

    recognition.start()
    listening=true
    orb.classList.add("listening")
}

// ===== ANALYZE DELAY =====
function analyze(text){
    orb.classList.remove("listening")

    analyzeTimer=setTimeout(()=>{
        fetch("/ask",{
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({message:text})
        })
        .then(res=>res.json())
        .then(data=>speak(data.reply))
    },3000)   // 3 second delay
}

// ===== SPEAK =====
function speak(text){
    const utter=new SpeechSynthesisUtterance(text)
    utter.pitch=1.2
    utter.rate=1

    utter.onstart=()=>{
        speaking=true
        orb.classList.add("speaking")
    }

    utter.onend=()=>{
        speaking=false
        orb.classList.remove("speaking")
        completeSound.currentTime=0
        completeSound.play()
    }

    speechSynthesis.speak(utter)
}

// ===== CLICK HANDLER =====
orb.addEventListener("click",()=>{
    if(listening || speaking){
        resetAll()
        return
    }

    clickSound.currentTime=0
    clickSound.play()
    startListening()
})

</script>
</body>
</html>
"""

# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def home():
    return HTML

@app.route("/ask", methods=["POST"])
def ask():
    data=request.get_json()
    message=data.get("message","")
    age=30

    product=choose_product(message,age)

    if product=="MEDICAL":
        return jsonify({"reply":"For clients under 16 experiencing pigment loss, we recommend consulting a licensed medical professional before cosmetic treatment."})

    ai = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":"You are a confident, bright-toned professional salon hair expert."},
            {"role":"user","content":f"Client concern: {message}. Recommend {product} and explain why in a high-end salon FAQ tone."}
        ]
    )

    return jsonify({"reply":ai.choices[0].message.content})

# ============================================================

if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
