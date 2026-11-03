# -*- coding: utf-8 -*-
"""STEMS DO PLEXUS (4_MIXAGEM) → o que o tandera.analisar(..., stems=...) entende (01/11, panelas de som).
A mixagem de cada vídeo do canal vem faixa por faixa: «V009_[VOZES_MIXADO].wav», «[PLEXUS_MIXADO_1]», «[MUSICAS_MIXADO]»,
«[SFX_MIXADO_1..9]», às vezes um render da mistura, e rascunhos («teste voice change.wav», «ElevenLabs_…»). Aqui:
  papel(nome)            → (papel, família) ou None: voz (VOZES, PLEXUS e as vozes de personagem: CHUBBY, FREDIE…), musica, efeitos (SFX),
                           mix (render/master); família = «mixado» ([X_MIXADO_n]), «simples» (MUSICAS.wav…) ou «mvsep» (separado no mvsep)
  escolher(...)          → {papel: [arquivos]} só com as faixas do tamanho do vídeo (±0,5 s) e de UMA família (V017/V020 têm as duas)
  juntar(arquivos, dst)  → soma as faixas de um papel num wav só, SEMPRE igual (mesma ordem, float32) e com a data = a mais nova das
                           faixas: o mesmo arquivo dá a mesma assinatura no servidor e no PC (a separação «entregue-…» bate)
Roda em qualquer Python com numpy + soundfile (+ soxr se as taxas forem diferentes)."""
import os, re, unicodedata

TOL_S = 0.5


def _norm(nome):
    t = "".join(c for c in unicodedata.normalize("NFD", os.path.splitext(os.path.basename(nome))[0]) if unicodedata.category(c) != "Mn")
    return t.upper()


def papel(nome):
    n = _norm(nome)
    if "MVSEP" in n:
        for k, p in (("SPEECH", "voz"), ("MUSIC", "musica"), ("SFX", "efeitos")):
            if f"_{k}_" in n or n.endswith(k): return p, "mvsep"
        return None
    m = re.search(r"\[([A-Z ]+?)_MIXADO", n)
    if m:
        cat = m.group(1).strip()
        if cat in ("MUSICAS", "MUSICA"): return "musica", "mixado"
        if cat == "SFX": return "efeitos", "mixado"
        return "voz", "mixado"                                  # VOZES, PLEXUS, VOZ e as vozes de personagem (CHUBBY, FREDIE, VLOGS…)
    if re.search(r"\[(MIXADO|RENDER)\]|MASTER_PRINT", n): return "mix", "mixado"
    base = re.sub(r"^\d+\s*-\s*", "", n).strip()
    if base in ("MUSICAS", "MUSICA"): return "musica", "simples"
    if base == "SFX": return "efeitos", "simples"
    if base in ("VOZES", "PLEXUS", "VOZ"): return "voz", "simples"
    if re.fullmatch(r"\d{3}(_RENDER)?", base): return "mix", "simples"
    return None


def escolher(stems, dur_video, durs, mtimes=None):
    """stems = {nome: caminho}, durs = {nome: s} → ({papel: [caminhos]} ou {}, [notas]). Fica a família com mais faixas no tamanho do
    vídeo (empate: a mais nova); sem voz, ou sem música e sem efeitos = {} (a separação roda pelo modelo)."""
    notas, fam = [], {}
    for nome, cam in sorted(stems.items()):
        pf = papel(nome)
        if not pf:
            notas.append(f"fora (não é faixa da mixagem): {nome}"); continue
        d = durs.get(nome)
        if not d or abs(d - dur_video) > TOL_S:
            notas.append(f"fora (tem {d or 0:.2f} s, o vídeo {dur_video:.2f} s): {nome}"); continue
        fam.setdefault(pf[1], {}).setdefault(pf[0], []).append(cam)
    boas = {f: g for f, g in fam.items() if g.get("voz") and (g.get("musica") or g.get("efeitos"))}
    if not boas:
        return {}, notas + ["sem voz + música/efeitos do tamanho do vídeo: a separação roda pelo modelo"]
    nova = lambda g: max((mtimes or {}).get(c, 0) for v in g.values() for c in v)          # noqa: E731
    f = max(boas, key=lambda f: (sum(len(v) for v in boas[f].values()), nova(boas[f])))
    if len(boas) > 1: notas.append(f"duas famílias de faixas ({', '.join(sorted(boas))}): fica «{f}»")
    g = {p: sorted(v) for p, v in boas[f].items()}
    if len(g.get("mix", [])) != 1: g.pop("mix", None)       # render: só se houver UM
    return g, notas


