import os
from flask import Flask, request

app = Flask(__name__)

# ===============================
# FRONTEND WITH REAL SPEECH DETECTION
# ===============================
@app.route("/")
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<title>Bright Clinical AI</title>
</head>
<body style="background:black;color:white;text-align:center;margin-top:100px;font-family:Arial;">

<h1>Bright Clinical AI</h1>
<button onclick="record()">Speak</button>
<p id="status">Idle</p>

<script>
async function record(){

    const status = document.getElementById("status");

    if(!navigator.mediaDevices){
        status.innerText = "Microphone not supported";
        return;
    }

    try{

        const stream = await navigator.mediaDevices.getUserMedia({audio:true});
        const audioContext = new AudioContext();
        const source = audioContext.createMediaStreamSource(stream);
        const analyser = audioContext.createAnalyser();

        source.connect(analyser);

        const data = new Uint8Array(analyser.fftSize);

        const recorder = new MediaRecorder(stream);
        let chunks = [];
        let speakingDetected = false;

        recorder.ondataavailable = e => {
            if(e.data.size > 0){
                chunks.push(e.data);
            }
        };

        recorder.onstop = async () => {

            if(!speakingDetected){
                status.innerText = "No speech detected";
                return;
            }

            const blob = new Blob(chunks, {type:"audio/webm"});

            status.innerText = "Sending to backend...";

            const formData = new FormData();
            formData.append("audio", blob, "speech.webm");

            const res = await fetch("/voice", {
                method:"POST",
                body:formData
            });

            const text = await res.text();
            status.innerText = text;
        };

        recorder.start();
        status.innerText = "Listening... Speak now";

        const detectSpeech = () => {
            analyser.getByteTimeDomainData(data);

            let sum = 0;
            for(let i=0;i<data.length;i++){
                let val = (data[i] - 128) / 128;
                sum += val * val;
            }

            let volume = Math.sqrt(sum / data.length);

            if(volume > 0.02){
                speakingDetected = true;
            }

            if(recorder.state === "recording"){
                requestAnimationFrame(detectSpeech);
            }
        };

        detectSpeech();

        setTimeout(()=>{
            recorder.stop();
        }, 5000);

    } catch(err){
        status.innerText = "Microphone blocked: " + err.message;
    }
}
</script>

</body>
</html>
"""


# ===============================
# BACKEND AUDIO RECEIVER (TEST MODE)
# ===============================
@app.route("/voice", methods=["POST"])
def voice():

    print("VOICE ROUTE HIT")

    if "audio" not in request.files:
        return "No file received"

    audio_file = request.files["audio"]
    path = "/tmp/test.webm"
    audio_file.save(path)

    size = os.path.getsize(path)
    print("Received file size:", size)

    return f"Backend received file size: {size} bytes"


# ===============================
# RUN SERVER
# ===============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
