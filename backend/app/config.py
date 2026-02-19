import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://chatbot:chatbot@localhost:3306/chatbot",
)

HORARIO_ABERTURA = int(os.getenv("HORARIO_ABERTURA", "8"))
HORARIO_FECHAMENTO = int(os.getenv("HORARIO_FECHAMENTO", "19"))
INTERVALO_MINUTOS = int(os.getenv("INTERVALO_MINUTOS", "40"))
