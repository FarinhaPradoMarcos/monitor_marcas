"""SQLite. Toda fonte grava no mesmo formato na tabela mencoes."""
import json
import sqlite3
from pathlib import Path

CAMINHO = Path(__file__).with_name("dados") / "mencoes.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS mencoes (
    id            INTEGER PRIMARY KEY,
    fonte         TEXT NOT NULL,      -- 'noticias', 'youtube', ...
    marca         TEXT NOT NULL,
    busca         TEXT,               -- consulta que trouxe o item
    url           TEXT NOT NULL,
    titulo        TEXT,
    veiculo       TEXT,               -- site da noticia, canal do video...
    texto         TEXT,
    publicado_em  TEXT,               -- ISO 8601 UTC
    coletado_em   TEXT NOT NULL,
    cita_no_titulo INTEGER DEFAULT 0, -- 1 se a marca aparece no titulo (mencao mais forte)
    metricas      TEXT,               -- JSON: views, likes, comentarios...
    sentimento    TEXT,               -- preenchido depois pela analise
    categorias    TEXT,               -- 'risco,produto', 'esporte', 'outros'...
    UNIQUE (fonte, marca, url)
);
-- uma foto das metricas a cada coleta: permite medir crescimento (views da semana)
CREATE TABLE IF NOT EXISTS metricas_hist (
    fonte       TEXT NOT NULL,
    url         TEXT NOT NULL,
    coletado_em TEXT NOT NULL,
    views       INTEGER,
    likes       INTEGER,
    comentarios INTEGER,
    PRIMARY KEY (fonte, url, coletado_em)
);
-- Google Trends: interesse de busca (0-100 relativo a marca base; pode passar de 100)
CREATE TABLE IF NOT EXISTS trends (
    marca       TEXT NOT NULL,
    data        TEXT NOT NULL,
    valor       REAL,
    coletado_em TEXT NOT NULL,
    PRIMARY KEY (marca, data)
);
-- buscas relacionadas em alta (ex.: sabor novo que comecou a ser buscado)
CREATE TABLE IF NOT EXISTS trends_relacionadas (
    marca       TEXT NOT NULL,
    coletado_em TEXT NOT NULL,
    tipo        TEXT NOT NULL,   -- 'em_alta' ou 'principais'
    termo       TEXT NOT NULL,
    valor       TEXT,            -- '+250%', 'Aumento repentino' ou 0-100
    PRIMARY KEY (marca, coletado_em, tipo, termo)
);
CREATE INDEX IF NOT EXISTS ix_mencoes_data ON mencoes (publicado_em);
CREATE INDEX IF NOT EXISTS ix_mencoes_marca ON mencoes (marca, fonte);
"""


def conectar() -> sqlite3.Connection:
    CAMINHO.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(CAMINHO)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    colunas = {r["name"] for r in con.execute("PRAGMA table_info(mencoes)")}
    for col, tipo in (("categorias", "TEXT"), ("sentimento_score", "REAL")):
        if col not in colunas:  # banco criado antes desta coluna existir
            con.execute(f"ALTER TABLE mencoes ADD COLUMN {col} {tipo}")
    return con


def salvar(con: sqlite3.Connection, mencoes: list[dict]) -> int:
    """Insere mencoes novas; repetidas (mesma fonte+marca+url) so atualizam as metricas. Retorna novas."""
    antes = con.execute("SELECT COUNT(*) FROM mencoes").fetchone()[0]
    for m in mencoes:
        con.execute(
            """INSERT INTO mencoes (fonte, marca, busca, url, titulo, veiculo, texto, publicado_em,
                                    coletado_em, cita_no_titulo, metricas, categorias)
               VALUES (:fonte, :marca, :busca, :url, :titulo, :veiculo, :texto, :publicado_em,
                       :coletado_em, :cita_no_titulo, :metricas, :categorias)
               ON CONFLICT (fonte, marca, url) DO UPDATE SET
                   metricas = excluded.metricas, categorias = excluded.categorias""",
            {**m, "metricas": json.dumps(m.get("metricas") or {}, ensure_ascii=False),
             "categorias": m.get("categorias")},
        )
        met = m.get("metricas") or {}
        if "views" in met:
            con.execute("INSERT OR REPLACE INTO metricas_hist VALUES (?, ?, ?, ?, ?, ?)",
                        (m["fonte"], m["url"], m["coletado_em"], met.get("views"),
                         met.get("likes"), met.get("comentarios")))
    con.commit()
    return con.execute("SELECT COUNT(*) FROM mencoes").fetchone()[0] - antes
