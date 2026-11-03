# -*- coding: utf-8 -*-
"""ENTONAÇÃO (Praat): trechos contínuos de fala (pausa > 0,25 s quebra) com a altura no começo/fim (semitons rel. 110 Hz), o final
(st/s: sobe = pergunta?, desce, plano) e as sílabas por segundo. Medida, não veredito."""
import re

import numpy as np


def entonacao(wav_voz, palavras):
    import parselmouth
    snd = parselmouth.Sound(wav_voz); tr = []; cur = []
    for w in palavras:
        if cur and w["ini"] - cur[-1]["fim"] > 0.25: tr.append(cur); cur = []
        cur.append(w)
    if cur: tr.append(cur)
    out = []
    for t in tr:
        a, b = t[0]["ini"], t[-1]["fim"]
        p = snd.extract_part(from_time=max(0, a - 0.05), to_time=b + 0.05, preserve_times=True).to_pitch(time_step=0.01, pitch_floor=70, pitch_ceiling=350)
        f = p.selected_array["frequency"]; xs = p.xs(); v = f > 0
        st = 12 * np.log2(f[v] / 110.0); vt = xs[v]

        def med(x0, x1):
            m = (vt >= x0) & (vt <= x1); return round(float(st[m].mean()), 2) if m.any() else None
        incl = float(np.polyfit(vt[vt >= vt[-1] - 0.35], st[vt >= vt[-1] - 0.35], 1)[0]) if len(vt) > 5 and (vt >= vt[-1] - 0.35).sum() > 3 else None
        sil = sum(max(1, len(re.findall(r"[aeiouáéíóúâêôãõ]+", w["p"].lower()))) for w in t)
        out.append({"ini": round(a, 3), "fim": round(b, 3), "texto": " ".join(w["p"] for w in t), "altura_ini_st": med(a, a + 0.25) if len(vt) else None,
                    "altura_fim_st": med(b - 0.25, b) if len(vt) else None, "final_st_por_s": round(incl, 1) if incl is not None else None,
                    "final": None if incl is None else ("sobe (pergunta?)" if incl > 6 else ("desce" if incl < -6 else "plano")),
                    "silabas_por_s": round(sil / max(0.2, b - a), 2)})
    return out


def rodar(A, ctx):
    from . import separacao
    pal = A["fala"].get("palavras") or []
    voz = separacao.stem(A, "voz")
    return {"trechos": entonacao(voz, pal) if voz and pal else []}
