# -*- coding: utf-8 -*-
"""SINAL — as medidas de conta pura (sem modelo) que a ficha sonora usa desde agosto, agora dentro do Tandera (leves: só numpy e
OpenCV, rodam em qualquer Python). O corte NÃO sai mais daqui (o histograma perdia 17 de 59 no V009): quem dá o corte é a peça
«cortes» (AutoShot ∪ TransNetV2) e ele entra aqui como entrada.
  ataques(wav)            fluxo espectral com limiar LOCAL: instante (10 ms), força, pico em dB, banda (grave/médio/agudo)
  movimento(video, cortes) quanto a imagem muda quadro a quadro (0–100) e os PICOS (salto sobre o meio segundo anterior)
  fala_ativa(voz, dur)    onde a voz separada TEM som (50 ms; buracos < 0,25 s fecham)
  vaos(falas, dur)        trechos sem fala ≥ 0,4 s (onde golpe de virada cabe)
  candidatos(ats, mov, rots)  junta ataque + pico de movimento + corte + etiqueta física num evento (até 0,35 s)
  folha(video, t0, t1, destino)  quadros a qps/s com o tempo escrito, numa grade"""
import os, subprocess

import numpy as np

SR = 44100


def le_audio(caminho, sr=SR):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", caminho, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True, check=True,
                         creationflags=0x08000000 if os.name == "nt" else 0).stdout
    return np.frombuffer(raw, np.float32).copy()


def ataques(wav):
    """Devolve (ataques [{t, forca, pico_db, banda}], envelope a cada 0,1 s)"""
    x = le_audio(wav)
    n, h = 2048, 441
    if x.size < n: return [], []
    quadros = np.lib.stride_tricks.sliding_window_view(x, n)[::h] * np.hanning(n)
    S = np.abs(np.fft.rfft(quadros, axis=1)); f = np.fft.rfftfreq(n, 1 / SR)
    fluxo = np.concatenate([[0], np.maximum(0, np.diff(np.log1p(S * 50), axis=0)).sum(1)])
    env_db = 20 * np.log10(np.sqrt(np.mean(quadros ** 2, axis=1)) + 1e-9)
    k = 50                                  # limiar LOCAL (1 s em volta): um tiro alto não deixa o resto «surdo»
    jan = np.lib.stride_tricks.sliding_window_view(np.pad(fluxo, k, mode="edge"), 2 * k + 1)
    med = np.median(jan, axis=1); mad = np.median(np.abs(jan - med[:, None]), axis=1)
    limiar = med + 2.5 * mad + 0.02 * fluxo.max()
    picos = []
    for i in range(1, fluxo.size - 1):
        if fluxo[i] > limiar[i] and fluxo[i] >= fluxo[i - 1] and fluxo[i] >= fluxo[i + 1]:
            if picos and i - picos[-1] < 6:
                if fluxo[i] > fluxo[picos[-1]]: picos[-1] = i
                continue
            picos.append(i)
    teto = env_db.max(); kk = 150
    teto_local = np.lib.stride_tricks.sliding_window_view(np.pad(env_db, kk, mode="edge"), 2 * kk + 1).max(axis=1)
    out = []
    for i in picos:
        j = min(env_db.size - 1, i + 8); pico = float(env_db[i:j + 1].max())
        if pico < teto - 50 or pico < teto_local[i] - 24 or pico - float(env_db[max(0, i - 3)]) < 3: continue
        esp = S[i:j + 1].mean(0)
        bandas = {"grave": esp[f < 250].sum(), "médio": esp[(f >= 250) & (f < 2500)].sum(), "agudo": esp[f >= 2500].sum()}
        out.append(dict(t=round(i * h / SR, 2), forca=round(float(fluxo[i] / (fluxo.max() + 1e-9)), 2), pico_db=round(pico - teto, 1),
                        banda=max(bandas, key=bandas.get)))
    env = [dict(t=round(i * h / SR, 1), db=round(float(env_db[i:i + 10].max() - teto), 1)) for i in range(0, env_db.size, 10)]
    return out, env


