# -*- coding: utf-8 -*-
"""TEXTO NA TELA na placa (PaddleOCR 3.7, paddlepaddle-gpu) — roda no ambiente SEPARADO .venv-ocr (as bibliotecas da NVIDIA do paddle
são de outra versão que as do torch: separado, um não quebra o outro). Igual ao ocr_placa.py do servidor do catálogo (01/11).
Conversa por linhas de JSON:
  entra:  {"quadros": [[k, "caminho.jpg"], ...]}
  sai:    {"out": [[k, [[texto, nota], ...]], ...], "onde": "gpu:0"}   (ou {"erro": "..."})
Filtro igual ao do servidor: nota >= 0,6 e 2+ letras."""
import json, os, sys

os.environ.setdefault("FLAGS_allocator_strategy", "auto_growth")
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
from paddleocr import PaddleOCR  # noqa: E402

dev = sys.argv[1] if len(sys.argv) > 1 else "gpu:0"
ocr = PaddleOCR(lang="pt", use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=True, device=dev,
                **({} if dev.startswith("gpu") else {"enable_mkldnn": False}))
print(json.dumps({"pronto": True, "onde": dev}), flush=True)
for linha in sys.stdin:
    if not linha.strip(): continue
    p = json.loads(linha)
    try:
        out = []
        for k, q in p["quadros"]:
            res = ocr.predict(q)
            txt = [[t, round(float(s), 3)] for o in res for t, s in zip(o["rec_texts"], o["rec_scores"]) if s >= 0.6 and len(t.strip()) >= 2]
            if txt: out.append([k, txt])
        print(json.dumps({"out": out, "onde": dev}, ensure_ascii=False), flush=True)
    except Exception as e:
        print(json.dumps({"erro": f"{type(e).__name__}: {str(e)[:300]}"}, ensure_ascii=False), flush=True)
