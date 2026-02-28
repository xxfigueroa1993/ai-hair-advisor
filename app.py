import os
import tempfile
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

MIN_AUDIO_SIZE = 15000
MIN_TRANSCRIPT_LENGTH = 5


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
        audioChunks.push(event.data);
    };

    mediaRecorder.onstop = async () => {

        const audioBlob = new Blob(audioChunks, { type: "audio/webm" });

        const formData = new FormData();
        formData.append("audio", audioBlob);

        document.getElementById("status").innerText = "Processing...";

        const response = await fetch("/voice", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        document.getElementById("status").innerText = data.text;

        if(data.text &&
           data.text !== "No speech detected" &&
           data.text !== "I didn’t catch that clearly. Please try again and speak a little louder."){

            // 🔥 Fix speech reliability
            window.speechSynthesis.cancel();

            const speakText = () => {
                const utterance = new SpeechSynthesisUtterance(data.text);

                const voices = speechSynthesis.getVoices();
                if (voices.length > 0) {
                    utterance.voice = voices.find(v => v.lang === "en-US") || voices[0];
                }

                utterance.rate = 1;
                utterance.pitch = 1;

                speechSynthesis.speak(utterance);
            };

            if (speechSynthesis.getVoices().length === 0) {
                speechSynthesis.onvoiceschanged = speakText;
            } else {
                speakText();
            }
        }
    };

    mediaRecorder.start();

    setTimeout(() => {
        mediaRecorder.stop();
    }, 5000);
}

</script>

</body>
</html>
"""


@app.route("/voice", methods=["POST"])
def voice():

    if "audio" not in request.files:
        return jsonify({"text": "No audio received"})

    file = request.files["audio"]

    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    print("Backend received file size:", file_size)

    if file_size < MIN_AUDIO_SIZE:
        print("Detected silence")
        return jsonify({"text": "No speech detected"})

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
        file.save(temp_audio.name)
        temp_audio_path = temp_audio.name

    try:
        with open(temp_audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )

        user_text = transcript.strip()

        print("User said:", repr(user_text))

        if not user_text or len(user_text) < MIN_TRANSCRIPT_LENGTH:
            print("Transcript too short")
            return jsonify({
                "text": "I didn’t catch that clearly. Please try again and speak a little louder."
            })

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

        print("AI response:", response_text)

        return jsonify({"text": response_text})

    except Exception as e:
        print("Error:", e)
        return jsonify({"text": "Error processing request"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
