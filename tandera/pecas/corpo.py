# -*- coding: utf-8 -*-
"""CORPO. Duas medidas:
  - peça «corpo» (por plano): Sapiens2-1B (308 pontos, fp16, teto de ~5,5 GB) + DETR acham a pessoa maior; a articulação que mais mexe
    vira o sinal da repetição (reps, faixa em graus, como entra e sai do plano). Medido num vídeo de teste (régua: punhos 62/41).
  - ferramenta «pisada» = `esqueletos()`: o esqueleto quadro a quadro no formato de 33 pontos do MediaPipe, pro /sonoplastia pisadas.py.
    MediaPipe Pose heavy (CPU) é o padrão (F2, 01/11: 4/4 pisadas conferidas × RTMW-x 0/4); rtmw e sapiens ficam como opção medida."""
import os, sys

import numpy as np

from .. import base

SAP_REPO = os.path.join(base.REGUA, "repos", "sapiens2")
SAP_CK = os.path.join(base.REGUA, "modelos", "sapiens2")
SAP2COCO = [0, 1, 2, 3, 4, 5, 6, 7, 8, 62, 41, 9, 10, 11, 12, 13, 14]
ARTIC = {"cotovelo esq.": (5, 7, 9), "cotovelo dir.": (6, 8, 10), "joelho esq.": (11, 13, 15), "joelho dir.": (12, 14, 16),
         "quadril esq.": (5, 11, 13), "quadril dir.": (6, 12, 14)}
DE_COCO_WB = {0: 0, 2: 1, 5: 2, 7: 3, 8: 4, 11: 5, 12: 6, 13: 7, 14: 8, 15: 9, 16: 10, 23: 11, 24: 12, 25: 13, 26: 14, 27: 15, 28: 16,
              29: 19, 30: 22, 31: 17, 32: 20}
DE_SAPIENS = {0: 0, 2: 1, 5: 2, 7: 3, 8: 4, 11: 5, 12: 6, 13: 7, 14: 8, 15: 62, 16: 41, 23: 9, 24: 10, 25: 11, 26: 12, 27: 13, 28: 14,
              29: 17, 30: 20, 31: 15, 32: 18}
ESCALA_SCORE = {"rtmw": 8.0, "sapiens": 1.0}
_modelos = {}


def _sapiens(dev="cuda"):
    if "sapiens" not in _modelos:
        import torch
        if dev == "cuda":   # o Whisper do ditado mora na placa: teto por processo (estoura = erro, não invade)
            torch.cuda.set_per_process_memory_fraction(min(1.0, 5.5 * 1024 ** 3 / torch.cuda.get_device_properties(0).total_memory))
        sys.path.insert(0, SAP_REPO)
        from sapiens.pose.models import init_model
        from sapiens.pose.datasets import UDPHeatmap
        from transformers import DetrForObjectDetection, DetrImageProcessor
        cfg = os.path.join(SAP_REPO, "sapiens", "pose", "configs", "keypoints308", "shutterstock_goliath_3po",
                           "sapiens2_1b_keypoints308_shutterstock_goliath_3po-1024x768.py")
        m = init_model(cfg, os.path.join(SAP_CK, "pose", "sapiens2_1b_pose.safetensors"), device="cpu")
        m = (m.half() if dev == "cuda" else m).to(dev).eval()
        _c = dict(m.cfg.codec); _c.pop("type"); m.codec = UDPHeatmap(**_c)
        dp = DetrImageProcessor.from_pretrained(os.path.join(SAP_CK, "detector", "detr-resnet-101-dc5"))
        dm = DetrForObjectDetection.from_pretrained(os.path.join(SAP_CK, "detector", "detr-resnet-101-dc5")).eval().to(dev)
        _modelos["sapiens"] = (m, dp, dm, dev)
    return _modelos["sapiens"]


def soltar():
    _modelos.clear(); base.liberar_torch()
    try:
        import torch
        torch.cuda.set_per_process_memory_fraction(1.0)
    except Exception:
        pass


def _sapiens_poses(fr_bgr, max_pessoas=1):
    """[(kp (308,2), sc (308,))] das maiores pessoas no quadro"""
    import torch, cv2
    from PIL import Image
    m, dp, dm, dev = _sapiens()
    rgb = cv2.cvtColor(fr_bgr, cv2.COLOR_BGR2RGB)
    with torch.no_grad():
        o = dm(**dp(images=Image.fromarray(rgb), return_tensors="pt").to(dev))
    res = dp.post_process_object_detection(o, target_sizes=torch.tensor([rgb.shape[:2]], device=dev), threshold=0.5)[0]
    bx = res["boxes"][res["labels"] == 1].cpu().numpy()
    out = []
    for bb in sorted(bx, key=lambda b: -(b[2] - b[0]) * (b[3] - b[1]))[:max_pessoas]:
        d = m.data_preprocessor(m.pipeline(dict(img=fr_bgr, bbox=bb[None], bbox_score=np.ones(1, np.float32))))
        x = d["inputs"].unsqueeze(0) if d["inputs"].dim() == 3 else d["inputs"]
        with torch.no_grad():
            pr = m(x.to(dev).half() if dev == "cuda" else x.to(dev))
        kp, sc = m.codec.decode(pr[0].float().cpu().numpy())
        meta = d["data_samples"]["meta"]
        kp = kp / meta["input_size"] * meta["bbox_scale"] + meta["bbox_center"] - 0.5 * meta["bbox_scale"]
        out.append((kp[0], sc[0]))
    return out


def _angulo(k, a, b, c):
    v1, v2 = k[:, a] - k[:, b], k[:, c] - k[:, b]
    return np.degrees(np.arccos(np.clip((v1 * v2).sum(1) / (np.linalg.norm(v1, axis=1) * np.linalg.norm(v2, axis=1) + 1e-9), -1, 1)))


