"""
Google Trends pelos endpoints internos do site (nao oficiais, podem mudar).

O Trends compara no maximo 5 termos e cada consulta tem escala propria. Toda consulta leva a
marca base como ancora e os valores sao reescalados pela media dela (100 = nivel da marca base).
"""
import json
import logging
from datetime import datetime, timezone

import requests

from .util import Cliente

log = logging.getLogger("trends")
BASE = "https://trends.google.com/trends"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0 Safari/537.36")
PERIODO = "today 3-m"   # 90 dias, resolucao diaria


def _json(r: requests.Response) -> dict:
    return json.loads(r.text[r.text.index("{"):])  # resposta vem com prefixo anti-XSSI ")]}'"


def _explore(cli: Cliente, itens: list[str], geo: str) -> list[dict]:
    req = {"comparisonItem": [{"keyword": k, "geo": geo, "time": PERIODO} for k in itens],
           "category": 0, "property": ""}
    return _json(cli.get(f"{BASE}/api/explore",
                         params={"hl": "pt-BR", "tz": "180", "req": json.dumps(req)}))["widgets"]


def _widget(cli: Cliente, w: dict, caminho: str) -> dict:
    return _json(cli.get(f"{BASE}/api/widgetdata/{caminho}",
                         params={"hl": "pt-BR", "tz": "180", "req": json.dumps(w["request"]),
                                 "token": w["token"]}))


def coletar(config: dict, con) -> dict:
    cli = Cliente(intervalo_s=3.0)
    cli.s.headers["User-Agent"] = UA
    cli.get(f"{BASE}/?geo={config['pais']}")  # pega o cookie NID que a API exige
    base = config["marca_base"]
    marcas = config["marcas"]
    ancora = marcas[base]["trends"]
    outras = [m for m in marcas if m != base]
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")

    serie: dict[str, dict[str, float]] = {}
    for i in range(0, len(outras), 4):  # ancora + 4 = limite de 5 termos
        lote = [base] + outras[i:i + 4]
        widgets = _explore(cli, [marcas[m]["trends"] for m in lote], config["pais"])
        ts = next(w for w in widgets if w["id"] == "TIMESERIES")
        pontos = _widget(cli, ts, "multiline")["default"]["timelineData"]
        media_ancora = sum(p["value"][0] for p in pontos) / len(pontos) or 1
        for p in pontos:
            data = datetime.fromtimestamp(int(p["time"]), timezone.utc).date().isoformat()
            for m, v in zip(lote, p["value"]):
                if m == base and i > 0:
                    continue
                serie.setdefault(m, {})[data] = round(v / media_ancora * 100, 2)
        log.info("lote %s ok (%d pontos)", lote, len(pontos))

        if i == 0:  # buscas relacionadas da marca base (a 1a da lista)
            rel = next((w for w in widgets if w["id"].startswith("RELATED_QUERIES")), None)
            if rel:
                d = _widget(cli, rel, "relatedsearches")["default"]["rankedList"]
                for tipo, lista in (("principais", d[0]), ("em_alta", d[1])):
                    for q in lista.get("rankedKeyword", [])[:15]:
                        con.execute("INSERT OR REPLACE INTO trends_relacionadas VALUES (?,?,?,?,?)",
                                    (base, agora, tipo, q["query"], q.get("formattedValue")))

    for m, pts in serie.items():
        con.executemany("INSERT OR REPLACE INTO trends VALUES (?,?,?,?)",
                        [(m, d, v, agora) for d, v in pts.items()])
    con.commit()
    return {m: len(p) for m, p in serie.items()}
