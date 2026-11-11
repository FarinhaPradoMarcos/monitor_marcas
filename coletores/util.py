import os
import re
import time
import unicodedata
from pathlib import Path

import requests

USER_AGENT = "monitor-marcas/0.1"
ERROS_TEMPORARIOS = {429, 500, 502, 503, 504}


def segredo(nome: str) -> str | None:
    """Variavel de ambiente ou linha NOME=valor do .env."""
    if os.environ.get(nome):
        return os.environ[nome]
    env = Path(__file__).resolve().parent.parent / ".env"
    if not env.exists():
        return None
    for linha in env.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*([A-Za-z_]\w*)\s*=\s*(.*?)\s*$", linha)
        if m and m.group(1) == nome:
            return m.group(2).strip("'\"")
    return None


def _sem_chave(texto: str) -> str:
    # mensagens de erro do requests trazem a URL inteira, inclusive ?key=...
    return re.sub(r"(key=)[^&\s'\"]+", r"\1***", str(texto))


def normalizar(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def cita(texto: str, termos: list[str]) -> bool:
    """True se o texto cita algum termo, como frase ou hashtag (#monsterenergy)."""
    norm = normalizar(texto)
    t = f" {norm.replace('#', ' ')} "
    hashtags = set(re.findall(r"#(\w+)", norm))
    for x in termos:
        x = normalizar(x)
        if re.search(rf"\b{re.escape(x)}\b", t) or x.replace(" ", "") in hashtags:
            return True
    return False


class Cliente:
    """Session do requests com intervalo minimo entre chamadas e retry em erro temporario."""

    def __init__(self, intervalo_s: float = 1.5, tentativas: int = 4):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = USER_AGENT
        self.intervalo = intervalo_s
        self.tentativas = tentativas
        self._ultimo = 0.0

    def get(self, url: str, **kw) -> requests.Response:
        erro = None
        for t in range(self.tentativas):
            espera = self._ultimo + self.intervalo - time.monotonic()
            if espera > 0:
                time.sleep(espera)
            self._ultimo = time.monotonic()
            try:
                r = self.s.get(url, timeout=30, **kw)
            except requests.RequestException as e:
                erro = _sem_chave(e)
            else:
                if r.status_code not in ERROS_TEMPORARIOS:
                    if not r.ok:
                        raise RuntimeError(f"HTTP {r.status_code} em {_sem_chave(r.url)}")
                    return r
                erro = f"HTTP {r.status_code}"
            time.sleep(10 * (t + 1))
        raise RuntimeError(f"{url}: falhou {self.tentativas}x ({erro})")