def corpo(video, planos, fps, larg, alt, placa=True, passo=2):
    import cv2
    from scipy.signal import find_peaks
    W = min(720, larg); out = []
    dev = "cuda" if placa else "cpu"
    _sapiens(dev)
    for a, b in planos:
        Q = base.ler_quadros(video, a, b, fps, larg, alt, W)
        qs = list(range(0, len(Q), passo))
        if len(Q) and qs and qs[-1] != len(Q) - 1: qs.append(len(Q) - 1)
        k = np.zeros((len(qs), 17, 2)); s = np.zeros((len(qs), 17))
        for j, i in enumerate(qs):
            ps = _sapiens_poses(cv2.cvtColor(Q[i], cv2.COLOR_RGB2BGR))
            if ps: k[j], s[j] = ps[0][0][SAP2COCO], ps[0][1][SAP2COCO]
        com = s.sum(1) > 0
        r = {"de_q": a, "ate_q": b, "quadros_medidos": len(qs), "com_pessoa": int(com.sum())}
        if com.sum() >= 3:
            ang = {n: _angulo(k, *ix) for n, ix in ARTIC.items()}
            conf = {n: float(s[com][:, list(ix)].mean()) for n, ix in ARTIC.items()}
            boas = [n for n in ang if conf[n] > 0.3] or list(ang)
            n = max(boas, key=lambda n: float(np.ptp(ang[n][com])))
            g = ang[n].copy()
            if (~com).any(): g[~com] = np.interp(np.where(~com)[0], np.where(com)[0], g[com])
            tq = np.array([a + i for i in qs]); vel = np.gradient(g, tq / fps) if len(g) > 1 else np.zeros_like(g)

            def fase(i):
                v = vel[i]; x = g[i]
                return {"angulo": round(float(x), 1), "vel_graus_s": round(float(v), 1),
                        "movimento": "dobrando" if v < -25 else ("esticando" if v > 25 else "parado"),
                        "ponto": "dobrado ao máximo" if x < 70 else ("esticado" if x > 150 else "no meio")}
            pk, _ = find_peaks(-g, prominence=35, distance=max(1, int(fps * 0.8 / passo)))
            lo, hi = float(g.min()), float(g.max())
            r.update({"articulacao": n, "faixa_graus": [round(lo, 1), round(hi, 1)], "reps_contadas": int(len(pk)), "entrada": fase(0),
                      "saida": fase(len(g) - 1), "termina_num_extremo": bool(hi - lo > 30 and min(abs(g[-1] - lo), abs(g[-1] - hi)) < 0.15 * (hi - lo)),
                      "curva": [[int(t), round(float(x), 1)] for t, x in zip(tq, g)]})
        out.append(r)
    soltar()
    return out


def rodar(A, ctx):
    c, p = A["cortes"], A["preparo"]
    if not p["tem_imagem"]: return {"planos": []}
    return {"planos": corpo(A.video, c["planos"], c["fps"], p["largura"], p["altura"], ctx.placa)}


# ------------------------------------------------------------------ ferramenta «pisada»: esqueleto quadro a quadro (33 pontos)
def _para_mp33(kp, sc, mapa, escala):
    p = np.full((33, 4), np.nan, np.float32); p[:, 2:] = 0.0
    for i, j in mapa.items():
        p[i, :2] = kp[j]; p[i, 2] = p[i, 3] = float(np.clip(sc[j] / escala, 0, 1))
    return p


def esqueletos(quadros, fps, q0, max_pessoas=1, detector="mediapipe"):
    """quadros = lista de BGR. Devolve [[pose (33,4): x, y (px), visibilidade, presença], ...] por quadro.
    detector: mediapipe (padrão, CPU) · rtmw (RTMW-x, CPU) · sapiens (Sapiens2-1B, placa)"""
    import cv2
    if detector == "rtmw":
        from rtmlib import Wholebody
        if "rtmw" not in _modelos: _modelos["rtmw"] = Wholebody(mode="performance", backend="onnxruntime", device="cpu")
        out = []
        for fr in quadros:
            kp, sc = _modelos["rtmw"](fr)
            poses = [_para_mp33(kp[i], sc[i], DE_COCO_WB, ESCALA_SCORE["rtmw"]) for i in range(len(kp))]
            poses.sort(key=lambda p: -float(np.nanmax(p[:, 1]) - np.nanmin(p[:, 1])) if np.isfinite(p[:, 1]).any() else 0)
            out.append(poses[:max_pessoas])
        return out
    if detector == "sapiens":
        if os.environ.get("CUDA_VISIBLE_DEVICES", None) in ("", "-1"):
            raise SystemExit("Sapiens2 só com a placa (avisar no Medidor antes)")
        return [[_para_mp33(kp, sc, DE_SAPIENS, ESCALA_SCORE["sapiens"]) for kp, sc in _sapiens_poses(fr, max_pessoas)] for fr in quadros]
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision
    op = vision.PoseLandmarkerOptions(base_options=BaseOptions(model_asset_path=base.POSE_HEAVY, delegate=BaseOptions.Delegate.CPU),
                                      running_mode=vision.RunningMode.VIDEO, num_poses=max_pessoas,
                                      min_pose_detection_confidence=0.4, min_pose_presence_confidence=0.4, min_tracking_confidence=0.4)
    out = []
    with vision.PoseLandmarker.create_from_options(op) as lm:
        for k, fr in enumerate(quadros):
            h, w = fr.shape[:2]
            r = lm.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)), int(round((q0 + k) * 1000 / fps)))
            out.append([np.array([[p.x * w, p.y * h, p.visibility, p.presence] for p in pl], np.float32) for pl in (r.pose_landmarks or [])])
    return out
