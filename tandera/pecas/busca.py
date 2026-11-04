# -*- coding: utf-8 -*-
"""BUSCA no diário: frase → momento. Os pedaços do diário (resumo, cada linha do tempo com o que se vê e se ouve, falas de ouro, reações,
momentos aproveitáveis) viram documentos com tempo; a busca junta PALAVRA (BM25: nome, marca, gíria escrita igual) e SENTIDO
(Qwen3-Embedding-8B, o melhor aberto no MTEB-BR) por RRF — a pré-busca que venceu no servidor (95,4% top50).
Na 5070 o 8B vai em 4 bits (nf4; em bf16 são 16 GB e não cabem). `buscar(A, "frase")` devolve os momentos."""
import os, re, unicodedata

import numpy as np

from .. import base

REPO = "Qwen/Qwen3-Embedding-8B"
INSTRUCAO = "Instruct: Given a search request for a moment in a video, retrieve the diary passage that describes it\nQuery: "
_m = {}


def _seg(t):
    if t is None: return None
    m = re.match(r"^\s*(\d+):(\d+(?:\.\d+)?)", str(t))
    return int(m.group(1)) * 60 + float(m.group(2)) if m else None


def _itens(v):
    """os itens de um campo do diário como dicts: o modelo às vezes devolve lista DENTRO de lista (04/11, EP02: falas_de_ouro = [[{…}]])
    ou texto solto no lugar do objeto — achata e embrulha, em vez de quebrar a peça inteira"""
    if isinstance(v, dict):
        yield v
    elif isinstance(v, (list, tuple)):
        for x in v:
            yield from _itens(x)
    elif v not in (None, ""):
        yield {"texto": str(v)}


def documentos(d):
    docs = []
    add = lambda tipo, txt, de=None, ate=None: docs.append({"tipo": tipo, "texto": txt.strip(), "de": de, "ate": ate}) if txt and txt.strip() else None  # noqa: E731
    add("resumo", str(d.get("resumo") or ""))
    for x in _itens(d.get("linha_do_tempo")):
        add("linha do tempo", f"{x.get('ve', x.get('texto', ''))} · som: {x.get('ouve', '')}", _seg(x.get("de")), _seg(x.get("ate")))
    for x in _itens(d.get("falas_de_ouro")):
        add("fala de ouro", f"«{x.get('fala', x.get('texto', ''))}» ({x.get('por_que', '')})", _seg(x.get("t")))
    for x in _itens(d.get("reacoes")):
        add("reação", f"{x.get('quem', '')}: {x.get('expressao', x.get('texto', ''))}", _seg(x.get("t")))
    for x in _itens(d.get("momentos_aproveitaveis")):
        add("momento", f"{x.get('tipo', '')}: {x.get('por_que', x.get('texto', ''))}", _seg(x.get("de")), _seg(x.get("ate")))
    for x in d.get("escrito_e_marcas") or []:
        add("escrito", str(x))
    if d.get("etiquetas"): add("etiquetas", ", ".join(map(str, d["etiquetas"])))
    return docs


def _norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    return [w for w in re.findall(r"[a-z0-9']+", "".join(c for c in s if not unicodedata.combining(c))) if len(w) > 1]


def modelo(dev="cuda"):
    if "m" not in _m:
        import torch
        from transformers import AutoModel, AutoTokenizer, BitsAndBytesConfig
        tok = AutoTokenizer.from_pretrained(REPO, padding_side="left")
        if dev == "cuda":
            q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16)
            m = AutoModel.from_pretrained(REPO, quantization_config=q, device_map={"": 0}, torch_dtype=torch.bfloat16).eval()
        else:
            m = AutoModel.from_pretrained(REPO, torch_dtype=torch.bfloat16).eval()
        _m["m"] = (tok, m, dev)
    return _m["m"]


def soltar():
    _m.clear(); base.liberar_torch()


def vetores(textos, dev="cuda", lote=8):
    import torch
    tok, m, dev = modelo(dev)
    out = []
    for i in range(0, len(textos), lote):
        x = tok(textos[i:i + lote], padding=True, truncation=True, max_length=4096, return_tensors="pt").to(dev)
        with torch.no_grad():
            h = m(**x).last_hidden_state[:, -1]                    # último token (padding à esquerda)
        out.append(torch.nn.functional.normalize(h.float(), dim=-1).cpu().numpy())
    return np.concatenate(out) if out else np.zeros((0, 4096), np.float32)


def rodar(A, ctx):
    d = (A.get("diario") or {}).get("diario")
    if not d: return {"documentos": [], "obs": "sem diário"}
    docs = documentos(d)
    D = vetores([x["texto"] for x in docs], "cuda" if ctx.placa else "cpu")
    np.savez_compressed(os.path.join(A.dir("busca"), "vetores.npz"), D=D.astype(np.float16))
    soltar()
    return {"documentos": docs, "arquivo": "pecas/busca/vetores.npz", "modelo": REPO + (" nf4" if ctx.placa else " bf16")}


def buscar(A, frase, n=10, dev="cuda"):
    """frase → [{texto, de, ate, tipo, nota}] (BM25 + Qwen3-Embedding por RRF). Carrega o modelo (4 bits) na 1ª chamada."""
    from rank_bm25 import BM25Okapi
    docs = A["busca"]["documentos"]
    if not docs: return []
    D = np.load(os.path.join(A.pasta, "pecas", "busca", "vetores.npz"))["D"].astype(np.float32)
    bm = BM25Okapi([_norm(x["texto"]) for x in docs])
    r1 = list(np.argsort(-bm.get_scores(_norm(frase))))
    q = vetores([INSTRUCAO + frase], dev)[0]
    r2 = list(np.argsort(-(D @ q)))
    s = {}
    for lista in (r1, r2):
        for p, i in enumerate(lista): s[i] = s.get(i, 0) + 1 / (60 + p)
    return [dict(docs[i], nota=round(s[i], 4)) for i in sorted(s, key=lambda i: -s[i])[:n]]