def _quadros_ffmpeg(video):
    """(fps, gerador de quadros BGR no tamanho cheio) pelo ffmpeg — quando o OpenCV não abre o vídeo"""
    import json as _json
    j = _json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate",
                                    "-of", "json", video], capture_output=True, text=True).stdout or "{}").get("streams") or [{}]
    w, h = j[0].get("width"), j[0].get("height")
    n, _, d = (j[0].get("r_frame_rate") or "30/1").partition("/"); fps = float(n) / float(d or 1)
    if not w: return fps, iter(())

    def gera():
        pr = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", video, "-map", "0:v:0", "-an", "-pix_fmt", "bgr24", "-f", "rawvideo", "-"],
                              stdout=subprocess.PIPE, creationflags=0x08000000 if os.name == "nt" else 0)
        t = w * h * 3
        try:
            while True:
                b = pr.stdout.read(t)
                if len(b) < t: break
                yield np.frombuffer(b, np.uint8).reshape(h, w, 3)
        finally:
            pr.stdout.close(); pr.wait()
    return fps, gera()


def movimento(video, cortes_s=(), cinza=None, fps_cinza=None):
    """{fps, picos [{t, salto, mov}], curva [{t, mov}] a cada 0,1 s, dur}; corte (da peça «cortes») não é movimento.
    01/11 (panelas): o OpenCV do Linux não abre AV1 (os 4K AV1 de um cliente): nenhum quadro lido = os mesmos quadros pelo ffmpeg, a mesma conta
    (medido no WSL: sem isso, 0 picos × 6 no PC). No PC o OpenCV abre e nada muda."""
    import cv2
    if cinza is not None:
        # SERVIDOR (lote RunPod 01/11): os quadros 96×170 cinza vêm da mesma leitura do preparo — não abre o vídeo de novo (PC: não vêm)
        cq = {int(round(c * fps_cinza)) for c in cortes_s}
        mov, ant = [], None
        for i, g in enumerate(cinza):
            p = g.astype(np.float32)
            mov.append(0.0 if ant is None or i in cq else float(np.mean(np.abs(p - ant))))
            ant = p
        return _movimento_fim(np.array(mov), fps_cinza, cortes_s)
    cap = cv2.VideoCapture(video); fps = cap.get(cv2.CAP_PROP_FPS) or 30
    ok, fr = cap.read()
    if ok:
        def quadros(primeiro=fr):
            yield primeiro
            while True:
                ok, f = cap.read()
                if not ok: break
                yield f
        fonte = quadros()
    else:
        cap.release(); fps, fonte = _quadros_ffmpeg(video)
    cq = {int(round(c * fps)) for c in cortes_s}
    ant, mov, i = None, [], 0
    for fr in fonte:
        p = cv2.cvtColor(cv2.resize(fr, (96, 170)), cv2.COLOR_BGR2GRAY).astype(np.float32)
        mov.append(0.0 if ant is None or i in cq else float(np.mean(np.abs(p - ant))))
        ant = p; i += 1
    cap.release()
    return _movimento_fim(np.array(mov), fps, cortes_s)


def _movimento_fim(mov, fps, cortes_s):
    picos = []
    cortes = sorted(cortes_s)
    if mov.size > 5:
        janela = max(3, int(fps / 2))
        for k in range(janela, mov.size - 1):
            b = np.median(mov[k - janela:k]) + 1e-6
            if mov[k] > 2.2 * b and mov[k] > 4 and mov[k] >= mov[k - 1] and mov[k] >= mov[k + 1]:
                t = round(k / fps, 2)
                if any(abs(t - c) < 0.15 for c in cortes): continue
                if picos and t - picos[-1]["t"] < 0.2: continue
                picos.append(dict(t=t, salto=round(float(mov[k] / b), 1), mov=round(float(mov[k]), 1)))
    passo = max(1, int(fps / 10))
    curva = [dict(t=round(k / fps, 1), mov=round(float(mov[k:k + passo].mean()), 1)) for k in range(0, mov.size, passo)]
    return dict(fps=fps, picos=picos, curva=curva, dur=round(mov.size / fps, 2), cortes=list(cortes))


