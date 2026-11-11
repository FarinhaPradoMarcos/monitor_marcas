"""
Dashboard ao vivo em http://127.0.0.1:8050. Le o banco a cada requisicao, em modo somente leitura.
"""
import json
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

import analise
import dashboard
import db

BASE = Path(__file__).parent
HOST, PORTA = "127.0.0.1", 8050

app = FastAPI(title="Monitor de marcas", docs_url=None, redoc_url=None, openapi_url=None)


def _conectar() -> sqlite3.Connection:
    if not db.CAMINHO.exists():
        raise HTTPException(503, "Banco ainda nao existe: rode `python coletar.py` primeiro.")
    con = sqlite3.connect(f"{db.CAMINHO.as_uri()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


@app.get("/", response_class=HTMLResponse)
def pagina():
    return dashboard.pagina_ao_vivo()


@app.get("/api/semana")
def semana(ate: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$",
                                   description="dia de uma coleta (AAAA-MM-DD); vazio = mais recente")):
    config = json.loads((BASE / "config.json").read_text(encoding="utf-8"))  # edicoes valem na hora
    con = _conectar()
    try:
        agora = analise.ultima_coleta(con, ate)
        if agora is None:
            raise HTTPException(404, f"Nenhuma coleta em {ate}." if ate else "Nenhuma coleta no banco.")
        return analise.semana(con, config, agora)
    finally:
        con.close()


if __name__ == "__main__":
    import uvicorn
    print(f"Dashboard ao vivo em http://{HOST}:{PORTA}  (Ctrl+C para parar)")
    uvicorn.run(app, host=HOST, port=PORTA, log_level="warning")
