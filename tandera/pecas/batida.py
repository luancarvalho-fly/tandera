# -*- coding: utf-8 -*-
"""BATIDA: Beat This! (final0) no stem de MÚSICA, cada batida puxada pro ATAQUE na onda (~10 ms); a grade reta FECHADA NA ONDA quando a
música é de tempo fixo (teste de 21/10); e o corte × batida (quadro da batida, desvio em quadros e ms, o acaso pra comparar)."""
import numpy as np

from .. import base


def _beat_this(placa):
    """o Beat This! (final0): o mesmo modelo da peça «musica» — no lote as duas usam o mesmo carregado"""
    from beat_this.inference import File2Beats
    return base.segurado(("beat_this", bool(placa)), lambda: File2Beats(checkpoint_path="final0", device="cuda" if placa else "cpu", dbn=False))


def aquecer(ctx):
    _beat_this(ctx.placa)


def batidas(wav, placa=True):
    import soundfile as sf
    b, db = _beat_this(placa)(wav)
    x, sr = sf.read(wav, dtype="float32", always_2d=True); x = x.mean(1)

    def ataque(t, jan=0.035):
        a, bb = max(0, int((t - jan) * sr)), min(len(x), int((t + jan) * sr))
        e = np.convolve(np.abs(x[a:bb]), np.ones(int(sr / 1000)) / int(sr / 1000), "same"); return (a + int(np.argmax(np.diff(e, prepend=e[0])))) / sr
    return {"batidas": [round(ataque(float(t)), 4) for t in b], "tempos_fortes": [round(ataque(float(t)), 4) for t in db]}


def grade_na_onda(wav, bt_lista, T=None):
    """tempo fixo (loop de DAW) = grade reta t_k = t0 + k·P, achada por PENTE nos ataques e fechada nos golpes fortes; resíduo grande =
    a música não é de tempo fixo e fica a lista crua do Beat This"""
    import soundfile as sf
    from scipy.signal import butter, sosfiltfilt
    from scipy.ndimage import maximum_filter1d
    bt = np.asarray(bt_lista, float)
    if len(bt) < 8:
        return {"fechada": False, "motivo": "poucas batidas"}
    x, sr = sf.read(wav, dtype="float64", always_2d=True); x = x.mean(1); T = T or len(x) / sr

    def env(lo, hi):
        sos = butter(4, [lo, hi], "bandpass", fs=sr, output="sos") if lo and hi else (butter(4, lo, "highpass", fs=sr, output="sos") if lo else butter(4, hi, "lowpass", fs=sr, output="sos"))
        y = np.abs(sosfiltfilt(sos, x)); kk = max(1, int(sr * 0.002)); return np.convolve(y, np.ones(kk) / kk, "same")
    E = {"agudo": env(2000, None), "grave": env(None, 150)}

    def ataque(e, t, jan=0.05):
        a, b = max(0, int((t - jan) * sr)), min(len(e), int((t + jan) * sr))
        if b - a < 10: return t, 0.0
        seg = e[a:b]; ip = int(np.argmax(seg)); pico = seg[ip]
        base_ = np.percentile(e[max(0, a - int(0.1 * sr)):a + 1], 20) if a > 0 else 0
        lim = base_ + 0.5 * (pico - base_); j = ip
        while j > 0 and seg[j] > lim: j -= 1
        return (a + j) / sr, float(20 * np.log10(pico + 1e-12) - 20 * np.log10(base_ + 1e-12))

    def golpe(t):
        ta, sa = ataque(E["agudo"], t); tg, sg = ataque(E["grave"], t)
        return (ta, sa, "agudo") if sa >= sg else (tg, sg, "grave")
    cheio = np.convolve(np.abs(x), np.ones(max(1, int(sr * 0.002))) / max(1, int(sr * 0.002)), "same")[:: int(sr / 1000)]
    o = maximum_filter1d(np.maximum(0, np.diff(np.log(cheio + 1e-6), prepend=np.log(cheio[0] + 1e-6))), 9)
    bpm_bt = 60 / float(np.median(np.diff(bt)))
    melhor = {}
    for mult in (0.5, 1.0, 2.0):
        b0 = bpm_bt * mult
        if not 50 <= b0 <= 220: continue
        res_m = (0, None, None)
        for bpm in np.arange(b0 * 0.92, b0 * 1.08, 0.02):
            Pm = 60 / bpm * 1000; n = int((len(o) - 1) / Pm)
            if n < 6: continue
            fases = np.arange(0, Pm, 2.0)
            idx = (fases[:, None] + np.arange(n)[None] * Pm).astype(int)
            sc = o[idx].mean(1); j = int(np.argmax(sc))
            if sc[j] > res_m[0]: res_m = (float(sc[j]), 60 / bpm, fases[j] / 1000)
        melhor[mult] = res_m
    cand = sorted([v for v in melhor.values() if v[1]], key=lambda v: v[1])
    if not cand:
        return {"fechada": False, "motivo": "sem andamento"}
    topo = max(v[0] for v in cand)
    P, t0 = next(v[1:] for v in cand if v[0] >= 0.6 * topo)
    meio_tempo = bool(abs(60 / P - 2 * bpm_bt) < 0.1 * bpm_bt)
    dist = lambda f: float(np.median(np.abs(((bt - f) / P + 0.5) % 1 - 0.5)))      # noqa: E731
    t0 = min((t0, t0 + P / 2), key=dist)
    pts = []
    for i in range(int(np.ceil(-t0 / P)) - 1, int((T - t0) / P) + 2):
        t = t0 + i * P
        if 0.05 < t < T - 0.05:
            ta, salto, _ = golpe(t)
            if salto > 12 and abs(ta - t) < 0.05: pts.append((i, ta))
    if len(pts) < 6:
        return {"fechada": False, "motivo": f"só {len(pts)} golpes fortes perto da grade", "bpm_cru": round(60 / P, 2), "meio_tempo": meio_tempo}
    ki, ti = np.array(pts).T
    P2, t02 = np.polyfit(ki, ti, 1); res = ti - (t02 + ki * P2)
    fechada = bool(np.median(np.abs(res)) < 0.012)
    grade = [round(float(t02 + i * P2), 4) for i in range(int(np.ceil(-t02 / P2)), int((T - t02) / P2) + 1) if 0 <= t02 + i * P2 <= T]
    return {"fechada": fechada, "bpm": round(float(60 / P2), 3), "P_s": round(float(P2), 5), "t0_s": round(float(t02), 4), "meio_tempo_corrigido": meio_tempo,
            "golpes_usados": int(len(pts)), "residuo_mediano_ms": round(float(np.median(np.abs(res))) * 1000, 1),
            "residuo_max_ms": round(float(np.max(np.abs(res))) * 1000, 1), "grade": grade if fechada else [],
            "motivo": "" if fechada else "resíduo grande: a música não é de tempo fixo (fica a lista crua do Beat This)"}


