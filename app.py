from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
import os

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are an Elite Professional Salon Hair Consultant.
Only answer hair-related questions.
If asked anything outside hair, respond:
"I am a Professional Salon Hair Consultant. How may I assist you with your hair needs today?"
"""

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= FRONTEND =================

html = """
<!DOCTYPE html>
<html>
<head>
<title>Global Professional Hair Intelligence</title>

<style>
body {
    background: #0b1220;
    font-family: 'Segoe UI', sans-serif;
    text-align: center;
    color: white;
    margin-top: 80px;
}

h1 {
    font-size: 34px;
    font-weight: 500;
    letter-spacing: 1px;
}

select {
    margin-top: 30px;
    padding: 10px 20px;
    font-size: 15px;
    background: #1f2937;
    color: white;
    border: 1px solid #374151;
    border-radius: 6px;
}

.halo-ring {
    width: 180px;
    height: 180px;
    border-radius: 50%;
    border: 6px solid #3b82f6;
    background: transparent;
    box-shadow: 0 0 30px #3b82f6;
    animation: pulse 2s infinite;
    cursor: pointer;
    margin: 60px auto;
}

@keyframes pulse {
    0% { box-shadow: 0 0 15px #3b82f6; }
    50% { box-shadow: 0 0 60px #60a5fa; }
    100% { box-shadow: 0 0 15px #3b82f6; }
}

#response {
    margin-top: 40px;
    width: 60%;
    margin-left: auto;
    margin-right: auto;
    font-size: 18px;
    line-height: 1.6;
}

.status {
    margin-top: 15px;
    font-size: 14px;
    color: #9ca3af;
}
</style>
</head>

<body>

<h1>Global Professional Hair Intelligence</h1>

<select id="language">
<option value="English">English</option>
<option value="Spanish">Spanish</option>
<option value="French">French</option>
<option value="Portuguese">Portuguese</option>
<option value="German">German</option>
<option value="Italian">Italian</option>
<option value="Arabic">Arabic</option>
<option value="Hindi">Hindi</option>
<option value="Mandarin Chinese">Mandarin Chinese</option>
<option value="Japanese">Japanese</option>
<option value="Korean">Korean</option>
<option value="Russian">Russian</option>
</select>

<div class="halo-ring" onclick="startListening()"></div>

<div class="status" id="status">Click the halo to speak</div>

<div id="response"></div>

<script>
let recognition;
let ws;

function startListening() {

    if (!('webkitSpeechRecognition' in window)) {
        alert("Speech Recognition not supported in this browser. Use Chrome.");
        return;
    }

    recognition = new webkitSpeechRecognition();
    recognition.lang = "en-US";
    recognition.start();

    document.getElementById("status").innerText = "Listening...";

    recognition.onresult = function(event) {
        let transcript = event.results[0][0].transcript;
        document.getElementById("status").innerText = "Processing...";

        connectWebSocket(transcript);
    };

    recognition.onerror = function() {
        document.getElementById("status").innerText = "Speech recognition error.";
    };
}

function connectWebSocket(question) {

    document.getElementById("response").innerHTML = "";
    ws = new WebSocket("wss://" + location.host + "/ws");

    ws.onmessage = function(event) {
        document.getElementById("response").innerHTML += event.data;
    };

    ws.onopen = function() {
        let language = document.getElementById("language").value;

        ws.send(JSON.stringify({
            question: question,
            language: language
        }));

        document.getElementById("status").innerText = "Responding...";
    };

    ws.onclose = function() {
        document.getElementById("status").innerText = "Click the halo to speak again";
    };
}
</script>

</body>
</html>
"""

@app.get("/")
async def home():
    return HTMLResponse(html)

# ================= BACKEND =================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    data = await websocket.receive_json()

    user_question = data["question"]
    language = data["language"]

    final_prompt = SYSTEM_PROMPT + f"\nRespond in {language}."

    response = client.chat.completions.create(
        model="gpt-4o",
        stream=True,
        messages=[
            {"role": "system", "content": final_prompt},
            {"role": "user", "content": user_question}
        ]
    )

    for chunk in response:
        if chunk.choices[0].delta.content:
            await websocket.send_text(chunk.choices[0].delta.content)
