"""
Sentimento local com distilbert multilingue (ONNX quantizado, ~136 MB), sem PyTorch.
Baixado uma vez para modelos/, numa revisao fixa do repositorio.
"""
import json
import logging
from pathlib import Path

import numpy as np
import requests

log = logging.getLogger("sentimento")

REPO = "Xenova/distilbert-base-multilingual-cased-sentiments-student"
REVISAO = "9d9ac661fd7b0b48535a1fc99b20ae6947629e65"
ARQUIVOS = ["config.json", "tokenizer.json", "onnx/model_quantized.onnx"]
PASTA = Path(__file__).with_name("modelos") / "sentimento"
ROTULOS_PT = {"positive": "positivo", "neutral": "neutro", "negative": "negativo"}
LOTE = 32
MAX_TOKENS = 256
FAIXA_NEUTRA = 0.25  # |P(pos) - P(neg)| abaixo disso conta como neutro


def _baixar():
    for nome in ARQUIVOS:
        destino = PASTA / nome
        if destino.exists():
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://huggingface.co/{REPO}/resolve/{REVISAO}/{nome}"
        log.info("baixando %s", url)
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            tmp = destino.with_suffix(destino.suffix + ".part")
            with open(tmp, "wb") as f:
                for bloco in r.iter_content(1 << 20):
                    f.write(bloco)
            tmp.replace(destino)


class Classificador:
    def __init__(self):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        _baixar()
        cfg = json.loads((PASTA / "config.json").read_text(encoding="utf-8"))
        self.rotulos = [ROTULOS_PT.get(cfg["id2label"][str(i)].lower(), cfg["id2label"][str(i)])
                        for i in range(len(cfg["id2label"]))]
        self.tok = Tokenizer.from_file(str(PASTA / "tokenizer.json"))
        self.tok.enable_truncation(max_length=MAX_TOKENS)
        self.tok.enable_padding()
        self.sess = ort.InferenceSession(str(PASTA / "onnx" / "model_quantized.onnx"),
                                         providers=["CPUExecutionProvider"])
        self.entradas = {i.name for i in self.sess.get_inputs()}

    def classificar(self, textos: list[str]) -> list[tuple[str, float]]:
        """[(rotulo, score)], score = P(positivo) - P(negativo), de -1 a 1."""
        saida = []
        i_pos, i_neg = self.rotulos.index("positivo"), self.rotulos.index("negativo")
        for i in range(0, len(textos), LOTE):
            enc = self.tok.encode_batch([t or "" for t in textos[i:i + LOTE]])
            feed = {"input_ids": np.array([e.ids for e in enc], dtype=np.int64),
                    "attention_mask": np.array([e.attention_mask for e in enc], dtype=np.int64)}
            if "token_type_ids" in self.entradas:
                feed["token_type_ids"] = np.zeros_like(feed["input_ids"])
            logits = self.sess.run(None, feed)[0]
            p = np.exp(logits - logits.max(axis=1, keepdims=True))
            p /= p.sum(axis=1, keepdims=True)
            for linha in p:
                score = float(linha[i_pos] - linha[i_neg])
                # o modelo quase nunca escolhe "neutro" no argmax; usamos uma faixa no score
                rot = "positivo" if score > FAIXA_NEUTRA else "negativo" if score < -FAIXA_NEUTRA else "neutro"
                saida.append((rot, score))
        return saida


def aplicar_no_banco(con) -> int:
    """Classifica todas as mencoes ainda sem sentimento. Retorna quantas."""
    rows = con.execute("SELECT id, fonte, titulo, texto FROM mencoes WHERE sentimento IS NULL").fetchall()
    if not rows:
        return 0
    clf = Classificador()
    # noticia: so o titulo (nao baixamos o corpo); video: titulo + comeco da descricao
    textos = [(r["titulo"] or "") + (" " + (r["texto"] or "")[:300] if r["fonte"] == "youtube" else "")
              for r in rows]
    for r, (rot, score) in zip(rows, clf.classificar(textos)):
        con.execute("UPDATE mencoes SET sentimento = ?, sentimento_score = ? WHERE id = ?",
                    (rot, round(score, 4), r["id"]))
    con.commit()
    return len(rows)
