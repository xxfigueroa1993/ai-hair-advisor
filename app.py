import os
from flask import Flask, request, jsonify, session, render_template
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")


# -----------------------------
# ROOT ROUTE (SAFE)
# -----------------------------

@app.route("/")
def home():
    return """
    <html>
        <head><title>Bright Clinical AI</title></head>
        <body style="background:black;color:white;text-align:center;margin-top:100px;font-family:sans-serif;">
            <h1>Bright Clinical AI Running</h1>
            <p>Server is active.</p>
        </body>
    </html>
    """


# -----------------------------
# PROCESS ROUTE
# -----------------------------

@app.route("/process", methods=["POST"])
def process_voice():

    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        if not client.api_key:
            return jsonify({"error": "Missing OPENAI_API_KEY"}), 500

        audio_file = request.files.get("audio")
        if not audio_file:
            return jsonify({"error": "No audio uploaded"}), 400

        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )

        user_text = transcript.text.strip()

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional salon specialist."},
                {"role": "user", "content": user_text}
            ]
        )

        reply_text = completion.choices[0].message.content

        speech = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=reply_text
        )

        audio_output = speech.read()

        return jsonify({
            "transcript": user_text,
            "reply": reply_text,
            "audio": audio_output.hex()
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -----------------------------
# RENDER PORT BIND
# -----------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
