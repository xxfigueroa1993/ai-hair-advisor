import os
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Bright Clinical AI</title>
        <style>
            body {
                background: black;
                color: white;
                font-family: Arial;
                text-align: center;
                margin-top: 120px;
            }
        </style>
    </head>
    <body>
        <h1>Bright Clinical AI is Running</h1>
        <p>If you see this, Render is working correctly.</p>
    </body>
    </html>
    """

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
