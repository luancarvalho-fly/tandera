# -*- coding: utf-8 -*-
"""SOM: o retrato CLAP (laion/larger_clap_general) do som original em janelas de 5 s a cada 2,5 s (igual ao catálogo), em lote de 16 na
placa. Serve pra «som parecido» (79% no teste de 01/11, o melhor dos 4) e busca por frase em INGLÊS (75% × 46% em português).
`frase(A, "a door slam")` devolve as janelas mais parecidas."""
import os

import numpy as np

from .. import base

REPO = "laion/larger_clap_general"
_m = {}


def carregar(dev="cuda"):
    if dev not in _m:
        from transformers import ClapModel, ClapProcessor
        _m.clear(); _m[dev] = (ClapModel.from_pretrained(REPO).to(dev).eval(), ClapProcessor.from_pretrained(REPO))
    return _m[dev]


def soltar():
    _m.clear(); base.liberar_torch()


def _vetor(f):
    import torch
    f = f if torch.is_tensor(f) else f.pooler_output
    return torch.nn.functional.normalize(f.float(), dim=-1).cpu().numpy()


def janelas(pcm48, jan=5.0, passo=2.5):
    js, ts, t = [], [], 0.0
    while (t + 1) * 48000 <= len(pcm48):
        seg = pcm48[int(t * 48000): int((t + jan) * 48000)]; js.append(seg); ts.append(t + min(jan, len(seg) / 48000) / 2); t += passo
    return js, ts


def retratos_audio(lista48, dev="cuda", lote=16):
    import torch
    m, p = carregar(dev); out = []
    with torch.no_grad():
        for i in range(0, len(lista48), lote):
            x = p(audio=lista48[i:i + lote], sampling_rate=48000, return_tensors="pt").to(dev)
            out.append(_vetor(m.get_audio_features(**x)))
    return np.concatenate(out) if out else np.zeros((0, 512), np.float32)


def retratos_texto(frases, dev="cuda"):
    import torch
    m, p = carregar(dev)
    with torch.no_grad():
        return _vetor(m.get_text_features(**p(text=frases, return_tensors="pt", padding=True).to(dev)))


def rodar(A, ctx):
    from . import preparo
    s = preparo.caminho(A, "som48k")
    if not s: return {"janelas": 0, "sem_som": True}
    dev = "cuda" if ctx.placa else "cpu"
    js, ts = janelas(base.ler_audio(s, 48000))
    aud = retratos_audio(js, dev)
    np.savez_compressed(os.path.join(A.dir("som"), "clap.npz"), aud=aud.astype(np.float16), t_aud=np.array(ts))
    soltar()
    return {"janelas": len(ts), "arquivo": "pecas/som/clap.npz", "dim": int(aud.shape[1]) if len(aud) else 512, "janela_s": 5.0, "passo_s": 2.5}


def frase(A, texto, n=5, dev="cuda"):
    d = np.load(os.path.join(A.pasta, "pecas", "som", "clap.npz"))
    q = retratos_texto([texto], dev)[0]; s = d["aud"].astype(np.float32) @ q
    return [{"t": round(float(d["t_aud"][i]), 2), "nota": round(float(s[i]), 3)} for i in np.argsort(-s)[:n]]
