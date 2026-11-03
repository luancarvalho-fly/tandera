# -*- coding: utf-8 -*-
"""FALA: o texto pelo Whisper large-v3-turbo (faster-whisper, fp16 na placa; int8 no processador quando pedido) na VOZ SEPARADA,
e cada palavra no MILISSEGUNDO pelo MMS_FA (torchaudio) + conferência na onda (régua, 17/10: início 8 ms, 74% a ±1 quadro).
Filtros contra fala inventada: o mesmo texto 3+ vezes seguidas = laço (sai); trecho sem energia na voz (< −40 dB) sai.
Também é a FALA de quem só precisa de texto com tempo (Kakashi, CORRETOR, /sonoplastia --cpu): `transcrever()`."""
import os, re, unicodedata

import numpy as np

from .. import base

WHISPER = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
_modelos = {}


def _whisper(dispositivo):
    if dispositivo == "cuda":
        # 01/11: o ctranslate2 não acha sozinho a cublas64_12.dll no Windows (ela vem com o torch, em torch\lib). Dentro do `analisar` o
        # torch já estava carregado e funcionava; chamado sozinho (`tandera fala --dispositivo cuda`, Kakashi/DUBX) quebrava.
        import torch  # noqa: F401  (carrega as DLLs do CUDA)
    from faster_whisper import WhisperModel
    k = dispositivo
    if k not in _modelos:
        _modelos[k] = WhisperModel(WHISPER, device=dispositivo, compute_type="float16" if dispositivo == "cuda" else "int8")
    return _modelos[k]


def soltar():
    _modelos.clear(); base.liberar_torch()


def _mms(dispositivo):
    from torchaudio.pipelines import MMS_FA as b
    return base.segurado(("mms", dispositivo), lambda: b.get_model().to(dispositivo))


def aquecer(ctx):
    """o lote: Whisper e MMS carregados uma vez pro bloco (fora do lote o Whisper sai da placa antes do MMS entrar)"""
    dev = "cuda" if ctx.placa else "cpu"
    _whisper(dev); _mms(dev)


def _pico_db(x16, a, b):
    y = x16[int(a * 16000):max(int(a * 16000) + 1, int(b * 16000))]
    if not len(y): return -99.0
    k = 160; n = len(y) // k
    return float(10 * np.log10(np.max(np.mean(y[: n * k].reshape(n, k) ** 2, axis=1)) + 1e-12)) if n else float(10 * np.log10(np.mean(y ** 2) + 1e-12))


def _referencia_db(x16):
    """o «alto» da fala deste arquivo: percentil 99 da energia em janelas de 10 ms"""
    k = 160; n = len(x16) // k
    if not n: return -20.0
    e = 10 * np.log10(np.mean(x16[: n * k].reshape(n, k) ** 2, axis=1) + 1e-12)
    return float(np.percentile(e, 99))


def trechos_com_som(x16, piso, junta=1.0, minimo=0.3, folga=0.3):
    """[(ini, fim)] em s dos trechos em que a energia (10 ms) passa do `piso`: buracos < `junta` s se juntam, trecho com menos de `minimo`
    s de som sai (estalo), cada um ganha `folga` s dos dois lados. É o MESMO corte relativo do filtro de energia, só que ANTES do Whisper."""
    k = 160; n = len(x16) // k
    if not n: return []
    e = 10 * np.log10(np.mean(x16[: n * k].reshape(n, k) ** 2, axis=1) + 1e-12)
    on = np.where(e >= piso)[0]
    if not len(on): return []
    spans, a, b, cnt = [], on[0], on[0], 1
    for i in on[1:]:
        if (i - b) * 0.01 <= junta: b = i; cnt += 1
        else:
            spans.append((a, b, cnt)); a = b = i; cnt = 1
    spans.append((a, b, cnt))
    dur = len(x16) / 16000
    out = []
    for a, b, cnt in spans:
        if cnt * 0.01 < minimo: continue
        ini, fim = max(0.0, a * 0.01 - folga), min(dur, (b + 1) * 0.01 + folga)
        if out and ini <= out[-1][1]: out[-1] = (out[-1][0], fim)
        else: out.append((ini, fim))
    return out


