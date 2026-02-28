import os
import tempfile
import base64
from flask import Flask, request, jsonify
from openai import OpenAI

# Ensure logs flush immediately (important for Render)
os.environ["PYTHONUNBUFFERED"] = "1"

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

print("API KEY LOADED:", os.environ.get("OPENAI_API_KEY") is not None, flush=True)


@app.route("/")
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<title>AI Hair Advisor</title>
</head>
<body style="background:black;color:white;text-align:center;margin-top:60px;font-family:Arial;">

<h1>AI Hair Advisor</h1>
<button onclick="startRecording()">Start / Stop Recording</button>

<p id="status">Idle</p>
<audio id="audioPlayer" controls autoplay></audio>

<script>

let mediaRecorder;
let audioChunks = [];
let recording = false;

async function startRecording(){

    if (!recording){

        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                echoCancellation: false,
                noiseSuppression: false,
                autoGainControl: true
            }
        });

        mediaRecorder = new MediaRecorder(stream, {
            mimeType: "audio/webm;codecs=opus",
            audioBitsPerSecond: 128000
        });

        audioChunks = [];

        mediaRecorder.ondataavailable = event => {
            if (event.data.size > 0){
                audioChunks.push(event.data);
            }
        };

        mediaRecorder.onstop = async () => {

            await new Promise(resolve => setTimeout(resolve, 500));

            const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
            const formData = new FormData();
            formData.append("audio", audioBlob, "audio.webm");

            document.getElementById("status").innerText = "Processing...";

            const response = await fetch("/voice", {
                method: "POST",
                body: formData
            });

            const data = await response.json();

            document.getElementById("status").innerText = data.text;

            if (data.audio){
                const player = document.getElementById("audioPlayer");
                player.src = "data:audio/mp3;base64," + data.audio;
                player.play();
            }
        };

        mediaRecorder.start();
        recording = true;
        document.getElementById("status").innerText = "Recording... Click again to stop.";

    } else {
        mediaRecorder.stop();
        recording = false;
    }
}

</script>
</body>
</html>
"""


@app.route("/voice", methods=["POST"])
def voice():

    print("\n===== VOICE ROUTE HIT =====", flush=True)

    if "audio" not in request.files:
        print("No audio received", flush=True)
        return jsonify({"text": "No audio received"})

    file = request.files["audio"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
        file.save(temp_audio.name)
        temp_audio_path = temp_audio.name

    try:
        # -------- TRANSCRIPTION --------
        print("Starting transcription...", flush=True)

        with open(temp_audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )

        user_text = transcript.strip()
        print("Transcript:", user_text, flush=True)

        if not user_text:
            return jsonify({"text": "I didn’t catch that clearly. Please try again."})

        # -------- GPT RESPONSE --------
        print("Calling GPT...", flush=True)

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """
You are a professional hair product advisor.

ONLY recommend products from this catalog:

1. Hydrate Restore Shampoo – For dry hair
2. Deep Repair Mask – For damaged hair
3. Curl Define Cream – For curly hair
4. Scalp Balance Serum – For oily scalp
5. Shine Boost Conditioner – For dull hair

Be short, confident, and clear.
"""
                },
                {
                    "role": "user",
                    "content": user_text
                }
            ]
        )

        response_text = completion.choices[0].message.content.strip()
        print("GPT Response:", response_text, flush=True)

        # -------- TEXT TO SPEECH --------
        print("Generating voice...", flush=True)

        speech = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=response_text
        )

        audio_bytes = speech.read()
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        print("Voice generated successfully", flush=True)

        return jsonify({
            "text": response_text,
            "audio": audio_base64
        })

    except Exception as e:
        print("ERROR:", str(e), flush=True)
        return jsonify({"text": "Server error: " + str(e)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
