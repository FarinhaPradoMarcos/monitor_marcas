"""Numeros da semana. Relatorio e dashboard leem daqui, entao os dois sempre batem."""
import json
from datetime import datetime, timedelta, timezone


def _contagem(con, ini, fim):
    """{(marca, fonte): {"total", "titulo"}} de mencoes publicadas em [ini, fim)."""
    out = {}
    for r in con.execute(
            """SELECT marca, fonte, COUNT(DISTINCT url) total, COALESCE(SUM(cita_no_titulo), 0) titulo
               FROM mencoes WHERE publicado_em >= ? AND publicado_em < ? GROUP BY marca, fonte""",
            (ini.isoformat(), fim.isoformat())):
        out[(r["marca"], r["fonte"])] = {"total": r["total"], "titulo": r["titulo"]}
    return out


def _ganho_views(con, ate: str) -> dict[str, int]:
    """views ganhas por video entre as duas ultimas coletas ate `ate` (vazio se so houve uma)."""
    out = {}
    for r in con.execute("""
            WITH fotos AS (
                SELECT url, views, ROW_NUMBER() OVER (PARTITION BY url ORDER BY coletado_em DESC) k
                FROM metricas_hist WHERE fonte = 'youtube' AND coletado_em <= ?)
            SELECT a.url, a.views - b.views ganho FROM fotos a JOIN fotos b
            ON a.url = b.url AND a.k = 1 AND b.k = 2""", (ate,)):
        out[r["url"]] = max(0, r["ganho"] or 0)
    return out


def ultima_coleta(con, ate_dia: str | None = None) -> datetime | None:
    """Horario da ultima coleta (ou da ultima coleta do dia `ate_dia`, formato AAAA-MM-DD)."""
    if ate_dia:
        v = con.execute("SELECT MAX(coletado_em) FROM mencoes WHERE substr(coletado_em, 1, 10) = ?",
                        (ate_dia,)).fetchone()[0]
    else:
        v = con.execute("SELECT MAX(coletado_em) FROM mencoes").fetchone()[0]
    return datetime.fromisoformat(v) if v else None


def coletas(con) -> list[str]:
    """Dias (AAAA-MM-DD) em que houve coleta, do mais recente para o mais antigo."""
    return [r[0] for r in con.execute(
        "SELECT DISTINCT substr(coletado_em, 1, 10) d FROM mencoes ORDER BY d DESC")]