def transcrever(audio, idioma=None, dispositivo="cuda", palavras=False, vad=False, filtrar=True):
    """audio = caminho (qualquer formato) ou float32 16 kHz mono. Devolve {idioma, segmentos:[{ini,fim,txt,palavras?}], descartados}.
    idioma None/'auto' = o Whisper detecta.
    01/11 (medido numa sessão do Kakashi, 3 min de microfone): o VAD do faster-whisper e o corte de energia em −40 dB ABSOLUTO comiam
    fala de verdade (304 palavras × 402 sem filtro; «Ó, rodando. Tipo... 1463» sumia). Agora: sem VAD, e o trecho só sai se o pico dele
    ficar 40 dB abaixo do «alto» do próprio arquivo (relativo: microfone baixo não perde fala) ou se for laço (3+ iguais seguidos).
    01/11 «2026-11-01c» (sessão do Kakashi 2026-11-01_135524: 4 min com 100 s de silêncio digital no começo → ZERO segmentos): no silêncio
    o Whisper inventa «Legenda Adriana Zanotto» e, escrevendo cada trecho a partir do anterior, repete a frase por cima da fala de verdade;
    o filtro de laço tirava tudo. Agora: (1) o Whisper só ouve os trechos COM SOM (o mesmo corte relativo, antes dele: `clip_timestamps`);
    (2) cada trecho não herda o texto do anterior (`condition_on_previous_text=False`), então uma invenção não contamina o resto."""
    x16 = base.ler_audio(audio, 16000) if isinstance(audio, str) else np.asarray(audio, np.float32)
    if len(x16) < 1600:
        return {"idioma": None, "segmentos": [], "descartados": [], "modelo": WHISPER}
    trechos = trechos_com_som(x16, _referencia_db(x16) - 40) if filtrar else [(0.0, len(x16) / 16000)]
    if not trechos:
        return {"idioma": None, "segmentos": [], "descartados": [], "modelo": WHISPER, "sem_som": True}
    m = _whisper(dispositivo)
    segs, info = m.transcribe(x16, language=None if idioma in (None, "", "auto") else idioma, vad_filter=vad, beam_size=5,
                              word_timestamps=palavras, condition_on_previous_text=False,
                              clip_timestamps=[t for ab in trechos for t in ab])
    brutos = [(s.start, s.end, s.text.strip(), [(w.word.strip(), w.start, w.end) for w in (s.words or []) if w.word.strip()])
              for s in segs if s.text.strip()]
    out, fora = _filtra(brutos, x16, filtrar, palavras)
    return {"idioma": info.language, "segmentos": out, "descartados": fora, "modelo": WHISPER + (" fp16" if dispositivo == "cuda" else " int8 (processador)")}


# frase INTEIRA que o Whisper inventa em silêncio/estalo (vista no Kakashi e em apps de chat); só sai se não for a ÚNICA fala de um áudio curto
INVENTADAS = re.compile(r"((tchau)[,.!]?\s*)+|obrigad[oa][.!]?|thank you[.!]?|.*amara\.org.*|.*legenda.*zanotto.*|legendas? pela comunidade.*",
                        re.I)


def _filtra(brutos, x16, filtrar=True, palavras=False):
    """[(ini, fim, txt, [(p, ini, fim)])] → (segmentos, descartados): laço (3+ iguais seguidos), energia RELATIVA (pico 40 dB abaixo do
    «alto» do arquivo) e frase inventada. O MESMO filtro pros dois motores (o do Tandera e o rápido)."""
    chave = [re.sub(r"\W+", " ", b[2].lower()).strip() for b in brutos]
    laco, i = set(), 0
    while i < len(brutos):
        k = i
        while k + 1 < len(brutos) and chave[k + 1] == chave[i]: k += 1
        if k - i + 1 >= 3: laco.update(range(i, k + 1))
        i = k + 1
    sozinha = len(brutos) == 1 and len(x16) / 16000 < 6
    out, fora = [], []
    piso = _referencia_db(x16) - 40
    for n, (a, b, txt, ws) in enumerate(brutos):
        if not re.search(r"\w", txt):           # só pontuação («.», «...»): não é fala
            continue
        if filtrar and (n in laco or _pico_db(x16, a, b) < piso or (INVENTADAS.fullmatch(txt) and not sozinha)):
            fora.append(txt); continue
        d = {"ini": round(a, 3), "fim": round(b, 3), "txt": txt}
        if palavras:
            d["palavras"] = [{"p": p, "ini": round(wa, 3), "fim": round(wb, 3)} for p, wa, wb in ws]
        out.append(d)
    return out, fora


