from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
import os
import base64

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are an Elite Professional Salon Hair Consultant.
Only answer hair-related questions.
If unrelated, redirect politely.
"""

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

html = """
<!DOCTYPE html>
<html>
<head>
<title>Global Professional Hair Intelligence</title>

<style>
body {
    background: radial-gradient(circle at center, #0a0f1c 0%, #030712 100%);
    font-family: 'Segoe UI', sans-serif;
    text-align: center;
    color: white;
    margin-top: 80px;
}

h1 {
    font-size: 38px;
    font-weight: 500;
}

select {
    margin-top: 30px;
    padding: 10px 20px;
    font-size: 15px;
    background: rgba(30,41,59,0.6);
    color: white;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px;
}

/* ===== TRUE SEAMLESS HALO ===== */

.halo-container {
    position: relative;
    width: 240px;
    height: 240px;
    margin: 80px auto;
    cursor: pointer;
}

.halo-core {
    position: absolute;
    width: 100%;
    height: 100%;
    border-radius: 50%;
    background: radial-gradient(circle at center,
        rgba(59,130,246,0.25) 0%,
        rgba(59,130,246,0.15) 40%,
        transparent 70%);
    animation: pulse 3s infinite ease-in-out;
}

.halo-energy {
    position: absolute;
    width: 100%;
    height: 100%;
    border-radius: 50%;
    background: radial-gradient(circle,
        rgba(59,130,246,0.5) 0%,
        rgba(59,130,246,0.2) 40%,
        transparent 70%);
    animation: breathe 2.5s infinite ease-in-out;
}

@keyframes breathe {
    0% { transform: scale(1); opacity: 0.5; }
    50% { transform: scale(1.2); opacity: 1; }
    100% { transform: scale(1); opacity: 0.5; }
}

@keyframes pulse {
    0% { opacity: 0.6; }
    50% { opacity: 1; }
    100% { opacity: 0.6; }
}

.listening .halo-energy {
    background: radial-gradient(circle,
        rgba(239,68,68,0.6) 0%,
        rgba(239,68,68,0.2) 40%,
        transparent 70%);
}

.thinking .halo-core {
    animation: spin 1.2s linear infinite;
}

@keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}

.status {
    margin-top: 30px;
    color: #9ca3af;
}

#response {
    margin-top: 40px;
    width: 60%;
    margin-left: auto;
    margin-right: auto;
    font-size: 18px;
}
</style>
</head>

<body>

<h1>Global Professional Hair Intelligence</h1>

<select id="language">
<option>English</option>
<option>Spanish</option>
<option>French</option>
<option>Portuguese</option>
<option>German</option>
<option>Arabic</option>
<option>Hindi</option>
<option>Mandarin Chinese</option>
<option>Japanese</option>
<option>Korean</option>
<option>Russian</option>
</select>

<div id="halo" class="halo-container" onclick="startListening()">
    <div class="halo-core"></div>
    <div class="halo-energy"></div>
</div>

<div class="status" id="status">Click the halo to speak</div>
<div id="response"></div>
<audio id="ttsAudio"></audio>

<script>

let recognition;
let ws;

function getWebSocketURL() {
    let protocol = window.location.protocol === "https:" ? "wss://" : "ws://";
    return protocol + window.location.host + "/ws";
}

function startListening() {

    if (!('webkitSpeechRecognition' in window)) {
        alert("Use Google Chrome.");
        return;
    }

    const halo = document.getElementById("halo");
    halo.classList.add("listening");

    recognition = new webkitSpeechRecognition();
    recognition.lang = "en-US";
    recognition.continuous = false;
    recognition.interimResults = false;

    document.getElementById("status").innerText = "Listening...";
    recognition.start();

    recognition.onresult = function(event) {
    console.log("RESULT FIRED");
    const transcript = event.results[0][0].transcript;
    console.log("Transcript:", transcript);
    sendToAI(transcript);
};

    recognition.onend = function() {
        halo.classList.remove("listening");
    };

    // Safety fallback (forces stop after 8 sec)
    setTimeout(() => {
        if (recognition) recognition.stop();
    }, 8000);
}

function sendToAI(text) {

    const halo = document.getElementById("halo");
    halo.classList.add("thinking");
    document.getElementById("status").innerText = "Thinking...";
    document.getElementById("response").innerHTML = "";

    ws = new WebSocket(getWebSocketURL());

    ws.onopen = function() {
        let language = document.getElementById("language").value;
        ws.send(JSON.stringify({question: text, language: language}));
    };

    ws.onmessage = function(event) {
        if(event.data.startsWith("AUDIO:")) {
            let audioData = event.data.replace("AUDIO:", "");
            let audio = document.getElementById("ttsAudio");
            audio.src = "data:audio/mp3;base64," + audioData;
            audio.play();
        } else {
            document.getElementById("response").innerHTML += event.data;
        }
    };

    ws.onclose = function() {
        halo.classList.remove("thinking");
        document.getElementById("status").innerText = "Click the halo to speak";
    };
}

</script>

</body>
</html>
"""

@app.get("/")
async def home():
    return HTMLResponse(html)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    data = await websocket.receive_json()

    final_prompt = SYSTEM_PROMPT + f"\nRespond in {data['language']}."

    full_text = ""

    response = client.chat.completions.create(
        model="gpt-4o",
        stream=True,
        messages=[
            {"role": "system", "content": final_prompt},
            {"role": "user", "content": data["question"]}
        ]
    )

    for chunk in response:
        if chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            full_text += content
            await websocket.send_text(content)

    speech = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=full_text
    )

    audio_bytes = speech.read()
    encoded = base64.b64encode(audio_bytes).decode("utf-8")
    await websocket.send_text("AUDIO:" + encoded)

