
from flask import Flask, render_template

from config import Config
from models import db, Student, Subject, Grade

app = Flask(__name__)

# Konfiguracja polaczenia z MySQL
app.config["SQLALCHEMY_DATABASE_URI"] = Config.database_url()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Polaczenie SQLAlchemy z aplikacja Flask
db.init_app(app)


@app.route("/")
def home():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
