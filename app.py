import os
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<title>Force Bluetooth Mic</title>
</head>
<body style="background:black;color:white;text-align:center;margin-top:80px;font-family:Arial;">

<h1>Bluetooth Mic Test</h1>
<button onclick="start()">Start Listening</button>

<p id="status">Idle</p>
<p id="volume">Volume: 0</p>

<script>
async function start(){

    const status = document.getElementById("status");
    const volumeDisplay = document.getElementById("volume");

    try{

        await navigator.mediaDevices.getUserMedia({audio:true});
        const devices = await navigator.mediaDevices.enumerateDevices();

        const headset = devices.find(d =>
            d.kind === "audioinput" &&
            d.label.includes("onn Neckband Pro")
        );

        if(!headset){
            status.innerText = "Bluetooth mic not found";
            return;
        }

        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                deviceId: { exact: headset.deviceId },
                echoCancellation: false,
                noiseSuppression: false,
                autoGainControl: false
            }
        });

        const audioContext = new AudioContext();
        const source = audioContext.createMediaStreamSource(stream);
        const analyser = audioContext.createAnalyser();

        analyser.fftSize = 2048;
        source.connect(analyser);

        const data = new Uint8Array(analyser.fftSize);

        status.innerText = "Listening using Bluetooth mic... Speak now";

        function detect(){
            analyser.getByteTimeDomainData(data);

            let sum = 0;
            for(let i=0;i<data.length;i++){
                let val = (data[i] - 128) / 128;
                sum += val * val;
            }

            let volume = Math.sqrt(sum / data.length);
            volumeDisplay.innerText = "Volume: " + volume.toFixed(6);

            requestAnimationFrame(detect);
        }

        detect();

    } catch(err){
        status.innerText = "Error: " + err.message;
    }
}
</script>

</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