def corte_x_batida(cortes_q, fps, batidas_s, folga=0.0, meias=False):
    bt = np.asarray(batidas_s, float) - folga
    if not len(bt) or not len(cortes_q):
        return {"lista": [], "resumo": {}}
    alvos = [(t, "batida") for t in bt]
    if meias and len(bt) > 1:
        alvos += [((a + b) / 2, "meia batida") for a, b in zip(bt[:-1], bt[1:])]
    out = []
    for c in cortes_q:
        t = c / fps; tb, tipo = min(alvos, key=lambda x: abs(x[0] - t)); qb = int(np.floor(tb * fps + 1e-6))
        out.append({"corte_q": int(c), "batida_s": round(float(tb), 4), "tipo": tipo, "batida_q": qb, "desvio_q": int(c - qb), "desvio_ms": round((t - tb) * 1000, 1)})
    P = float(np.median(np.diff(bt))) / (2 if meias else 1) if len(bt) > 1 else 0
    d = np.array([o["desvio_q"] for o in out])
    return {"lista": out, "resumo": {"cortes": len(out), "no_quadro_da_batida": int((d == 0).sum()), "a_1_quadro": int((np.abs(d) <= 1).sum()),
                                     "mediana_ms": round(float(np.median([o["desvio_ms"] for o in out])), 1),
                                     "acaso_a_1_quadro_pct": round(min(100.0, 300.0 / (P * fps)) if P else 0, 1)}}


def rodar(A, ctx):
    from . import separacao
    mus = separacao.stem(A, "musica")
    if not mus:
        return {"sem_som": True}
    b = batidas(mus, ctx.placa)
    base.liberar_torch()
    g = grade_na_onda(mus, b["batidas"])
    c = A["cortes"]; folga = A["preparo"].get("folga_aac_s", 0.0)
    usar = g.get("grade") or b["batidas"]
    cxb = corte_x_batida(c["cortes"], c["fps"], usar, folga, meias=bool(g.get("grade")))
    cxb["fonte"] = "grade fechada na onda" if g.get("grade") else "lista crua do Beat This"
    return {**b, "grade": g, "corte_x_batida": cxb}
