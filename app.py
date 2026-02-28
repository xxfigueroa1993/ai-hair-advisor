import os
import tempfile
from flask import Flask, request, jsonify, send_file
from openai import OpenAI

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

<h1>AI Hair Advisor (Voice Enabled)</h1>
<button onclick="startRecording()">Start / Stop Recording</button>

<p id="status">Idle</p>

<audio id="audioPlayer" autoplay></audio>

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
                autoGainControl: true,
                channelCount: 1
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

            await new Promise(resolve => setTimeout(resolve, 1000));

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

            if (data.audio_url){
                const player = document.getElementById("audioPlayer");
                player.src = data.audio_url + "?t=" + new Date().getTime();
                player.play();
            }
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
        print("No audio received", flush=True)
        return jsonify({"text": "No audio received"})

    file = request.files["audio"]
    print("Audio file received", flush=True)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
        file.save(temp_audio.name)
        temp_audio_path = temp_audio.name

    print("Saved temp file:", temp_audio_path, flush=True)

    try:
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

Be short and clear. Only recommend from this list.
"""
                },
                {
                    "role": "user",
                    "content": user_text
                }
            ]
        )

        response_text = completion.choices[0].message.content.strip()

        print("GPT response:", response_text, flush=True)

        print("Generating voice response...", flush=True)

        speech_file_path = os.path.join(tempfile.gettempdir(), "response.mp3")

        with client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=response_text
        ) as response:
            response.stream_to_file(speech_file_path)

        print("Voice file saved:", speech_file_path, flush=True)

        return jsonify({
            "text": response_text,
            "audio_url": "/audio"
        })

    except Exception as e:
        print("FULL ERROR:", str(e), flush=True)
        return jsonify({"text": "Server error: " + str(e)})


@app.route("/audio")
def serve_audio():
    speech_file_path = os.path.join(tempfile.gettempdir(), "response.mp3")
    return send_file(speech_file_path, mimetype="audio/mpeg")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
