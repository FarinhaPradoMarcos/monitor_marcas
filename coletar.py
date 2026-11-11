"""
python coletar.py                 # ultimos 7 dias
python coletar.py --dias 14       # primeira vez, para ja ter semana anterior
python coletar.py --so-relatorio  # sem coletar, so regera relatorio e dashboard
"""
import argparse
import json
import logging
from pathlib import Path

import classificar
import dashboard
import db
import relatorio
import sentimento
from coletores import noticias, trends, youtube

BASE = Path(__file__).parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=7)
    ap.add_argument("--so-relatorio", action="store_true",
                    help="nao coleta nada: so reclassifica e gera relatorio + dashboard com o banco atual")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")

    config = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
    con = db.conectar()

    if args.so_relatorio:
        classificar.reclassificar_banco(con, config)
        print(f"Relatorio: {relatorio.gerar(con, config)}")
        print(f"Dashboard: {dashboard.gerar(con, config)}")
        return

    coletores = {
        "noticias": lambda: noticias.coletar(config, args.dias),
        "youtube": lambda: youtube.coletar(config, args.dias, con=con),
    }
    for nome, coletar in coletores.items():
        try:
            itens = coletar()
        except youtube.SemChave as e:
            print(f"{nome}: pulado ({e})")
            continue
        except Exception:
            logging.exception("coletor %s falhou", nome)
            continue
        classificar.aplicar(itens, config)
        print(f"{nome}: {len(itens)} itens, {db.salvar(con, itens)} novos")

    classificar.reclassificar_banco(con, config)

    try:
        print("trends:", trends.coletar(config, con))
    except Exception:
        logging.exception("coletor trends falhou")

    try:
        print(f"sentimento: {sentimento.aplicar_no_banco(con)} mencoes classificadas")
    except Exception:
        logging.exception("analise de sentimento falhou")

    caminho = relatorio.gerar(con, config)
    print(f"\nRelatorio: {caminho}")
    print(f"Dashboard: {dashboard.gerar(con, config)}")


if __name__ == "__main__":
    main()
