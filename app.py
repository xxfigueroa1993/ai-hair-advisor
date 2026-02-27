import os
import json
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are Bright Clinical AI, a professional hair product advisor.

STRICT RULES:
- Ignore greetings.
- Extract the core hair concern.
- ALWAYS select EXACTLY ONE product from:
  Formula Exclusiva
  Laciador
  Gotero
  Gotika
- Never leave product empty.
- If unclear, select closest product and ask clarifying question.
- Keep response concise and confident.
- End by confirming the recommendation.

Return ONLY valid JSON:

{
  "product": "Product Name",
  "response": "Professional spoken recommendation ending with confirmation question."
}
"""

@app.route("/")
def index():
    return "Bright Clinical AI is running."

@app.route("/voice", methods=["POST"])
def voice():
    try:
        print("VOICE ROUTE HIT")

        if "audio" not in request.files:
            print("NO AUDIO FILE")
            return jsonify({
                "product": None,
                "response": "No audio received."
            })

        audio_file = request.files["audio"]
        print("AUDIO RECEIVED")

        # Save file temporarily (Render allows /tmp)
        audio_path = "/tmp/input.webm"
        audio_file.save(audio_path)
        print("FILE SAVED TO /tmp")

        # Transcribe with Whisper
        with open(audio_path, "rb") as f:
            transcript_response = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )

        transcript = transcript_response.text.strip()
        print("TRANSCRIPT:", transcript)

        # If silence or empty transcript
        if len(transcript) < 3:
            print("TRANSCRIPT TOO SHORT")
            return jsonify({
                "product": None,
                "response": "I didn’t hear anything clearly. Please try again."
            })

        # Get GPT structured JSON response
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": transcript}
            ],
            temperature=0.2
        )

        print("GPT RESPONSE RECEIVED")

        parsed = json.loads(completion.choices[0].message.content)

        valid_products = [
            "Formula Exclusiva",
            "Laciador",
            "Gotero",
            "Gotika"
        ]

        if parsed.get("product") not in valid_products:
            print("INVALID PRODUCT RETURNED - DEFAULTING")
            parsed["product"] = "Formula Exclusiva"
            parsed["response"] = (
                "Formula Exclusiva is recommended for your concern. "
                "Does that align with your goal?"
            )

        return jsonify(parsed)

    except Exception as e:
        print("🔥 FULL ERROR:", str(e))
        return jsonify({
            "product": None,
            "response": "Server error occurred. Please try again."
        })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