RAPIDO = "http://127.0.0.1:8178"          # o whisper-server do OpenWhispr (ditado): o MESMO large-v3-turbo, já carregado na placa
# 01/11 (ele: «ganha o modelo large»): o LARGE-v3 que ele escolheu pra DUBLAGEM em 23/08 (medido no arquivo dele: o turbo agrupava a frase
# errado e adiantava a 2ª frase ~900 ms; o large agrupou certo). O mesmo whisper-server + ggml-large-v3 que o DUBX subia, na 8899.
# pacote da Fly: no PC do Luan eram o whisper-server do OpenWhispr e o ggml-large-v3 dele (caminhos fixos); aqui, por variável (sem
# elas, o modelo="large" para com «falta»). O Tandera normal (turbo) não usa isto.
WHISPER_SERVER = os.environ.get("TANDERA_WHISPER_SERVER", "")
GGML_LARGE = os.environ.get("TANDERA_GGML_LARGE", "")
LARGE = "http://127.0.0.1:8899"


def servidor_large():
    """(url, processo que EU subi ou None): usa o large-v3 da 8899 se já estiver no ar; senão sobe (sem janela) e espera até ~60 s"""
    import os, subprocess, time
    if rapido_no_ar(LARGE):
        return LARGE, None
    for p in (WHISPER_SERVER, GGML_LARGE):
        if not os.path.exists(p):
            raise RuntimeError(f"Whisper large: falta {p}")
    pr = subprocess.Popen([WHISPER_SERVER, "--model", GGML_LARGE, "--host", "127.0.0.1", "--port", "8899", "--threads", "8"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=base.SEM_JANELA)
    for _ in range(90):
        time.sleep(0.7)
        if rapido_no_ar(LARGE):
            return LARGE, pr
        if pr.poll() is not None:
            break
    pr.terminate()
    raise RuntimeError("o Whisper large não subiu na 8899")


def _palavras_whispercpp(ws, a):
    """o whisper.cpp manda TOKENS («most» + «rando»): junta em palavras (token que começa com espaço abre palavra nova) e tira os
    tokens especiais ([_BEG_], [_TT_123])"""
    out = []
    for w in ws or []:
        t = w.get("word") or ""
        if not t.strip() or re.fullmatch(r"\s*\[_?[A-Z_0-9]+\]\s*", t):
            continue
        ini, fim = a + float(w["start"]), a + float(w["end"])
        if out and not t.startswith(" "):
            out[-1] = (out[-1][0] + t.strip(), out[-1][1], fim)
        else:
            out.append((t.strip(), ini, fim))
    return out


def rapido_no_ar(url=RAPIDO):
    import urllib.request
    try:
        urllib.request.urlopen(url + "/", timeout=0.5).read(1)
        return True
    except Exception as e:
        return getattr(e, "code", None) is not None          # respondeu com erro HTTP = está no ar


def _wav16(y):
    import io, wave
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())
    return b.getvalue()


def _pedacos(trechos, x16, maximo=28.0):
    """trechos com som → pedaços de até `maximo` s, cortando no ponto mais quieto entre 60% e 100% do limite"""
    out = []
    for a, b in trechos:
        while b - a > maximo:
            i0, i1 = int((a + maximo * 0.6) * 100), int((a + maximo) * 100)
            seg = x16[i0 * 160:i1 * 160]
            n = len(seg) // 160
            corte = a + maximo if not n else (i0 + int(np.argmin(np.mean(seg[: n * 160].reshape(n, 160) ** 2, axis=1)))) / 100
            out.append((a, corte)); a = corte
        out.append((a, b))
    return out


def transcrever_rapido(audio, idioma=None, dispositivo="cpu", palavras=False, url=RAPIDO, modelo="turbo", max_len=None):
    """modelo="large": o large-v3 da DUBLAGEM (servidor próprio na 8899, sobe e desce sozinho se não estava no ar). Sem fallback pro turbo:
    quem pediu o large (o DUBX) decidiu que o turbo erra o tempo da frase."""
    if modelo == "large":
        url, meu = servidor_large()
        try:
            r = _transcrever_servidor(audio, idioma, palavras, url, max_len=max_len)
            r["modelo"] = "whisper-server large-v3 (ggml, o da dublagem)"
            return r
        finally:
            if meu is not None:
                meu.terminate()
    return _transcrever_servidor(audio, idioma, palavras, url, dispositivo, max_len)