def grava_wav_float(dst, x, sr):
    """WAV float32 SEMPRE com os mesmos bytes pras mesmas amostras. O soundfile (libsndfile) põe um bloco PEAK com a HORA da gravação:
    01/11, prova no WSL — a mesma soma no Windows e no Linux deu amostras idênticas e 2 bytes diferentes no cabeçalho → outra assinatura
    → outra versão da separação entregue (o PC refaria tudo)."""
    import struct
    import numpy as np
    x = np.ascontiguousarray(x, dtype="<f4"); n, ch = x.shape
    dados = x.tobytes()
    fmt = struct.pack("<HHIIHHH", 3, ch, sr, sr * ch * 4, ch * 4, 32, 0)            # IEEE float, cbSize 0
    corpo = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"fact" + struct.pack("<II", 4, n) + b"data" + struct.pack("<I", len(dados)) + dados
    with open(dst, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", len(corpo)) + corpo)


def juntar(arquivos, dst, mtime=None):
    """soma as faixas (ordem do nome) num wav float32; mono vira estéreo se alguma for estéreo; taxa = a da 1ª (soxr nas outras)"""
    import numpy as np, soundfile as sf
    arquivos = sorted(arquivos, key=lambda c: os.path.basename(c))
    xs, sr0 = [], None
    for c in arquivos:
        x, sr = sf.read(c, dtype="float32", always_2d=True)
        if sr0 is None: sr0 = sr
        elif sr != sr0:
            import soxr
            x = soxr.resample(x, sr, sr0).astype(np.float32)
        xs.append(x)
    ch = max(x.shape[1] for x in xs); n = max(len(x) for x in xs)
    soma = np.zeros((n, ch), np.float32)
    vistos, repetidas = [], []
    for c, x in zip(arquivos, xs):
        # o mesmo export salvo duas vezes («[VOZES_MIXADO]» e «[VOZES_MIXADO_1]» iguais) entraria em dobro: igual a uma já somada = fora
        m = x.mean(1)[: len(x) - len(x) % 100].reshape(-1, 100).mean(1) if len(x) >= 100 else x.mean(1)
        if any(len(v) == len(m) and float(np.abs(v - m).max()) <= 1e-4 * (float(np.abs(v).max()) + 1e-9) for v in vistos if np.abs(v).max() > 0):
            repetidas.append(os.path.basename(c)); continue
        vistos.append(m)
        soma[:len(x)] += x if x.shape[1] == ch else np.repeat(x[:, :1], ch, axis=1)
    if repetidas: print("stems: faixa repetida fora da soma:", ", ".join(repetidas), flush=True)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + ".parcial.wav"
    grava_wav_float(tmp, soma, sr0); os.replace(tmp, dst)
    m = mtime if mtime is not None else max(os.stat(c).st_mtime for c in arquivos)
    os.utime(dst, (m, m))
    return dst


def stems_prontos(escolhidos, pasta, mtimes=None):
    """{papel: [caminhos]} → {papel: um arquivo}: faixa única fica como está; várias são somadas em <pasta>/<papel>.wav"""
    out = {}
    for p, cams in escolhidos.items():
        if len(cams) == 1: out[p] = cams[0]
        else: out[p] = juntar(cams, os.path.join(pasta, p + ".wav"), max((mtimes or {}).get(c) or os.stat(c).st_mtime for c in cams))
    return out
