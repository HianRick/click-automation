"""Ponto de entrada da API de Automacao."""

from src.app import app, ensure_user_profile_initialized


if __name__ == "__main__":
    import uvicorn

    ensure_user_profile_initialized()
    uvicorn.run(app, host="0.0.0.0", port=5001)
