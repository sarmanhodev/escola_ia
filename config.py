import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")

    if not SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY não configurada. " "Defina a variável no arquivo .env."
        )

    SQLALCHEMY_DATABASE_URI = "sqlite:///" + str(BASE_DIR / "escola.db").replace(
        "\\", "/"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
