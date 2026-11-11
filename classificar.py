"""Categorias por palavra-chave (config.json -> categorias)."""
from coletores.util import cita


def categorias(texto: str, config: dict) -> list[str]:
    return [nome for nome, termos in config["categorias"].items() if cita(texto, termos)] or ["outros"]


def reclassificar_banco(con, config: dict) -> int:
    """Reaplica as categorias em todo o historico (edicoes no config.json passam a valer para tudo)."""
    rows = con.execute("SELECT id, titulo, texto FROM mencoes").fetchall()
    con.executemany("UPDATE mencoes SET categorias = ? WHERE id = ?",
                    [(",".join(categorias(f"{r['titulo'] or ''} {r['texto'] or ''}", config)), r["id"])
                     for r in rows])
    con.commit()
    return len(rows)


def aplicar(mencoes: list[dict], config: dict) -> list[dict]:
    for m in mencoes:
        m["categorias"] = ",".join(categorias(f"{m.get('titulo') or ''} {m.get('texto') or ''}", config))
    return mencoes
