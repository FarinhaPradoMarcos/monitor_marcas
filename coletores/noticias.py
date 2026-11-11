"""
Google News RSS. Cada consulta devolve no maximo ~100 itens; se bater no teto,
a busca e refeita dia a dia (after:/before:) para nao subcontar.
"""
import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from .util import Cliente, cita

log = logging.getLogger("noticias")
URL = "https://news.google.com/rss/search"
TETO = 95  # perto do maximo de ~100 por consulta: considera que cortou


def _buscar(cliente: Cliente, config: dict, q: str) -> list[ET.Element]:
    pais, idioma = config["pais"], config["idioma"]
    params = {"q": q, "hl": idioma, "gl": pais, "ceid": f"{pais}:{idioma.split('-')[0]}-419"}
    return ET.fromstring(cliente.get(URL, params=params).content).findall(".//item")


def _itens_da_busca(cliente: Cliente, config: dict, busca: str, dias: int) -> list[ET.Element]:
    hoje = date.today()
    inicio = hoje - timedelta(days=dias)
    itens = _buscar(cliente, config, f"{busca} after:{inicio} before:{hoje + timedelta(days=1)}")
    if len(itens) < TETO:
        return itens
    log.info("%s bateu no teto (%d); buscando dia a dia", busca, len(itens))
    itens = []
    for i in range(dias + 1):
        d = inicio + timedelta(days=i)
        do_dia = _buscar(cliente, config, f"{busca} after:{d} before:{d + timedelta(days=1)}")
        if len(do_dia) >= TETO:
            log.warning("%s em %s ainda no teto: contagem desse dia e um piso", busca, d)
        itens += do_dia
    return itens


def coletar(config: dict, dias: int, cliente: Cliente | None = None) -> list[dict]:
    cliente = cliente or Cliente()
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    saida = []
    for marca, m in config["marcas"].items():
        for busca in m["buscas"]:
            try:
                itens = _itens_da_busca(cliente, config, busca, dias)
            except Exception as e:  # uma busca falhar nao derruba a coleta inteira
                log.warning("%s / %s: %s", marca, busca, e)
                continue
            for it in itens:
                veiculo = it.findtext("source") or ""
                titulo = it.findtext("title") or ""
                if veiculo and titulo.endswith(f" - {veiculo}"):  # Google anexa " - Veiculo" no titulo
                    titulo = titulo[: -len(veiculo) - 3]
                try:
                    pub = parsedate_to_datetime(it.findtext("pubDate")).astimezone(timezone.utc)
                    publicado = pub.isoformat(timespec="seconds")
                except (TypeError, ValueError):
                    publicado = None
                saida.append({
                    "fonte": "noticias", "marca": marca, "busca": busca,
                    "url": it.findtext("link"), "titulo": titulo, "veiculo": veiculo,
                    "texto": None, "publicado_em": publicado, "coletado_em": agora,
                    "cita_no_titulo": int(cita(titulo, m["termos"])), "metricas": {},
                })
            log.info("%s / %s: %d itens", marca, busca, len(itens))
    return saida
