"""
YouTube Data API v3. Cota: search.list custa 100 por pagina, videos.list custa 1 por lote de 50.
Videos ja conhecidos continuam sendo atualizados por ACOMPANHAR_DIAS para medir ganho de views.
"""
import logging
from datetime import datetime, timedelta, timezone

from .util import Cliente, cita, segredo

log = logging.getLogger("youtube")
API = "https://www.googleapis.com/youtube/v3"
PAGINAS = 4              # ate 4 x 50 videos por busca (so continua se houver proxima pagina)
IDIOMAS_OK = ("pt",)     # video com idioma declarado diferente disso e descartado; sem idioma, fica
ACOMPANHAR_DIAS = 28     # videos conhecidos ate essa idade continuam com estatistica atualizada


class SemChave(RuntimeError):
    pass


def _get(cliente, chave, recurso, **params):
    r = cliente.get(f"{API}/{recurso}", params={**params, "key": chave})
    return r.json()


def _estatisticas(cliente, chave, ids):
    """{video_id: item} com snippet + statistics, em lotes de 50 (1 unidade cada)."""
    out = {}
    for i in range(0, len(ids), 50):
        d = _get(cliente, chave, "videos", part="snippet,statistics", id=",".join(ids[i:i + 50]))
        out.update({it["id"]: it for it in d.get("items", [])})
    return out


def coletar(config: dict, dias: int, cliente: Cliente | None = None, con=None) -> list[dict]:
    chave = segredo("YOUTUBE_API_KEY")
    if not chave:
        raise SemChave("YOUTUBE_API_KEY nao encontrada no .env")
    cliente = cliente or Cliente(intervalo_s=0.2)
    agora = datetime.now(timezone.utc)
    desde = (agora - timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%SZ")
    gasto = 0

    cota_max = config.get("youtube", {}).get("cota_max_por_coleta", 6000)

    # paginas em rodizio: se a cota acabar, toda marca ja teve pelo menos a primeira pagina
    achados: dict[tuple[str, str], str] = {}
    pendentes = [{"marca": marca, "busca": b, "token": None}
                 for marca, m in config["marcas"].items() for b in m["buscas"]]
    for pagina in range(PAGINAS):
        if not pendentes:
            break
        proximas = []
        for p in pendentes:
            if gasto + 100 > cota_max - 50:  # reserva para o videos.list
                log.warning("cota da coleta atingida (%d); parando na pagina %d", gasto, pagina + 1)
                proximas = []
                break
            params = dict(part="id", type="video", q=p["busca"], regionCode=config["pais"],
                          relevanceLanguage=config["idioma"].split("-")[0], publishedAfter=desde,
                          order="date", maxResults=50)
            if p["token"]:
                params["pageToken"] = p["token"]
            d = _get(cliente, chave, "search", **params)
            gasto += 100
            for it in d.get("items", []):
                achados.setdefault((p["marca"], it["id"]["videoId"]), p["busca"])
            if d.get("nextPageToken"):
                proximas.append({**p, "token": d["nextPageToken"]})
        pendentes = proximas
    for marca in config["marcas"]:
        log.info("%s: %d videos encontrados", marca, sum(1 for (mm, _v) in achados if mm == marca))

    if con is not None:  # videos ja conhecidos: so atualiza os numeros
        limite = (agora - timedelta(days=ACOMPANHAR_DIAS)).isoformat()
        for r in con.execute("""SELECT marca, url, busca FROM mencoes
                                WHERE fonte = 'youtube' AND publicado_em >= ?""", (limite,)):
            achados.setdefault((r["marca"], r["url"].rsplit("v=", 1)[-1]), r["busca"])

    ids = sorted({v for _m, v in achados})
    stats = _estatisticas(cliente, chave, ids)
    gasto += -(-len(ids) // 50)
    log.info("YouTube: %d videos, ~%d unidades de cota gastas", len(ids), gasto)

    coletado = agora.isoformat(timespec="seconds")
    saida = []
    descartes = {"sem_marca": 0, "idioma": 0}
    for (marca, vid), busca in achados.items():
        it = stats.get(vid)
        if not it:  # video removido ou privado
            continue
        sn, st = it["snippet"], it.get("statistics", {})
        titulo = sn.get("title", "")
        termos = config["marcas"][marca]["termos"]
        # a busca do YouTube e solta: so conta se a marca aparece no titulo, descricao ou tags
        if not cita(" ".join([titulo, sn.get("description") or "", " ".join(sn.get("tags") or [])]), termos):
            descartes["sem_marca"] += 1
            continue
        idioma = (sn.get("defaultAudioLanguage") or sn.get("defaultLanguage") or "").lower()
        if idioma and not idioma.startswith(IDIOMAS_OK):
            descartes["idioma"] += 1
            continue
        saida.append({
            "fonte": "youtube", "marca": marca, "busca": busca,
            "url": f"https://www.youtube.com/watch?v={vid}", "titulo": titulo,
            "veiculo": sn.get("channelTitle", ""), "texto": (sn.get("description") or "")[:2000],
            "publicado_em": sn.get("publishedAt", "").replace("Z", "+00:00") or None,
            "coletado_em": coletado,
            "cita_no_titulo": int(cita(titulo, termos)),
            "metricas": {"views": int(st.get("viewCount", 0)), "likes": int(st.get("likeCount", 0)),
                         "comentarios": int(st.get("commentCount", 0))},
        })
    log.info("YouTube: %d videos aceitos, descartados %s", len(saida), descartes)
    return saida
