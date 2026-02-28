import os
import tempfile
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

print("API KEY LOADED:", os.environ.get("OPENAI_API_KEY") is not None)


@app.route("/")
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<title>AI Hair Advisor</title>
</head>
<body style="background:black;color:white;text-align:center;margin-top:60px;font-family:Arial;">

<h1>AI Hair Advisor (DEBUG MODE)</h1>
<button onclick="startRecording()">Click to Speak</button>

<p id="status">Idle</p>

<script>

let mediaRecorder;
let audioChunks = [];

async function startRecording(){

    document.getElementById("status").innerText = "Listening...";

    const stream = await navigator.mediaDevices.getUserMedia({audio:true});
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];

    mediaRecorder.ondataavailable = event => {
        if (event.data.size > 0) {
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

    setTimeout(() => {
        mediaRecorder.stop();
    }, 6000);
}

</script>

</body>
</html>
"""


@app.route("/voice", methods=["POST"])
def voice():

    print("\n===== VOICE ROUTE HIT =====")

    if "audio" not in request.files:
        print("No audio file in request")
        return jsonify({"text": "No audio received"})

    file = request.files["audio"]
    print("Audio file received")

    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    print("File size:", file_size)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
        file.save(temp_audio.name)
        temp_audio_path = temp_audio.name

    print("Saved temp file at:", temp_audio_path)

    try:
        print("Starting Whisper transcription...")

        with open(temp_audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )

        print("Raw transcript:", transcript)

        user_text = transcript.strip()
        print("Clean transcript:", user_text)

        if not user_text:
            print("Transcript empty")
            return jsonify({"text": "Empty transcript"})

        print("Calling GPT...")

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional hair product advisor."},
                {"role": "user", "content": user_text}
            ]
        )

        response_text = completion.choices[0].message.content.strip()
        print("GPT response:", response_text)

        return jsonify({"text": response_text})

    except Exception as e:
        print("FULL ERROR:", str(e))
        return jsonify({"text": "Server error: " + str(e)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
