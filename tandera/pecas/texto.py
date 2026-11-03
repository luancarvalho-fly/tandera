# -*- coding: utf-8 -*-
"""TEXTO NA TELA: PaddleOCR 3.7 (venceu o RapidOCR no servidor: 67% × 50%) NA PLACA, no ambiente separado .venv-ocr (_ocr_placa.py),
nos quadros 1/s do preparo (lado menor 720). Leitura repetida do mesmo texto em segundos seguidos vira um item só (com de/até)."""
import difflib, json, os, re, subprocess, unicodedata

from .. import base


def _norm(t):
    t = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", t).split())


class _Leitor:
    """o PaddleOCR aberto no ambiente .venv-ocr (_ocr_placa.py): um pedido por linha. Fora do lote abre e fecha a cada vídeo (como
    sempre); no lote fica aberto pro bloco inteiro e o lote fecha no fim da peça."""
    def __init__(self, placa):
        env = dict(os.environ); env["PYTHONIOENCODING"] = "utf-8"
        self.p = subprocess.Popen([base.PY_OCR, os.path.join(os.path.dirname(__file__), "_ocr_placa.py"), "gpu:0" if placa else "cpu"],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8", env=env,
                                  creationflags=base.SEM_JANELA)
        try:
            ok = json.loads(self.p.stdout.readline() or "{}")
            if not ok.get("pronto"): raise RuntimeError("o PaddleOCR não abriu")
        except BaseException:
            self.fechar(); raise

    def ler(self, quadros):
        self.p.stdin.write(json.dumps({"quadros": quadros}, ensure_ascii=False) + "\n"); self.p.stdin.flush()
        r = json.loads(self.p.stdout.readline() or '{"erro": "o leitor fechou"}')
        if "erro" in r: raise RuntimeError(r["erro"])
        return {k: v for k, v in r["out"]}, r.get("onde")

    def fechar(self):
        try: self.p.stdin.close(); self.p.wait(timeout=30)
        except Exception: self.p.kill()


def _leitor(placa):
    if not os.path.exists(base.PY_OCR):
        raise RuntimeError(f"o ambiente do texto na tela não existe ({base.PY_OCR}): rode apps\\TANDERA\\ambiente\\instalar.py --ocr")
    return base.segurado(("ocr", placa), lambda: _Leitor(placa))


def aquecer(ctx):
    _leitor(ctx.placa)


def ler(quadros, placa=True, log=base.log):
    """quadros = [(k, caminho)] → {k: [[texto, nota]]}"""
    leitor = _leitor(placa)
    ok = False
    try:
        r = leitor.ler(quadros); ok = True
        return r
    finally:
        if not base.SEGURAR: leitor.fechar()
        elif not ok: base.largar(("ocr", placa))          # o leitor quebrou no meio do lote: o próximo vídeo abre outro


def rodar(A, ctx):
    from . import preparo
    if not A["preparo"]["tem_imagem"]: return {"itens": []}
    pasta = preparo.caminho(A, "q1"); qs = sorted(os.listdir(pasta))
    lido, onde = ler([[int(f[:5]) - 1, os.path.join(pasta, f)] for f in qs], ctx.placa, ctx.log)
    itens = []                                                       # o mesmo texto em segundos seguidos = um item (de/até)
    for k in sorted(lido):
        for t, nota in lido[k]:
            if len(re.sub(r"\W", "", t)) < 2: continue
            par = [x for x in itens if x["ate"] >= k - 1 and difflib.SequenceMatcher(None, _norm(x["texto"]), _norm(t)).ratio() > 0.6]
            if par:
                x = par[0]; x["ate"] = k; x["vezes"] += 1
                if nota > x["nota"]: x.update(texto=t, nota=nota)
            else:
                itens.append({"texto": t, "nota": nota, "de": k, "ate": k, "vezes": 1})
    return {"itens": [dict(x, de_s=x["de"], ate_s=x["ate"] + 1) for x in itens], "por_segundo": {str(k): v for k, v in lido.items()}, "onde": onde,
            "obs": "de/ate = segundo do quadro 1/s (o texto está na tela pelo menos de de_s até ate_s)"}
