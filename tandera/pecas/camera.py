# -*- coding: utf-8 -*-
"""CÂMERA por plano: CoTracker3 (offline, scaled) segue uma grade de pontos e a geometria (afim parcial, RANSAC) dá a CURVA — quanto a
cena anda em x/y e quanto cresce (escala) quadro a quadro. A classe sai por limiar fixo (77% no CameraBench; pan vira zoom às vezes):
quem decide é a curva. Poucos pontos seguidos (< 60%: explosão, fogo) = pouca confiança, conferir no olho."""
import os

import numpy as np

from .. import base

REPO = os.path.join(base.REGUA, "repos", "co-tracker")
PESO = os.path.join(base.REGUA, "modelos", "cotracker3", "scaled_offline.pth")


def _classe(dx, dy, ls, lim_t=0.06, lim_s=0.04):
    if max(abs(dx), abs(dy)) < lim_t and abs(ls) < lim_s: return "parada"
    if abs(ls) * 1.5 > max(abs(dx), abs(dy)): return "entrando (zoom/travelling pra frente)" if ls > 0 else "saindo (zoom/travelling pra trás)"
    if abs(dx) >= abs(dy): return "pan esquerda" if dx > 0 else "pan direita"
    return "tilt cima" if dy > 0 else "tilt baixo"


def deterministico():
    """o mesmo resultado em qualquer processo (a TransNetV2 liga isso pro processo inteiro; aqui fica explícito)"""
    import random, torch
    torch.manual_seed(42); np.random.seed(42); random.seed(42)
    try: torch.use_deterministic_algorithms(True, warn_only=True)
    except Exception: pass
    if torch.backends.cudnn.is_available():
        torch.backends.cudnn.deterministic = True; torch.backends.cudnn.benchmark = False


def camera(video, planos, fps, larg, alt, placa=True, n_max=48):
    import torch, cv2
    dev = "cuda" if placa else "cpu"
    ct = None; out = []
    for a, b in planos:
        if b - a < 4:
            out.append({"de_q": a, "ate_q": b, "classe": "curto demais (< 4 quadros)", "curva": []}); continue
        # 01/11: o LADO MAIOR em 512 (antes a largura: vídeo em pé virava 512×910 e o CoTracker3 foi a 11,1 GB no V009, acima do
        # teto de ~10 GB da placa; a curva é medida em fração da largura/altura, então a classe não depende do tamanho)
        Q = base.ler_quadros(video, a, b, fps, larg, alt, 512 if larg >= alt else max(2, int(round(512 * larg / alt / 2)) * 2))
        if len(Q) < 4:
            out.append({"de_q": a, "ate_q": b, "classe": "?", "curva": []}); continue
        if ct is None:
            deterministico()
            ct = torch.hub.load(REPO, "cotracker3_offline", source="local", pretrained=False)
            (ct.model if hasattr(ct, "model") else ct).load_state_dict(torch.load(PESO, map_location="cpu"))
            ct = ct.to(dev).eval()
        idx = np.unique(np.linspace(0, len(Q) - 1, min(n_max, len(Q))).round().astype(int))
        fs = Q[idx]; h, w = fs.shape[1:3]
        v = torch.from_numpy(np.ascontiguousarray(fs)).permute(0, 3, 1, 2)[None].float().to(dev)
        # 01/11: autocast fp16 na placa — em fp32 a placa ia a 11,1 GB no total (acima do teto); em fp16 8,9 GB, 58/58 classes iguais e
        # a mesma curva (diferença mediana 0) no V009, e 40% mais rápido (camera_teto.json)
        with torch.no_grad(), torch.autocast("cuda", dtype=torch.float16, enabled=(dev == "cuda")):
            tr, vis = ct(v, grid_size=24)
        tr, vis = tr.float(), vis.float()
        tr, vis = tr[0].cpu().numpy(), vis[0].cpu().numpy()
        dx = dy = ls = 0.0
        curva = [{"q": int(a + idx[0]), "dx": 0.0, "dy": 0.0, "escala": 0.0}]; vel = []
        for i in range(1, len(fs)):
            m = (vis[i] > 0.5) & (vis[i - 1] > 0.5); M = None
            if m.sum() >= 8:
                M, _ = cv2.estimateAffinePartial2D(tr[i - 1][m], tr[i][m], method=cv2.RANSAC, ransacReprojThreshold=2.0)
            if M is not None:
                ddx, ddy = M[0, 2] / w, M[1, 2] / h; dls = float(np.log(np.sqrt(abs(np.linalg.det(M[:, :2])))))
                dx += ddx; dy += ddy; ls += dls
                vel.append((int(a + idx[i]), float(np.hypot(ddx, ddy) + abs(dls)) / max(1, idx[i] - idx[i - 1])))
            curva.append({"q": int(a + idx[i]), "dx": round(dx, 4), "dy": round(dy, 4), "escala": round(ls, 4)})
        pico = max(vel, key=lambda x: x[1]) if vel else (None, 0)
        vis_pct = round(100 * float((vis > 0.5).mean()), 0)
        cl = _classe(dx, dy, ls)
        if vis_pct < 60: cl += f" (pouca confiança: só {vis_pct:.0f}% dos pontos seguidos — conferir no olho)"
        out.append({"de_q": a, "ate_q": b, "classe": cl, "dx": round(dx, 3), "dy": round(dy, 3), "log_escala": round(ls, 3),
                    "pontos_seguidos_pct": vis_pct, "pico_de_velocidade_q": pico[0], "curva": curva})
    del ct; base.liberar_torch()
    return out


def rodar(A, ctx):
    c, p = A["cortes"], A["preparo"]
    if not p["tem_imagem"]: return {"planos": []}
    return {"planos": camera(A.video, c["planos"], c["fps"], p["largura"], p["altura"], ctx.placa)}