def fala_ativa(voz, dur=None):
    x = le_audio(voz, 16000); h = 800; n = x.size // h
    if n == 0: return []
    db = 20 * np.log10(np.sqrt(np.mean(x[:n * h].reshape(n, h) ** 2, axis=1)) + 1e-9)
    ativo = db > db.max() - 30; trechos, ini = [], None
    for k, a in enumerate(ativo):
        if a and ini is None: ini = k
        if not a and ini is not None: trechos.append([ini * 0.05, k * 0.05]); ini = None
    if ini is not None: trechos.append([ini * 0.05, n * 0.05])
    juntos = []
    for t in trechos:
        if juntos and t[0] - juntos[-1][1] < 0.25: juntos[-1][1] = t[1]
        else: juntos.append(t)
    return [dict(ini=round(a, 2), fim=round(b, 2), txt="") for a, b in juntos if b - a >= 0.1]


def vaos(falas, dur):
    out, ultimo = [], 0.0
    for f in falas:
        if f["ini"] - ultimo >= 0.4: out.append((round(ultimo, 2), round(f["ini"], 2)))
        ultimo = max(ultimo, f["fim"])
    if dur - ultimo >= 0.4: out.append((round(ultimo, 2), round(dur, 2)))
    return out


FISICOS = ("Bang", "Slam", "Thump", "Thud", "Door", "Crash", "Smash", "Explosion", "Breaking", "Knock", "Tap", "Clatter", "Vehicle", "Car",
           "Engine", "Truck", "Skidding", "Tire squeal", "Footsteps", "Walk", "Run", "Scream", "Shout", "Yell", "Crowd", "Cheering", "Applause",
           "Whoosh", "Splash", "Glass", "Wood", "Metal", "Punch", "Hit", "Fire", "Gunshot", "Thunk", "Clip-clop", "Squeal", "Creak", "Rumble",
           "Gasp", "Grunt")


def candidatos(ats, mov, rots):
    evs = [dict(t=a["t"], fonte={"som"}, a=a) for a in ats]
    evs += [dict(t=p["t"], fonte={"movimento"}, m=p) for p in mov["picos"]]
    evs += [dict(t=c, fonte={"corte"}) for c in mov["cortes"]]
    evs.sort(key=lambda e: e["t"]); grupos = []
    for e in evs:
        if grupos and e["t"] - grupos[-1]["fim"] <= 0.35:
            g = grupos[-1]; g["fim"] = e["t"]; g["fonte"] |= e["fonte"]; g["itens"].append(e)
        else:
            grupos.append(dict(ini=e["t"], fim=e["t"], fonte=set(e["fonte"]), itens=[e]))
    jan = (rots or {}).get("janelas", [])
    for g in grupos:
        nomes = {}
        for w in (w for w in jan if g["ini"] - 0.6 <= w["t"] <= g["fim"] + 0.6):
            for n, p in w["rotulos"]:
                if any(f.lower() in n.lower() for f in FISICOS): nomes[n] = max(nomes.get(n, 0), p)
        g["rotulos"] = sorted(nomes.items(), key=lambda kv: -kv[1])[:4]
        if g["rotulos"]: g["fonte"].add("rótulo")
        fs = [i["a"]["forca"] for i in g["itens"] if "a" in i]; ss = [i["m"]["salto"] for i in g["itens"] if "m" in i]
        g["forca_som"] = max(fs) if fs else 0; g["salto_mov"] = max(ss) if ss else 0
        g["banda"] = next((i["a"]["banda"] for i in g["itens"] if "a" in i), "")
        g["fonte"] = sorted(g["fonte"]); g.pop("itens")
    return grupos


def folha(arq, t0, t1, destino, qps=10, largura=320, colunas=6):
    import cv2
    cap = cv2.VideoCapture(arq); fps = cap.get(cv2.CAP_PROP_FPS) or 30; imgs = []; t = max(0.0, t0)
    while t <= t1 + 1e-6:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(t * fps))); ok, fr = cap.read()
        if not ok: break
        h, w = fr.shape[:2]; fr = cv2.resize(fr, (largura, int(h * largura / w)))
        cv2.rectangle(fr, (0, 0), (78, 24), (0, 0, 0), -1)
        cv2.putText(fr, f"{t:5.2f}s", (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 255), 1, cv2.LINE_AA)
        imgs.append(fr); t += 1.0 / qps
    cap.release()
    if not imgs: return None
    while len(imgs) % colunas: imgs.append(np.zeros_like(imgs[0]))
    cv2.imwrite(destino, np.vstack([np.hstack(imgs[i:i + colunas]) for i in range(0, len(imgs), colunas)]), [cv2.IMWRITE_JPEG_QUALITY, 82])
    return destino
