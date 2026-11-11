"""Relatorio semanal em markdown (os numeros vem de analise.semana)."""
from datetime import datetime
from pathlib import Path

import analise

PASTA = Path(__file__).with_name("relatorios")


def _fmt(n) -> str:
    n = n or 0
    return f"{n / 1e6:.1f} mi" if n >= 1e6 else f"{n / 1e3:.1f} mil" if n >= 1e3 else f"{n:.0f}"


def _var(a, p) -> str:
    if a is None or p is None:
        return "-"
    return f"{(a - p) / p * 100:+.0f}%" if p else ("novo" if a else "-")


def _link(d) -> str:
    return f"[{d['titulo']}]({d['url']}) ({d.get('veiculo') or d.get('canal')}, {str(d['publicado_em'])[:10]})" \
        if d.get("publicado_em") else f"[{d['titulo']}]({d['url']})"


def gerar(con, config, agora: datetime | None = None) -> Path:
    R = analise.semana(con, config, agora)
    marcas, base = list(R["marcas"]), R["marca_base"]
    L = [f"# Monitor de marcas: {R['inicio']} a {R['fim']}", "",
         f"Marca base: **{base}**. Comparação contra a semana anterior.", ""]

    # alertas
    L += ["## Alertas", ""]
    if not R["alertas"]:
        L.append("- Nenhum alerta nesta semana.")
    for a in R["alertas"]:
        if a["tipo"] == "pico":
            L.append(f"- 📈 **{a['marca']}** em {a['fonte']}: {a['de']} → {a['para']} menções")
        else:
            L.append(f"- ⚠️ **{a['marca']}** (risco, sentimento {a['score']:+.2f}): {_link(a)}")
    L.append("")

    # visao geral por segmento
    L += ["## Visão geral", "",
          "| Marca | Grupo | Segmento | Notícias | YouTube | Sentimento médio | Busca (Trends, Monster=100) |",
          "|---|---|---|---|---|---|---|"]
    ordem = sorted(marcas, key=lambda m: (R["marcas"][m]["segmento"], m != base, m))
    for m in ordem:
        info, men, s, t = R["marcas"][m], R["mencoes"][m], R["sentimento"][m], R["trends"]["semana"][m]
        def cel(f):
            if f not in men:
                return "-"
            v = _var(men[f]["atual"], men[f]["anterior"]) if R["comparavel"][f] else "sem base"
            return f"{men[f]['atual']} ({v})"
        sm = ("-" if s["score_medio"] is None else
              f"{s['score_medio']:+.2f}" + (" (amostra pequena)" if s["amostra_pequena"] else ""))
        tr = f"{t['atual']:.0f} ({_var(t['atual'], t['anterior'])})" if t["atual"] is not None else "-"
        nome = f"**{m}**" if m == base else m
        L.append(f"| {nome} | {info['grupo']} | {info['segmento']} | {cel('noticias')} | {cel('youtube')} "
                 f"| {sm} | {tr} |")
    L += ["", "Entre parênteses: variação contra a semana anterior (\"sem base\" = a semana anterior "
          "ainda não foi coletada por inteiro nessa fonte). Sentimento de -1 (negativo) a +1 (positivo).", ""]

    # sentimento
    L += ["## Sentimento das menções da semana", "",
          "| Marca | Positivo | Neutro | Negativo | % negativo |", "|---|---|---|---|---|"]
    for m in ordem:
        s = R["sentimento"][m]
        tot = s["positivo"] + s["neutro"] + s["negativo"]
        if tot:
            neg = f"{s['negativo'] / tot * 100:.0f}%" + (" (amostra pequena)" if s["amostra_pequena"] else "")
            L.append(f"| {m} | {s['positivo']} | {s['neutro']} | {s['negativo']} | {neg} |")
    L += ["", "Só conta menções com a marca no título. Modelo automático: bom para tendência, "
          "erra ironia e gíria (ex.: \"briga Coca vs Pepsi\" em vídeo de humor sai negativo).", ""]

    # youtube
    yt = R["youtube"]
    L += ["## YouTube: popularidade", "",
          "| Marca | Vídeos novos | Views (vídeos novos) | Views ganhas desde a última coleta |",
          "|---|---|---|---|"]
    for m in ordem:
        y = yt["por_marca"][m]
        if y["videos"] or y["views_ganhas"]:
            L.append(f"| {m} | {y['videos']} | {_fmt(y['views'])} | "
                     f"{_fmt(y['views_ganhas']) if yt['tem_historico'] else 'sem histórico ainda'} |")
    L += ["", "Mais vistos da semana:", ""]
    L += [f"- **{v['marca']}**: [{v['titulo']}]({v['url']}) ({v['canal']}, {_fmt(v['views'])} views)"
          for v in sorted(yt["top"], key=lambda v: -v["views"])[:10]] or ["- nenhum"]
    L.append("")

    # trends em alta
    if R["trends"]["em_alta"]:
        L += [f"## Buscas em alta ligadas a {base} (Google Trends)", ""]
        L += [f"- {q['termo']} ({q['valor']})" for q in R["trends"]["em_alta"]] + [""]

    # categorias
    cats = R["categorias"]
    L += ["## Em que cada marca apareceu", "",
          "| Marca | " + " | ".join(c.capitalize() for c in cats) + " |", "|---" * (len(cats) + 1) + "|"]
    for m in ordem:
        L.append(f"| {m} | " + " | ".join(str(R["por_categoria"][m][c]) for c in cats) + " |")
    L += ["", "Uma menção pode cair em mais de uma categoria.", ""]

    # destaques
    L += ["## Destaques por marca", ""]
    for m in ordem:
        d = R["destaques"][m]
        if d["negativas"] or d["positivas"]:
            L += [f"### {m}", ""]
            L += [f"- 🔴 {_link(x)}" for x in d["negativas"]] + [f"- 🟢 {_link(x)}" for x in d["positivas"]] + [""]

    PASTA.mkdir(exist_ok=True)
    caminho = PASTA / f"{R['fim']}.md"
    caminho.write_text("\n".join(L), encoding="utf-8")
    return caminho
