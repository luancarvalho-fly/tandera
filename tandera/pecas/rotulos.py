# -*- coding: utf-8 -*-
"""RÓTULOS do som SEM a voz (o stem «resto» da separação), a cada 0,5 s em janelas de 1 s: as etiquetas AudioSet (527) do CED-Base
(mispeech/ced-base; no teste de 01/11 foi o melhor etiquetador: 75% × Dasheng 67% × YAMNet 55%; substitui o AST de agosto). Mesmo
formato que a ficha sonora lia: {t, db, musica (quanto parece trilha), rotulos [[nome, p], ...]} — pista, não instante exato."""
import numpy as np

from .. import base

GENERICOS = {"Music", "Musical instrument", "Electronic music", "Soundtrack music", "Ambient music", "Background music", "Orchestra",
             "Sound effect", "Inside, small room", "Inside, large room or hall", "Outside, urban or manmade", "Outside, rural or natural",
             "Silence", "Speech", "Narration, monologue", "Male speech, man speaking", "Female speech, woman speaking"}
MUSICA = {"Music", "Musical instrument", "Electronic music", "Soundtrack music", "Ambient music", "Background music", "Orchestra",
          "Synthesizer", "Drum", "Drum kit", "Piano", "Guitar", "Bass guitar", "Strings", "Theme music", "Video game music"}


def carregar(dev="cuda"):
    from transformers import AutoFeatureExtractor, AutoModelForAudioClassification
    return (AutoFeatureExtractor.from_pretrained(base.CED, trust_remote_code=True),
            AutoModelForAudioClassification.from_pretrained(base.CED, trust_remote_code=True).to(dev).eval())


def etiquetar_varios(wavs, dev="cuda"):
    """varios arquivos com o modelo carregado UMA vez (a trava de identidade da /sonoplastia, 01/11): {caminho: janelas}"""
    fe, m = carregar(dev)
    out = {w: etiquetar(base.ler_audio(w, 16000), dev, modelo=(fe, m), liberar=False) for w in wavs}
    del m; base.liberar_torch()
    return out


def etiquetar(x16, dev="cuda", passo=0.5, janela=1.0, lote=32, modelo=None, liberar=True):
    import torch
    fe, m = modelo or carregar(dev)
    rot = m.config.id2label; n = int(janela * 16000)
    ini = list(range(0, max(1, x16.size - n // 2), int(passo * 16000)))
    segs = [np.pad(x16[i:i + n], (0, max(0, n - x16[i:i + n].size))) for i in ini]
    out = []
    with torch.no_grad():
        for k in range(0, len(segs), lote):
            inp = fe(torch.tensor(np.stack(segs[k:k + lote])), sampling_rate=16000, return_tensors="pt")
            lg = m(**{a: b.to(dev) for a, b in inp.items()}).logits.float()
            pr = (torch.sigmoid(lg) if (lg.min() < 0 or lg.max() > 1) else lg).cpu().numpy()
            for j, p in enumerate(pr):
                i = ini[k + j]; seg = segs[k + j]
                top = np.argsort(p)[::-1][:12]
                out.append({"t": round(i / 16000 + janela / 2, 2), "db": round(float(20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9)), 1),
                            "musica": round(max((float(p[q]) for q in top if rot[int(q)] in MUSICA), default=0.0), 2),
                            "rotulos": [[rot[int(q)], round(float(p[q]), 3)] for q in top if rot[int(q)] not in GENERICOS and p[q] >= 0.06][:4]})
    if liberar:
        del m; base.liberar_torch()
    return out


def aquecer(ctx):
    dev = "cuda" if ctx.placa else "cpu"
    base.segurado(("ced", dev), lambda: carregar(dev))


def rodar(A, ctx):
    from . import separacao
    resto = separacao.stem(A, "resto")
    if not resto: return {"janelas": [], "sem_som": True}
    dev = "cuda" if ctx.placa else "cpu"
    modelo = base.segurado(("ced", dev), lambda: carregar(dev)) if base.SEGURAR else None     # o lote: o CED-Base carregado uma vez
    return {"modelo": "mispeech/ced-base", "passo": 0.5, "janela": 1.0,
            "janelas": etiquetar(base.ler_audio(resto, 16000), dev, modelo=modelo)}
