
from flask import Flask

app = Flask(__name__)


@app.route("/")
def home():
    return """
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>EduVulcan2.0</title>
    </head>
    <body>
        <h1>EduVulcan2.0</h1>
        <h2>Elektroniczny dziennik ocen</h2>
        <p>Serwer Flask działa poprawnie!</p>
    </body>
    </html>
    """


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