def semana(con, config, agora: datetime | None = None) -> dict:
    """
    Numeros da semana que termina em `agora`. Por padrao, `agora` = horario da ultima coleta:
    assim a janela nao "anda" sozinha entre uma coleta semanal e outra.
    """
    agora = agora or ultima_coleta(con) or datetime.now(timezone.utc)
    ini, ant = agora - timedelta(days=7), agora - timedelta(days=14)
    fim = agora + timedelta(seconds=1)  # inclui o que foi publicado no proprio segundo da coleta
    I, F = ini.isoformat(), fim.isoformat()  # janela [I, F) usada nas consultas
    marcas = config["marcas"]
    base = config.get("marca_base")
    atual, anterior = _contagem(con, ini, fim), _contagem(con, ant, ini)
    fontes = sorted({f for _, f in atual} | {f for _, f in anterior})
    al = config["alerta"]

    R = {"gerado_em": agora.isoformat(timespec="seconds"), "coletas": coletas(con), "inicio": ini.date().isoformat(),
         "fim": agora.date().isoformat(), "marca_base": base, "fontes": fontes,
         "marcas": {m: {"grupo": v.get("grupo", ""), "segmento": v.get("segmento", "")}
                    for m, v in marcas.items()},
         "categorias": list(config["categorias"]) + ["outros"]}

    # --- volume por fonte ---
    R["mencoes"] = {m: {f: {"atual": atual.get((m, f), {}).get("total", 0),
                            "anterior": anterior.get((m, f), {}).get("total", 0),
                            "titulo": atual.get((m, f), {}).get("titulo", 0)} for f in fontes}
                    for m in marcas}

    # Variacao contra a semana anterior so vale se a semana anterior foi coletada por inteiro:
    # noticias (busca dia a dia) sim; YouTube so a partir de uma coleta feita ha 7+ dias.
    completas = set(config.get("fontes_com_historico_completo", []))
    R["comparavel"] = {f: f in completas or bool(con.execute(
        "SELECT 1 FROM mencoes WHERE fonte = ? AND coletado_em < ? LIMIT 1", (f, ini.isoformat())).fetchone())
        for f in fontes}

    # --- sentimento: so mencoes com a marca no titulo (a manchete/titulo fala da marca) ---
    minimo = al.get("amostra_minima_sentimento", 15)
    R["sentimento"] = {m: {"positivo": 0, "neutro": 0, "negativo": 0, "score_medio": None,
                           "amostra_pequena": True} for m in marcas}
    for r in con.execute("""SELECT marca, sentimento, COUNT(DISTINCT url) n FROM mencoes
                            WHERE publicado_em >= ? AND publicado_em < ? AND sentimento IS NOT NULL AND cita_no_titulo = 1
                            GROUP BY marca, sentimento""", (I, F)):
        if r["marca"] in R["sentimento"]:
            R["sentimento"][r["marca"]][r["sentimento"]] = r["n"]
    for r in con.execute("""SELECT marca, AVG(sentimento_score) s, COUNT(DISTINCT url) n FROM mencoes
                            WHERE publicado_em >= ? AND publicado_em < ? AND sentimento_score IS NOT NULL AND cita_no_titulo = 1
                            GROUP BY marca""", (I, F)):
        if r["marca"] in R["sentimento"]:
            R["sentimento"][r["marca"]].update(score_medio=round(r["s"], 3), amostra_pequena=r["n"] < minimo)

    # --- categorias ---
    R["por_categoria"] = {m: {c: 0 for c in R["categorias"]} for m in marcas}
    for r in con.execute("""SELECT marca, categorias, COUNT(DISTINCT url) n FROM mencoes
                            WHERE publicado_em >= ? AND publicado_em < ? GROUP BY marca, categorias""", (I, F)):
        for c in (r["categorias"] or "outros").split(","):
            if r["marca"] in R["por_categoria"] and c in R["por_categoria"][r["marca"]]:
                R["por_categoria"][r["marca"]][c] += r["n"]

    # --- YouTube ---
    ganho = _ganho_views(con, F)
    R["youtube"] = {"tem_historico": bool(ganho), "por_marca": {}, "top": []}
    for m in marcas:
        rows = con.execute("""SELECT url, MAX(titulo) titulo, MAX(veiculo) veiculo, MAX(metricas) metricas
                              FROM mencoes WHERE fonte = 'youtube' AND marca = ? AND publicado_em >= ?
                              AND publicado_em < ? GROUP BY url""", (m, I, F)).fetchall()
        vids = [(json.loads(r["metricas"] or "{}").get("views", 0), r) for r in rows]
        conhecidos = [r["url"] for r in con.execute(
            "SELECT DISTINCT url FROM mencoes WHERE fonte = 'youtube' AND marca = ? AND coletado_em <= ?", (m, F))]
        R["youtube"]["por_marca"][m] = {"videos": len(rows), "views": sum(v for v, _ in vids),
                                        "views_ganhas": sum(ganho.get(u, 0) for u in conhecidos)}
        for v, r in sorted(vids, key=lambda x: -x[0])[:3]:
            if v:
                R["youtube"]["top"].append({"marca": m, "titulo": r["titulo"], "url": r["url"],
                                            "canal": r["veiculo"], "views": v})

    # --- Google Trends ---
    serie = {}
    for r in con.execute("SELECT marca, data, valor FROM trends ORDER BY data"):
        serie.setdefault(r["marca"], {})[r["data"]] = r["valor"]
    datas = sorted({d for s in serie.values() for d in s})
    R["trends"] = {"datas": datas, "series": {m: [serie.get(m, {}).get(d) for d in datas] for m in marcas},
                   "semana": {}}
    d_ini, d_ant, d_fim = ini.date().isoformat(), ant.date().isoformat(), agora.date().isoformat()
    for m in marcas:
        s = serie.get(m, {})
        a = [v for d, v in s.items() if d_ini <= d <= d_fim]
        p = [v for d, v in s.items() if d_ant <= d < d_ini]
        R["trends"]["semana"][m] = {"atual": round(sum(a) / len(a), 1) if a else None,
                                    "anterior": round(sum(p) / len(p), 1) if p else None}
    ultima = con.execute("SELECT MAX(coletado_em) FROM trends_relacionadas WHERE coletado_em <= ?", (F,)).fetchone()[0]
    R["trends"]["em_alta"] = [dict(r) for r in con.execute(
        """SELECT marca, termo, valor FROM trends_relacionadas WHERE coletado_em = ? AND tipo = 'em_alta'""",
        (ultima,))] if ultima else []

    # --- alertas ---
    alertas = []
    for m in marcas:
        for f in fontes:
            if not R["comparavel"][f]:
                continue
            c = R["mencoes"][m][f]
            n, p = c["atual"], c["anterior"]
            if n >= al["mencoes_minimas"] and (p == 0 or (n - p) / p * 100 >= al["aumento_minimo_pct"]):
                alertas.append({"tipo": "pico", "marca": m, "fonte": f, "de": p, "para": n})
    filtro_neg = "AND sentimento = 'negativo'" if al.get("risco_exige_negativo") else ""
    for r in con.execute(
            f"""SELECT marca, MAX(titulo) titulo, MAX(veiculo) veiculo, url, MAX(publicado_em) publicado_em,
                       MIN(sentimento_score) score
                FROM mencoes WHERE publicado_em >= ? AND publicado_em < ? AND (',' || categorias || ',') LIKE '%,risco,%'
                AND cita_no_titulo = 1 {filtro_neg}
                -- risco em conteudo so de esporte (ex.: briga de equipe na F1) nao e risco da bebida
                AND NOT ((',' || categorias || ',') LIKE '%,esporte,%'
                         AND (',' || categorias || ',') NOT LIKE '%,produto,%')
                GROUP BY marca, titulo ORDER BY publicado_em DESC""",  # mesmo titulo em 2 sites = 1 alerta
            (I, F)):
        alertas.append({"tipo": "risco", **dict(r)})
    R["alertas"] = alertas

    # --- destaques: mencoes mais negativas e mais positivas com a marca no titulo ---
    R["destaques"] = {}
    for m in marcas:
        def lista(ordem):
            return [dict(r) for r in con.execute(
                f"""SELECT fonte, MAX(titulo) titulo, MAX(veiculo) veiculo, url, MAX(publicado_em) publicado_em,
                           MAX(sentimento) sentimento, MAX(sentimento_score) score
                    FROM mencoes WHERE marca = ? AND cita_no_titulo = 1 AND publicado_em >= ?
                    AND publicado_em < ? AND sentimento_score IS NOT NULL
                    GROUP BY url ORDER BY score {ordem} LIMIT 3""", (m, I, F))]
        R["destaques"][m] = {"negativas": [d for d in lista("ASC") if d["sentimento"] == "negativo"],
                             "positivas": [d for d in lista("DESC") if d["sentimento"] == "positivo"]}

    # --- historico: blocos de 7 dias terminando agora (iguais ao relatorio), so os completos ---
    # Semana do calendario cortaria a semana atual pela metade e pareceria uma queda.
    primeira = con.execute("SELECT MIN(publicado_em) FROM mencoes WHERE fonte = 'noticias'").fetchone()[0]
    blocos = []
    if primeira:
        inicio_dados = datetime.fromisoformat(primeira) - timedelta(days=1)  # folga de fuso/arredondamento
        k = 0
        while k < 52 and agora - timedelta(days=7 * (k + 1)) >= inicio_dados:
            blocos.append((agora - timedelta(days=7 * (k + 1)), agora - timedelta(days=7 * k)))
            k += 1
    blocos.reverse()
    series = {m: [] for m in marcas}
    for a, b in blocos:
        cont = {r["marca"]: r["n"] for r in con.execute(
            """SELECT marca, COUNT(DISTINCT url) n FROM mencoes WHERE publicado_em >= ? AND publicado_em < ?
               GROUP BY marca""", (a.isoformat(), b.isoformat()))}
        for m in marcas:
            series[m].append(cont.get(m, 0))
    R["historico"] = {"semanas": [f"{a:%d/%m} a {b - timedelta(days=1):%d/%m}" for a, b in blocos],
                      "series": series}
    return R