def _transcrever_servidor(audio, idioma=None, palavras=False, url=RAPIDO, dispositivo="cpu", max_len=None):
    """A FALA do Tandera pra quem precisa de resposta NA HORA (apps de chat e de ditado): as regras do Tandera
    (só os trechos com som, cada pedaço ouvido sozinho, laço, energia relativa, frase inventada) em cima do motor que JÁ ESTÁ CARREGADO
    (o whisper-server do ditado, 8178: 0,2 s num áudio de 12 s × 5–13 s pra carregar o do Tandera — medido 01/11). Sem o 8178 no ar,
    roda o Whisper do próprio Tandera (`transcrever`). Mesmo formato de saída + "via"."""
    import json, urllib.request, uuid
    x16 = base.ler_audio(audio, 16000) if isinstance(audio, str) else np.asarray(audio, np.float32)
    if len(x16) < 1600:
        return {"idioma": None, "segmentos": [], "descartados": [], "modelo": WHISPER, "via": "nada"}
    if not rapido_no_ar(url):
        r = transcrever(x16, idioma, dispositivo, palavras)
        r["via"] = "tandera (8178 fora do ar)"
        return r
    trechos = trechos_com_som(x16, _referencia_db(x16) - 40)
    if not trechos:
        return {"idioma": None, "segmentos": [], "descartados": [], "modelo": "whisper-server 8178", "sem_som": True, "via": "8178"}
    brutos, lingua = [], None
    for a, b in _pedacos(trechos, x16):
        sep = uuid.uuid4().hex
        campo = lambda n, v: f"--{sep}\r\nContent-Disposition: form-data; name=\"{n}\"\r\n\r\n{v}\r\n".encode()   # noqa: E731
        corpo = (f"--{sep}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.wav\"\r\nContent-Type: audio/wav\r\n\r\n".encode()
                 + _wav16(x16[int(a * 16000):int(b * 16000)]) + b"\r\n" + campo("response_format", "verbose_json") + campo("temperature", "0")
                 + campo("split_on_word", "true")          # trecho nunca quebra no meio da palavra («dispon» / «ível»)
                 + (campo("max_len", str(int(max_len))) if max_len else b"")   # a quebra de linha da legenda do DUBX
                 + (campo("language", idioma) if idioma not in (None, "", "auto") else b"") + f"--{sep}--\r\n".encode())
        req = urllib.request.Request(url + "/inference", data=corpo, headers={"Content-Type": "multipart/form-data; boundary=" + sep})
        r = json.loads(urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace"))
        lingua = lingua or r.get("language") or r.get("detected_language")
        for s in r.get("segments") or []:
            t = (s.get("text") or "").strip()
            if not t:
                continue
            ws = _palavras_whispercpp(s.get("words"), a)
            raw = s.get("text") or ""
            if brutos and raw[:1].isalpha() and ws:          # o segmento começou no MEIO de uma palavra: o pedaço volta pro anterior
                pa, pb, ptxt, pws = brutos[-1]
                pedaco = ws.pop(0)
                if pws:
                    pws[-1] = (pws[-1][0] + pedaco[0], pws[-1][1], pedaco[2])
                brutos[-1] = (pa, pedaco[2], ptxt + pedaco[0], pws)
                t = " ".join(w[0] for w in ws) if ws else t[len(pedaco[0]):].strip()
                if not t:
                    continue
                s = dict(s, start=ws[0][1] - a if ws else s["start"])
            brutos.append((a + float(s["start"]), a + float(s["end"]), t, ws))
    out, fora = _filtra(brutos, x16, True, palavras)
    porta = url.rsplit(":", 1)[-1]
    return {"idioma": lingua, "segmentos": out, "descartados": fora, "modelo": f"whisper-server {porta} (OpenWhispr, large-v3-turbo)", "via": porta}


def para_srt(segmentos, max_len=70):
    """segmentos (com `palavras`) → texto SRT. max_len ≤ 1 = uma palavra por bloco (o que o DUBX usa pra casar fala × roteiro); senão junta as
    palavras de cada segmento em linhas de até max_len caracteres (o `max_len` + `split_on_word` do whisper.cpp que o DUBX usava)."""
    def hms(t):
        ms = int(round(max(0.0, t) * 1000))
        return "%02d:%02d:%02d,%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)
    blocos = []
    for s in segmentos:
        ws = s.get("palavras") or [{"p": s["txt"], "ini": s["ini"], "fim": s["fim"]}]
        if max_len <= 1:
            # o servidor já devolveu uma palavra por segmento (max_len 1, o jeito do DUBX): o segmento É o bloco
            blocos += [(s["ini"], s["fim"], s["txt"])] if len(s["txt"].split()) <= 1 else [(w["ini"], w["fim"], w["p"]) for w in ws]
            continue
        if len(s["txt"]) <= max_len:            # o servidor já quebrou no max_len (o jeito do DUBX): o segmento É a linha
            blocos.append((s["ini"], s["fim"], s["txt"]))
            continue
        atual = []
        for w in ws:
            if atual and len(" ".join(x["p"] for x in atual + [w])) > max_len:
                blocos.append((atual[0]["ini"], atual[-1]["fim"], " ".join(x["p"] for x in atual))); atual = []
            atual.append(w)
        if atual:
            blocos.append((atual[0]["ini"], atual[-1]["fim"], " ".join(x["p"] for x in atual)))
    return "\n".join(f"{i}\n{hms(a)} --> {hms(b)}\n{t}\n" for i, (a, b, t) in enumerate(blocos, 1))


def _limpa(t):
    t = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
    return [w for w in re.sub(r"[^a-z' ]", " ", t).split() if w]


def alinhar(x16, segmentos, dispositivo="cuda"):
    """cada palavra no ms: MMS_FA no trecho de cada segmento (±0,3 s) + conferência na onda (início/fim onde a energia passa de
    pico − 40 dB, só nas bordas de fala). Fala rápida demais pro alinhador = fica o tempo do próprio Whisper nesse trecho."""
    import torch
    from torchaudio.pipelines import MMS_FA as b
    mdl = _mms(dispositivo); tok = b.get_tokenizer(); aln = b.get_aligner()
    HOP = 16; n = len(x16) // HOP
    env = 10 * np.log10(np.mean(x16[:n * HOP].reshape(n, HOP) ** 2, axis=1) + 1e-12) if n else np.zeros(1)
    ws = []
    for s in segmentos:
        a, bb = max(0, s["ini"] - 0.3), s["fim"] + 0.3
        orig = [w["p"] for w in s.get("palavras", [])] or s["txt"].split()
        lw = _limpa(" ".join(orig))
        if not lw: continue
        wav = torch.from_numpy(x16[int(a * 16000):int(bb * 16000)])[None].to(dispositivo)
        try:
            with torch.inference_mode():
                em, _ = mdl(wav); sp = aln(em[0], tok(lw))
        except RuntimeError:
            ws += [{"p": w["p"], "ini": w["ini"], "fim": w["fim"], "como": "whisper"} for w in s.get("palavras", [])]; continue
        r = wav.shape[1] / em.shape[1] / 16000
        for w, o, x in zip(lw, orig if len(orig) == len(lw) else lw, sp):
            ws.append({"p": o, "ini": a + x[0].start * r, "fim": a + x[-1].end * r, "como": "mms"})
    for i, w in enumerate(ws):
        pk = float(env[int(w["ini"] * 1000):max(int(w["ini"] * 1000) + 1, int(w["fim"] * 1000))].max()) if n else -60
        if i == 0 or w["ini"] - ws[i - 1]["fim"] > 0.12:
            k = int(w["ini"] * 1000); j = env[max(0, k - 150):k + 150]; ix = np.where(j > pk - 40)[0]
            if len(ix): w["ini"] = (max(0, k - 150) + ix[0]) / 1000
        if i == len(ws) - 1 or ws[i + 1]["ini"] - w["fim"] > 0.12:
            k = int(w["fim"] * 1000); j = env[max(0, k - 150):k + 150]; ix = np.where(j > pk - 40)[0]
            if len(ix): w["fim"] = (max(0, k - 150) + ix[-1] + 1) / 1000
    del mdl; base.liberar_torch()
    return [{"p": w["p"], "ini": round(w["ini"], 3), "fim": round(w["fim"], 3), "como": w["como"]} for w in ws]


def rodar(A, ctx):
    from . import separacao
    voz = separacao.stem(A, "voz")
    if not voz:
        return {"sem_som": True, "segmentos": [], "palavras": []}
    dev = "cuda" if ctx.placa else "cpu"
    x16 = base.ler_audio(voz, 16000)
    t = transcrever(x16, ctx.idioma, dev, palavras=True)
    if not base.SEGURAR:                       # no lote o Whisper fica pro próximo vídeo (o lote solta no fim da peça)
        soltar()
    pal = alinhar(x16, t["segmentos"], dev)
    segs = [{k: v for k, v in s.items() if k != "palavras"} for s in t["segmentos"]]
    return {"sem_som": False, "idioma": t["idioma"], "modelo": t["modelo"], "segmentos": segs, "palavras": pal, "descartados": t["descartados"],
            "nota": "tempos do arquivo (sem descontar a folga do AAC: ver preparo.folga_aac_s)"}
