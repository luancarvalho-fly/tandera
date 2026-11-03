# -*- coding: utf-8 -*-
"""ROSTOS nos quadros 1/s do preparo (lado menor 720: rosto pequeno some no 480p), as peças que venceram no servidor em 31/10:
  SCRFD 10G (det_10g do buffalo_l, +30% rostos que o YuNet) acha e dá os 5 pontos → alinha 112×112 →
  AdaFace IR-101 WebFace12M tira a digital (95% × 79% da combinação antiga) → EmotiEffLib enet_b0_8_best_vgaf (ONNX) lê a expressão.
O SCRFD aqui é o mesmo cálculo do insightface (âncoras, distância → caixa e pontos, NMS 0,4), sem o pacote (no Windows ele pede
compilador). Tudo na placa: onnxruntime-gpu 1.23.2 com arena kSameAsRequested (só a memória que pede) e AVISO se cair no processador.
Sai: por quadro, as caixas, o tamanho, a expressão; digitais em pecas\\rostos\\digitais.npz (+ recortes 160 px pra quem for nomear)."""
import os, sys

import numpy as np

from .. import base

SCRFD = os.path.join(base.MODELOS, "scrfd", "det_10g.onnx")
ADAFACE = os.path.join(base.MODELOS, "adaface", "adaface_ir101_webface12m.ckpt")
EMO = os.path.join(base.MODELOS, "emotiefflib", "enet_b0_8_best_vgaf.onnx")
EMOS = ["Anger", "Contempt", "Disgust", "Fear", "Happiness", "Neutral", "Sadness", "Surprise"]
ORT_CUDA = {"arena_extend_strategy": "kSameAsRequested"}
ARC = np.array([[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366], [41.5493, 92.3655], [70.7299, 92.2041]], np.float32)


def _sessao(arq, placa):
    return base.ort_sessao(arq, placa, ORT_CUDA)


