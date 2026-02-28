import os
import tempfile
from flask import Flask, request, jsonify
from openai import OpenAI

# Force unbuffered logging
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

<h1>AI Hair Advisor (CLICK TO START / STOP)</h1>
<button onclick="startRecording()">Start / Stop Recording</button>

<p id="status">Idle</p>

<script>

let mediaRecorder;
let audioChunks = [];
let recording = false;

async function startRecording(){

    if (!recording){

        const stream = await navigator.mediaDevices.getUserMedia({audio:true});
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = event => {
            if (event.data.size > 0){
                audioChunks.push(event.data);
            }
        };

        mediaRecorder.onstop = async () => {

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
        };

        mediaRecorder.start();
        recording = true;
        document.getElementById("status").innerText = "Recording... Click again to stop.";

    } else {

        mediaRecorder.stop();
        recording = false;
        document.getElementById("status").innerText = "Stopped. Processing...";
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
        print("No audio file in request", flush=True)
        return jsonify({"text": "No audio received"})

    file = request.files["audio"]
    print("Audio file received", flush=True)

    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    print("File size:", file_size, flush=True)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
        file.save(temp_audio.name)
        temp_audio_path = temp_audio.name

    print("Saved temp file at:", temp_audio_path, flush=True)

    try:
        print("Starting Whisper transcription...", flush=True)

        with open(temp_audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )

        print("Raw transcript:", transcript, flush=True)

        user_text = transcript.strip()
        print("Clean transcript:", user_text, flush=True)

        if not user_text:
            print("Transcript empty", flush=True)
            return jsonify({"text": "I didn’t catch that clearly. Please try again."})

        print("Calling GPT...", flush=True)

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional hair product advisor. Give short, clear, specific product recommendations."
                },
                {
                    "role": "user",
                    "content": user_text
                }
            ]
        )

        response_text = completion.choices[0].message.content.strip()

        print("GPT response:", response_text, flush=True)

        return jsonify({"text": response_text})

    except Exception as e:
        print("FULL ERROR:", str(e), flush=True)
        return jsonify({"text": "Server error: " + str(e)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
