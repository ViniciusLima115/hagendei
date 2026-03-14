from app.config import _normalize_database_url


def test_normalize_database_url_converte_postgres_para_psycopg2_e_ssl():
    url = "postgres://user:secret@ep-cool-darkness-123456.us-east-1.aws.neon.tech/neondb"

    normalized = _normalize_database_url(url)

    assert normalized.startswith("postgresql+psycopg2://")
    assert "sslmode=require" in normalized


def test_normalize_database_url_preserva_local_sem_ssl():
    url = "postgresql://postgres:postgres@localhost:5432/barbearia"

    normalized = _normalize_database_url(url)

    assert normalized == "postgresql+psycopg2://postgres:postgres@localhost:5432/barbearia"
