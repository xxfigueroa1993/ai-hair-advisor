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
        <p>Render port binding successful.</p>
    </body>
    </html>
    """

# IMPORTANT:
# REMOVE app.run() COMPLETELY.
# Gunicorn handles server startup.