class Scrfd:
    def __init__(self, placa=True, tam=640, limiar=0.5):
        self.s = _sessao(SCRFD, placa); self.tam = tam; self.lim = limiar; self.nome = self.s.get_inputs()[0].name; self._anc = {}

    def _ancoras(self, h, w, st):
        k = (h, w, st)
        if k not in self._anc:
            c = (np.stack(np.mgrid[:h, :w][::-1], axis=-1).astype(np.float32) * st).reshape(-1, 2)
            self._anc[k] = np.stack([c] * 2, axis=1).reshape(-1, 2)
        return self._anc[k]

    def detectar(self, im):
        """im BGR → (caixas [N,5: x0 y0 x1 y1 nota], pontos [N,5,2])"""
        import cv2
        h0, w0 = im.shape[:2]; T = self.tam
        if h0 / w0 > 1: nh, nw = T, int(T / (h0 / w0))
        else: nw, nh = T, int(T * (h0 / w0))
        esc = nh / h0
        det = np.zeros((T, T, 3), np.uint8); det[:nh, :nw] = cv2.resize(im, (nw, nh))
        blob = cv2.dnn.blobFromImage(det, 1.0 / 128, (T, T), (127.5, 127.5, 127.5), swapRB=True)
        o = self.s.run(None, {self.nome: blob})
        cx, kx, sx = [], [], []
        for i, st in enumerate((8, 16, 32)):
            sc, bb, kp = o[i].ravel(), o[i + 3] * st, o[i + 6] * st
            a = self._ancoras(T // st, T // st, st)
            ok = np.where(sc >= self.lim)[0]
            if not len(ok): continue
            b = np.stack([a[:, 0] - bb[:, 0], a[:, 1] - bb[:, 1], a[:, 0] + bb[:, 2], a[:, 1] + bb[:, 3]], -1)[ok]
            p = np.stack([a[:, i % 2] + kp[:, i] for i in range(10)], -1).reshape(-1, 5, 2)[ok]
            cx.append(b); kx.append(p); sx.append(sc[ok])
        if not cx: return np.zeros((0, 5), np.float32), np.zeros((0, 5, 2), np.float32)
        b = np.concatenate(cx) / esc; p = np.concatenate(kx) / esc; s = np.concatenate(sx)
        ordem = s.argsort()[::-1]; b, p, s = b[ordem], p[ordem], s[ordem]
        fica = []; x0, y0, x1, y1 = b.T; area = (x1 - x0 + 1) * (y1 - y0 + 1); idx = np.arange(len(s))
        while len(idx):
            i = idx[0]; fica.append(i)
            xx0 = np.maximum(x0[i], x0[idx[1:]]); yy0 = np.maximum(y0[i], y0[idx[1:]])
            xx1 = np.minimum(x1[i], x1[idx[1:]]); yy1 = np.minimum(y1[i], y1[idx[1:]])
            inter = np.maximum(0, xx1 - xx0 + 1) * np.maximum(0, yy1 - yy0 + 1)
            idx = idx[1:][inter / (area[i] + area[idx[1:]] - inter) <= 0.4]
        return np.hstack([b[fica], s[fica, None]]).astype(np.float32), p[fica].astype(np.float32)


def alinhar(im, kp, tam=112):
    """o mesmo alinhamento do insightface (semelhança nos 5 pontos → gabarito ArcFace 112)"""
    import cv2
    from skimage.transform import SimilarityTransform
    try:
        t = SimilarityTransform.from_estimate(kp, ARC)
    except AttributeError:
        t = SimilarityTransform(); t.estimate(kp, ARC)
    return cv2.warpAffine(im, t.params[0:2, :], (tam, tam), borderValue=0.0)


class AdaFace:
    def __init__(self, dev="cuda"):
        import torch
        sys.path.insert(0, os.path.dirname(ADAFACE)); import net                 # noqa: E401
        self.m = net.build_model("ir_101")
        sd = torch.load(ADAFACE, map_location="cpu", weights_only=False)["state_dict"]
        self.m.load_state_dict({k[6:]: v for k, v in sd.items() if k.startswith("model.")}); self.m = self.m.to(dev).eval(); self.dev = dev

    def digitais(self, alinhados_bgr):
        import torch
        if not alinhados_bgr: return np.zeros((0, 512), np.float32)
        out = []
        for i in range(0, len(alinhados_bgr), 64):                                   # lote: a placa faz 64 de uma vez
            x = np.stack(alinhados_bgr[i:i + 64]).astype(np.float32) / 255.0
            x = torch.from_numpy((x - 0.5) / 0.5).permute(0, 3, 1, 2).contiguous().to(self.dev)
            with torch.no_grad():
                e, _ = self.m(x)
            out.append(torch.nn.functional.normalize(e, dim=-1).cpu().numpy())
        return np.concatenate(out).astype(np.float32)


class Expressao:
    def __init__(self, placa=True):
        self.s = _sessao(EMO, placa)

    def ler(self, recortes_rgb):
        import cv2
        if not recortes_rgb: return []
        x = np.stack([cv2.resize(c, (224, 224)) / 255.0 for c in recortes_rgb]).astype(np.float32)
        x = (x - np.array([0.485, 0.456, 0.406], np.float32)) / np.array([0.229, 0.224, 0.225], np.float32)
        lg = np.concatenate([self.s.run(None, {"input": x[i:i + 64].transpose(0, 3, 1, 2)})[0] for i in range(0, len(x), 64)])
        e = np.exp(lg - lg.max(1, keepdims=True)); p = e / e.sum(1, keepdims=True)
        return [(EMOS[int(np.argmax(r))], r) for r in p]


def rodar(A, ctx):
    import cv2
    from . import preparo
    p = A["preparo"]
    if not p["tem_imagem"]: return {"quadros": [], "rostos": 0}
    pasta = preparo.caminho(A, "q1"); qs = sorted(os.listdir(pasta))
    det = Scrfd(ctx.placa); emo = Expressao(ctx.placa)
    onde = {"rostos (SCRFD)": det.s.get_providers()[0], "expressão": emo.s.get_providers()[0]}
    if ctx.placa and any(v != "CUDAExecutionProvider" for v in onde.values()):
        ctx.log("ATENÇÃO: modelo de rosto no PROCESSADOR em vez da placa:", onde)
    ada = AdaFace("cuda" if ctx.placa else "cpu")
    rec_dir = os.path.join(A.dir("rostos"), "recortes"); os.makedirs(rec_dir, exist_ok=True)
    por_q, alinhados, meta = [], [], []
    for f in qs:
        im = cv2.imread(os.path.join(pasta, f)); h, w = im.shape[:2]; t = int(f[:5]) - 1 + 0.5
        caixas, pts = det.detectar(im)
        lst, recs = [], []
        for b, kp in zip(caixas, pts):
            x0, y0, x1, y1, sc = map(float, b); bw, bh = x1 - x0, y1 - y0
            if sc < 0.5 or min(bw, bh) < 36: continue
            c = im[max(0, int(y0)):int(y1), max(0, int(x0)):int(x1)]
            if c.size == 0: continue
            item = {"caixa": [int(x0), int(y0), int(bw), int(bh)], "tam": round(bw / w, 3), "nota": round(sc, 3)}
            recs.append(cv2.cvtColor(c, cv2.COLOR_BGR2RGB)); lst.append(item)
            if min(bw, bh) >= 56:                                     # digital só de rosto grande o bastante (igual ao catálogo)
                al = alinhar(im, kp)
                nit = float(cv2.Laplacian(cv2.cvtColor(al, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
                if nit >= 25:
                    n = len(meta); mg = int(max(bw, bh) * 0.45)
                    cr = im[max(0, int(y0) - mg):min(h, int(y1) + mg), max(0, int(x0) - mg):min(w, int(x1) + mg)]
                    base.gravar_jpg(os.path.join(rec_dir, f"{n}.jpg"), cv2.resize(cr, (160, int(160 * cr.shape[0] / max(1, cr.shape[1])))), 85)
                    alinhados.append(al); meta.append([t, sc, round(bw / w, 3), round(nit, 1)]); item["digital"] = n
        for item, (rot, pr) in zip(lst, emo.ler(recs)):
            item["expressao"] = rot; item["p"] = {e: round(float(s), 3) for e, s in zip(EMOS, pr)}
        if lst: por_q.append({"t": t, "rostos": lst})
    dig = ada.digitais(alinhados)
    np.savez_compressed(os.path.join(A.dir("rostos"), "digitais.npz"), emb=dig.reshape(-1, 512), meta=np.array(meta, np.float32).reshape(-1, 4))
    del ada; base.liberar_torch()
    return {"quadros": por_q, "rostos": sum(len(x["rostos"]) for x in por_q), "digitais": int(len(dig)), "onde": onde,
            "arquivos": {"digitais": "pecas/rostos/digitais.npz", "recortes": "pecas/rostos/recortes"},
            "obs": "t = segundo do quadro 1/s (centro do segundo); digital = índice em digitais.npz (AdaFace 512, normalizada)"}
