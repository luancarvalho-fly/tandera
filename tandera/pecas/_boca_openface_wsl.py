# -*- coding: utf-8 -*-
"""Tandera V2 — rosto, lado Linux (WSL): OpenFace 3.0, a boca pelos 98 pontos (lábio de dentro 90×94 ÷ ponte do nariz→queixo), como no
teste de 17/10 (teste_rosto_openface.py, AUC 0,875 na boca × fala). Roda com /opt/regua/.venv/bin/python (scripts\\tandera_rosto.sh).
Uso: python tandera_rosto_wsl.py lista.json saida.json pasta_dos_pesos   (lista = [caminhos /mnt/c/... dos quadros])"""
import json, os, sys
import numpy as np, cv2, torch
from openface.face_detection import FaceDetector
from openface.landmark_detection import LandmarkDetector

lista = json.load(open(sys.argv[1])); W = sys.argv[3]
det = FaceDetector(model_path=os.path.join(W, "Alignment_RetinaFace.pth"), device="cuda")
lmk = LandmarkDetector(model_path=os.path.join(W, "Landmark_98.pkl"), device="cuda", device_ids=[0])
out = {}
for f in lista:
    o = {}
    try:
        face, dets = det.get_face(f)
        if face is not None:
            im = cv2.imread(f)
            lm = lmk.detect_landmarks(im, dets)
            if lm is not None and len(lm):
                p = np.array(lm[0]).reshape(-1, 2)
                if len(p) == 98:
                    alt = np.linalg.norm(p[51] - p[16]) + 1e-9
                    o = {"boca": float(np.linalg.norm(p[90] - p[94]) / alt), "rosto_larg": float((p[:, 0].max() - p[:, 0].min()) / im.shape[1])}
    except Exception as e:
        o = {"erro": str(e)[:100]}
    out[f] = o
json.dump(out, open(sys.argv[2], "w"))
print("quadros", len(out), "com rosto", sum(1 for v in out.values() if "boca" in v))
