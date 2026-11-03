# -*- coding: utf-8 -*-
"""EFEITO EM QUALQUER VÍDEO (sem projeto) — mesmo motor do sfx_detectar (encaixe na onda contra a biblioteca inteira, 8 kHz,
na placa, coerência no tempo), mas sem gabarito: só diz O QUE achou e ONDE.
Uso: python sfx_video.py <stem.wav> <saida.json> [folga_aac_s]
  env REGUA_BIB (pasta com lista.txt + bib8k.npy + bib8k_ini.npy; padrão testes\\biblioteca), REGUA_PASSO (padrão 0.25)
Sai: cada achado = arquivo, início do ARQUIVO no relógio do vídeo (s), trecho do vídeo onde ele toca, nota, janelas."""
import json, os, sys, time
import numpy as np, soundfile as sf, librosa, torch
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAV, OUT = sys.argv[1], sys.argv[2]
AAC = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
SR, JAN, PASSO = 8000, 1.0, float(os.environ.get("REGUA_PASSO", "0.25"))
DB = os.environ.get("REGUA_BIB") or os.path.join(BASE, "testes", "biblioteca")
lista = open(os.path.join(DB, "lista.txt"), encoding="utf-8").read().splitlines()
bib = torch.from_numpy(np.load(os.path.join(DB, "bib8k.npy")).astype(np.float32))
ini = np.load(os.path.join(DB, "bib8k_ini.npy"))
q, sr0 = sf.read(WAV, dtype="float32", always_2d=True)
q8 = librosa.resample(q.mean(1), orig_sr=sr0, target_sr=SR).astype(np.float32)
L = int(JAN * SR)
t0s, Qs = [], []
for k in range(int((len(q8) / SR - JAN) / PASSO) + 1):
    t0 = k * PASSO; a = q8[int(t0 * SR): int(t0 * SR) + L].copy()
    if len(a) < L or np.sqrt((a ** 2).mean()) < 0.002: continue
    a -= a.mean(); a /= (np.linalg.norm(a) + 1e-9); t0s.append(t0); Qs.append(a)
print("janelas:", len(Qs), flush=True)
dev = os.environ.get("REGUA_DISP", "cuda"); BLOCO = min(1 << 25, len(bib)); NF = 1 << int(np.ceil(np.log2(BLOCO + 2 * L))); LOTE = 3; PISO = 0.003 * L ** 0.5; TOPK = 40
Q = torch.flip(torch.from_numpy(np.stack(Qs)), [1]).to(dev)
cand = [dict() for _ in Qs]
t = time.time()
for b0 in range(0, len(bib), BLOCO):
    seg = bib[b0: b0 + BLOCO + L].to(dev); n = len(seg)
    if n < L: break
    Sf = torch.fft.rfft(seg, n=NF)
    e2 = torch.cumsum(torch.cat([torch.zeros(1, device=dev), seg ** 2]), 0)
    en = torch.sqrt((e2[L:] - e2[:-L]).clamp_min(1e-9)); ok = en >= PISO
    for k in range(0, len(Qs), LOTE):
        c = torch.fft.irfft(Sf[None] * torch.fft.rfft(Q[k:k + LOTE], n=NF), n=NF)[:, L - 1: n][:, : len(en)] / en[None]
        c = torch.where(ok[None], c.abs(), torch.zeros_like(c))
        tv, tp = c.topk(TOPK, dim=1); del c
        tv, tp = tv.cpu().numpy(), tp.cpu().numpy() + b0
        for j in range(tv.shape[0]):
            cd = cand[k + j]
            for v, pos in zip(tv[j], tp[j]):
                i = int(np.searchsorted(ini, pos, side="right") - 1)
                if v > cd.get(i, (0, 0))[0]: cd[i] = (float(v), int(pos))
    del Sf, e2, en, seg, ok
print("biblioteca varrida em %.0f s" % (time.time() - t), flush=True)
ach = []
for t0, cd in zip(t0s, cand):
    for i, (v, pos) in sorted(cd.items(), key=lambda x: -x[1][0])[:5]:
        ach.append((i, t0 - (pos - ini[i]) / SR - AAC, v, t0))
grupos = {}
for i, d, v, t0 in ach:
    if v < 0.3: continue
    g = grupos.setdefault((i, round(d / 0.0417)), {"i": i, "d": [], "v": [], "t": []}); g["d"].append(d); g["v"].append(v); g["t"].append(t0)
saida = []
for g in grupos.values():
    rep = max(g["t"]) - min(g["t"])
    if rep < 0.5 - 1e-6: continue
    saida.append({"arquivo": lista[g["i"]], "nome": os.path.splitext(os.path.basename(lista[g["i"]]))[0], "inicio_do_arquivo_s": round(float(np.median(g["d"])), 4),
                  "toca_de_s": min(g["t"]), "toca_ate_s": max(g["t"]) + JAN, "repete_s": rep, "nota": round(float(np.median(g["v"])), 3), "janelas": len(g["t"]),
                  "confiavel": rep >= 1.0 - 1e-6})
saida.sort(key=lambda x: x["toca_de_s"])
json.dump({"wav": WAV, "folga_aac_s": AAC, "passo": PASSO, "achados": saida}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for s in saida:
    print("%s %6.2f s (arquivo começa)  toca %5.2f–%5.2f  nota %.2f  %s" % ("*" if s["confiavel"] else " ", s["inicio_do_arquivo_s"], s["toca_de_s"], s["toca_ate_s"], s["nota"], s["nome"][:70]))
print("achados:", len(saida), "| confiáveis (repete >= 1 s):", sum(s["confiavel"] for s in saida))
