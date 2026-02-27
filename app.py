import os
from flask import Flask, request

app = Flask(__name__)

@app.route("/")
def home():
    return """
    <h1>Bright Clinical AI</h1>
    <button onclick="record()">Record 5 Seconds</button>
    <p id="status">Idle</p>

    <script>
    async function record(){

        const status = document.getElementById("status");

        if(!navigator.mediaDevices){
            status.innerText = "Mic API not supported";
            return;
        }

        try{
            const stream = await navigator.mediaDevices.getUserMedia({audio:true});
            const recorder = new MediaRecorder(stream);
            let chunks = [];

            recorder.ondataavailable = e => {
                if(e.data.size > 0){
                    chunks.push(e.data);
                }
            };

            recorder.onstop = async () => {

                const blob = new Blob(chunks, { type:"audio/webm" });
                status.innerText = "Sending... Size: " + blob.size;

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
            status.innerText = "Recording...";

            setTimeout(()=>{
                recorder.stop();
            }, 5000);

        } catch(err){
            status.innerText = "Mic blocked: " + err.message;
        }
    }
    </script>
    """

@app.route("/voice", methods=["POST"])
def voice():

    if "audio" not in request.files:
        return "No file received"

    audio_file = request.files["audio"]
    path = "/tmp/test.webm"
    audio_file.save(path)

    size = os.path.getsize(path)
    print("Received file size:", size)

    return f"Backend received file size: {size} bytes"

port = int(os.environ.get("PORT", 10000))
app.run(host="0.0.0.0", port=port)
