# -*- coding: utf-8 -*-
"""IMAGEM: o retrato SigLIP 2 (google/siglip2-so400m-patch14-384) de cada quadro 1/s do preparo, em lote na placa — imagem parecida e
busca por frase (o catálogo usa o mesmo). `frase(A, "a man on a motorcycle")` devolve os segundos mais parecidos."""
import os

import numpy as np

from .. import base

REPO = "google/siglip2-so400m-patch14-384"
_m = {}


def carregar(dev="cuda"):
    if dev not in _m:
        import torch
        from transformers import AutoModel, AutoProcessor
        _m.clear()
        _m[dev] = (AutoModel.from_pretrained(REPO, torch_dtype=torch.float16 if dev == "cuda" else torch.float32).to(dev).eval(), AutoProcessor.from_pretrained(REPO))
    return _m[dev]


def soltar():
    _m.clear(); base.liberar_torch()


def _v(f):
    import torch
    f = f if torch.is_tensor(f) else f.pooler_output
    return torch.nn.functional.normalize(f.float(), dim=-1).cpu().numpy()


def rodar(A, ctx):
    import torch
    from PIL import Image
    from . import preparo
    if not A["preparo"]["tem_imagem"]: return {"quadros": 0}
    dev = "cuda" if ctx.placa else "cpu"; m, p = carregar(dev)
    pasta = preparo.caminho(A, "q1"); qs = sorted(os.listdir(pasta)); out = []
    with torch.no_grad():
        for i in range(0, len(qs), 32):
            ims = [Image.open(os.path.join(pasta, f)).convert("RGB") for f in qs[i:i + 32]]
            x = p(images=ims, return_tensors="pt").to(dev)
            out.append(_v(m.get_image_features(pixel_values=x["pixel_values"].to(m.dtype))))
    E = np.concatenate(out) if out else np.zeros((0, 1152), np.float32)
    np.savez_compressed(os.path.join(A.dir("imagem"), "siglip2.npz"), vis=E.astype(np.float16), t_vis=np.array([int(f[:5]) - 0.5 for f in qs]))
    soltar()
    return {"quadros": len(qs), "arquivo": "pecas/imagem/siglip2.npz", "dim": int(E.shape[1]) if len(E) else 1152}


def frase(A, texto, n=5, dev="cuda"):
    import torch
    m, p = carregar(dev); d = np.load(os.path.join(A.pasta, "pecas", "imagem", "siglip2.npz"))
    with torch.no_grad():
        q = _v(m.get_text_features(**p(text=[texto], return_tensors="pt", padding="max_length", max_length=64).to(dev)))[0]
    s = d["vis"].astype(np.float32) @ q
    return [{"t": float(d["t_vis"][i]), "nota": round(float(s[i]), 3)} for i in np.argsort(-s)[:n]]
