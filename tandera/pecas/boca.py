# -*- coding: utf-8 -*-
"""BOCA × FALA por plano: os 98 pontos do OpenFace 3.0 (no WSL Ubuntu-24.04; AUC 0,88 na boca) a cada 2 quadros; quanto tempo tem rosto
e se a boca mexe JUNTO com a fala medida. Boca mexendo sem fala, ou fala sem boca = conferir no olho (outra pessoa? off?)."""
import json, os, subprocess

import numpy as np

from .. import base

LOTE = 150


def _wsl(p):
    p = os.path.abspath(p).replace("\\", "/"); return "/mnt/" + p[0].lower() + p[2:]


def rodar(A, ctx):
    import cv2
    c, p = A["cortes"], A["preparo"]
    if not p["tem_imagem"]: return {"planos": []}
    fps = c["fps"]; pasta = A.dir("boca"); passo = 2; quadros = []
    for a, b in c["planos"]:
        Q = base.ler_quadros(A.video, a, b, fps, p["largura"], p["altura"], min(640, p["largura"]))
        for i in range(0, len(Q), passo):
            dst = os.path.join(pasta, f"r{a + i}.jpg")
            if not os.path.exists(dst): base.gravar_jpg(dst, cv2.cvtColor(Q[i], cv2.COLOR_RGB2BGR))
            quadros.append((a + i, dst))
    sh = _wsl(os.path.join(os.path.dirname(__file__), "_boca_openface.sh")); medida = {}
    for k in range(0, len(quadros), LOTE):
        lote = quadros[k:k + LOTE]
        lista, sai = os.path.join(pasta, f"lista_{k // LOTE:03d}.json"), os.path.join(pasta, f"saida_{k // LOTE:03d}.json")
        if os.name == "nt":
            json.dump([_wsl(d) for _, d in lote], open(lista, "w"))
            subprocess.run(["wsl", "-d", "Ubuntu-24.04", "-u", "root", "--", "bash", "-c",
                            f"tr -d '\\r' < {sh} > /tmp/tandera_boca.sh && bash /tmp/tandera_boca.sh {_wsl(lista)} {_wsl(sai)} "
                        f"{_wsl(os.path.dirname(__file__))} {_wsl(os.path.join(base.REGUA, 'modelos', 'openface3'))}"], check=True,
                           capture_output=True, creationflags=base.SEM_JANELA)
            res = json.load(open(sai)); medida.update({q: res.get(_wsl(d), {}) for q, d in lote})
        else:   # 06/11: no servidor (Linux) o MESMO OpenFace 3.0 roda direto, sem WSL, com os mesmos pesos (REGUA/modelos/openface3)
            json.dump([d for _, d in lote], open(lista, "w"))
            ofw = "/tmp/ofw"; os.makedirs(ofw, exist_ok=True)
            if not os.path.lexists(os.path.join(ofw, "weights")):
                os.symlink(os.path.join(base.REGUA, "modelos", "openface3"), os.path.join(ofw, "weights"))
            subprocess.run([base.PY_REGUA, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_boca_openface_wsl.py"), lista, sai,
                            os.path.join(ofw, "weights")], check=True, capture_output=True, cwd=ofw)
            res = json.load(open(sai)); medida.update({q: res.get(d, {}) for q, d in lote})
    folga = p.get("folga_aac_s", 0.0)
    fala_t = [(w["ini"] - folga, w["fim"] - folga) for w in (A.get("fala") or {}).get("palavras", [])]
    falando = lambda t: any(a <= t <= b for a, b in fala_t)                       # noqa: E731
    out = []
    for a, b in c["planos"]:
        qs = list(range(a, b, passo)); boca = np.array([medida.get(q, {}).get("boca", np.nan) for q in qs], float); tem = ~np.isnan(boca)
        r = {"de_q": a, "ate_q": b, "rosto_pct": round(100 * float(tem.mean()), 0) if len(qs) else 0}
        if tem.sum() >= 4:
            mov = np.abs(np.diff(np.where(tem, boca, np.nanmedian(boca)), prepend=np.nanmedian(boca)))
            k = max(1, int(round(0.25 * fps / passo))); mov = np.convolve(mov, np.ones(k) / k, "same")
            fl = np.array([falando(q / fps) for q in qs])
            r["fala_pct"] = round(100 * float(fl.mean()), 0); r["boca_aberta_media"] = round(float(np.nanmean(boca)), 3)
            if (fl & tem).any() and (~fl & tem).any():
                r["boca_mexe_na_fala_x_fora"] = round(float(mov[fl & tem].mean() / (mov[~fl & tem].mean() + 1e-6)), 2)
            alto = float(np.nanpercentile(mov, 75))
            r["boca_mexe_sem_fala"] = bool(((mov > alto) & ~fl & tem).mean() > 0.25)
            r["fala_sem_boca"] = bool(fl.mean() > 0.3 and float(mov[fl & tem].mean() if (fl & tem).any() else 0) < float(np.nanmedian(mov)))
        out.append(r)
    for f in os.listdir(pasta):
        if f.startswith("r") and f.endswith(".jpg"): os.remove(os.path.join(pasta, f))
    return {"planos": out}
