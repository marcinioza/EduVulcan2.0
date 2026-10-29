
import getpass

from app import app
from models import db, User


def create_admin():
    with app.app_context():
        existing = User.query.filter_by(username="admin").first()

        if existing:
            print("Konto admin juz istnieje.")
            return

        password = getpass.getpass("Podaj haslo administratora: ")
        confirm = getpass.getpass("Powtorz haslo: ")

        if len(password) < 12:
            print("Haslo musi miec minimum 12 znakow.")
            return

        if password != confirm:
            print("Hasla nie sa identyczne.")
            return

        admin = User(
            username="admin",
            role="admin"
        )

        admin.set_password(password)

        db.session.add(admin)
        db.session.commit()

        print("Konto administratora zostalo utworzone!")


if __name__ == "__main__":
    create_admin()
