
import os
from urllib.parse import quote_plus


class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    @staticmethod
    def database_url():
        existing_url = os.getenv("DATABASE_URL")

        if existing_url:
            return existing_url

        user = os.getenv("MYSQL_USER", "eduvulcan")
        password = os.environ["MYSQL_PASSWORD"]
        host = os.getenv("MYSQL_HOST", "db")
        port = os.getenv("MYSQL_PORT", "3306")
        database = os.getenv("MYSQL_DATABASE", "eduvulcan")

        return (
            f"mysql+pymysql://{quote_plus(user)}:"
            f"{quote_plus(password)}@{host}:{port}/{database}"
        )
