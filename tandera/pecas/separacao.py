# -*- coding: utf-8 -*-
"""SEPARAÇÃO: voz (BS-Roformer ep317, na placa, ambiente .venv-sep da REGUA) → o resto vira música × efeitos (BandIt Plus DnR, ambiente
do separador-cinema). Cada parte é gravada ao lado e trocada no fim (processo morto no meio não deixa wav pela metade; rodar de novo
pula a parte que terminou). Sai (pecas\\separacao\\): mix_48k · voz_48k · resto_48k (tudo menos a voz) · musica_48k · efeitos_48k."""
import os, shutil, subprocess

from .. import base


def separar(som48k, pasta, placa=True, log=base.log):
    import numpy as np, soundfile as sf
    p = lambda n: os.path.join(pasta, n)                     # noqa: E731
    parcial = lambda n: p(n[:-4] + ".parcial.wav")           # noqa: E731
    os.makedirs(pasta, exist_ok=True)
    if not os.path.exists(p("mix_48k.wav")):
        base.run(["ffmpeg", "-v", "error", "-y", "-i", som48k, "-ar", "48000", "-ac", "2", "-c:a", "pcm_f32le", parcial("mix_48k.wav")])
        os.replace(parcial("mix_48k.wav"), p("mix_48k.wav"))
    if not os.path.exists(p("voz_48k.wav")):
        log("separação 1/2: voz (BS-Roformer)")
        base.run(["ffmpeg", "-v", "error", "-y", "-i", p("mix_48k.wav"), "-ar", "44100", "-c:a", "pcm_f32le", p("mix_44k.wav")])
        d = p("rofo"); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
        env = dict(os.environ); env["PYTHONIOENCODING"] = "utf-8"
        if not placa: env["CUDA_VISIBLE_DEVICES"] = "-1"   # 03/11: vazio no Windows o audio-separator lia como placa e quebrava ("Invalid device id"); -1 = sem placa
        subprocess.run([base.ROFO, p("mix_44k.wav"), "--output_dir", d, "--output_format", "WAV", "--model_filename",
                        "model_bs_roformer_ep_317_sdr_12.9755.ckpt"] + (["--model_file_dir", base.ROFO_MODELOS] if base.ROFO_MODELOS else []),
                       check=True, env=env, capture_output=True, creationflags=base.SEM_JANELA)
        v = [f for f in os.listdir(d) if "vocal" in f.lower()][0]
        base.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(d, v), "-ar", "48000", "-ac", "2", "-c:a", "pcm_f32le", parcial("voz_48k.wav")])
        x, _ = sf.read(p("mix_48k.wav"), dtype="float32", always_2d=True); v_, _ = sf.read(parcial("voz_48k.wav"), dtype="float32", always_2d=True)
        n = min(len(x), len(v_))
        sf.write(parcial("resto_48k.wav"), x[:n] - v_[:n], 48000, subtype="FLOAT")
        os.replace(parcial("resto_48k.wav"), p("resto_48k.wav")); os.replace(parcial("voz_48k.wav"), p("voz_48k.wav"))
        shutil.rmtree(d, ignore_errors=True); os.remove(p("mix_44k.wav"))
    if not os.path.exists(p("efeitos_48k.wav")):
        log("separação 2/2: música × efeitos (BandIt Plus)")
        ent = p("bandit_in"); os.makedirs(ent, exist_ok=True); shutil.copy2(p("resto_48k.wav"), os.path.join(ent, "resto.wav"))
        cmd = [base.PY_CINE, os.path.join(base.CINE, "modelos-teste", "bancada", "rodar_msst_stub.py"),
               "--model_type", "bandit", "--config_path", os.path.join(base.CINE, "msst", "configs", "config_dnr_bandit_bsrnn_multi_mus64.yaml"),
               "--start_check_point", os.path.join(base.CINE, "modelos-teste", "bandit_plus", "model_bandit_plus_dnr_sdr_11.47.chpt"),
               "--input_folder", ent, "--store_dir", p("bandit")]
        if not placa: cmd.append("--force_cpu")
        subprocess.run(cmd, check=True, capture_output=True, creationflags=base.SEM_JANELA)
        pa = os.path.join(p("bandit"), "resto"); mf = [f for f in os.listdir(pa) if "music" in f.lower() and f.endswith(".wav")][0]
        import librosa
        mus, sr = sf.read(os.path.join(pa, mf), dtype="float32", always_2d=True)
        if sr != 48000: mus = librosa.resample(mus.T, orig_sr=sr, target_sr=48000).T
        r, _ = sf.read(p("resto_48k.wav"), dtype="float32", always_2d=True); n = min(len(r), len(mus))
        sf.write(parcial("musica_48k.wav"), mus[:n], 48000, subtype="FLOAT"); sf.write(parcial("efeitos_48k.wav"), r[:n] - mus[:n], 48000, subtype="FLOAT")
        os.replace(parcial("musica_48k.wav"), p("musica_48k.wav")); os.replace(parcial("efeitos_48k.wav"), p("efeitos_48k.wav"))
        shutil.rmtree(ent, ignore_errors=True); shutil.rmtree(p("bandit"), ignore_errors=True)
    return {k: p(k + "_48k.wav") for k in ("mix", "voz", "resto", "musica", "efeitos")}


def separar_varios(itens, placa=True, log=base.log, trabalho=None):
    """O LOTE (01/11, «um motor só»): a MESMA conta do separar() pra vários vídeos, com o BS-Roformer e o BandIt carregados UMA vez:
    o audio-separator recebe todos os mix_44k de uma vez (ele carrega o modelo e passa arquivo por arquivo, limpando o que é de cada
    arquivo) e o msst do BandIt lê a pasta com todos os restos. Cada vídeo é gravado na pasta dele com os mesmos nomes e as mesmas
    contas de antes. itens = [(som48k, pasta)] → [dict dos stems, ou a exceção daquele vídeo]."""
    import tempfile
    import numpy as np, soundfile as sf
    P = lambda pasta, n: os.path.join(pasta, n)                         # noqa: E731
    parcial = lambda pasta, n: P(pasta, n[:-4] + ".parcial.wav")        # noqa: E731
    out = [None] * len(itens)
    for i, (som48k, pasta) in enumerate(itens):
        try:
            os.makedirs(pasta, exist_ok=True)
            if not os.path.exists(P(pasta, "mix_48k.wav")):
                base.run(["ffmpeg", "-v", "error", "-y", "-i", som48k, "-ar", "48000", "-ac", "2", "-c:a", "pcm_f32le", parcial(pasta, "mix_48k.wav")])
                os.replace(parcial(pasta, "mix_48k.wav"), P(pasta, "mix_48k.wav"))
        except Exception as e:
            out[i] = e
    vivos = lambda: [i for i in range(len(itens)) if not isinstance(out[i], Exception)]     # noqa: E731
    tmp = tempfile.mkdtemp(prefix="sep_lote_", dir=trabalho)
    try:
        # 1/2 voz: um audio-separator pra todos os que faltam
        falta = [i for i in vivos() if not os.path.exists(P(itens[i][1], "voz_48k.wav"))]
        if falta:
            log(f"separação 1/2: voz (BS-Roformer) — {len(falta)} vídeo(s) com o modelo carregado uma vez")
            ent, d = os.path.join(tmp, "rofo_in"), os.path.join(tmp, "rofo")
            os.makedirs(ent); os.makedirs(d)
            nomes = {}
            for i in falta:
                pasta = itens[i][1]
                try:
                    base.run(["ffmpeg", "-v", "error", "-y", "-i", P(pasta, "mix_48k.wav"), "-ar", "44100", "-c:a", "pcm_f32le", P(pasta, "mix_44k.wav")])
                    nomes[i] = os.path.join(ent, f"v{i:03d}.wav")
                    try: os.link(P(pasta, "mix_44k.wav"), nomes[i])
                    except OSError: shutil.copy2(P(pasta, "mix_44k.wav"), nomes[i])
                except Exception as e:
                    out[i] = e
            env = dict(os.environ); env["PYTHONIOENCODING"] = "utf-8"
            if not placa: env["CUDA_VISIBLE_DEVICES"] = "-1"   # 03/11: vazio no Windows o audio-separator lia como placa e quebrava ("Invalid device id"); -1 = sem placa
            if nomes:
                subprocess.run([base.ROFO, *[nomes[i] for i in sorted(nomes)], "--output_dir", d, "--output_format", "WAV", "--model_filename",
                                "model_bs_roformer_ep_317_sdr_12.9755.ckpt"] + (["--model_file_dir", base.ROFO_MODELOS] if base.ROFO_MODELOS else []),
                               check=True, env=env, capture_output=True, creationflags=base.SEM_JANELA)
            for i in sorted(nomes):
                pasta = itens[i][1]
                try:
                    vs = [f for f in os.listdir(d) if f.startswith(f"v{i:03d}_") and "vocal" in f.lower()]
                    if not vs: raise RuntimeError("o BS-Roformer não devolveu a voz deste vídeo")
                    base.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(d, vs[0]), "-ar", "48000", "-ac", "2", "-c:a", "pcm_f32le",
                              parcial(pasta, "voz_48k.wav")])
                    x, _ = sf.read(P(pasta, "mix_48k.wav"), dtype="float32", always_2d=True)
                    v_, _ = sf.read(parcial(pasta, "voz_48k.wav"), dtype="float32", always_2d=True)
                    n = min(len(x), len(v_))
                    sf.write(parcial(pasta, "resto_48k.wav"), x[:n] - v_[:n], 48000, subtype="FLOAT")
                    os.replace(parcial(pasta, "resto_48k.wav"), P(pasta, "resto_48k.wav")); os.replace(parcial(pasta, "voz_48k.wav"), P(pasta, "voz_48k.wav"))
                    os.remove(P(pasta, "mix_44k.wav"))
                except Exception as e:
                    out[i] = e
        # 2/2 música × efeitos: um BandIt pra todos os que faltam
        falta = [i for i in vivos() if not os.path.exists(P(itens[i][1], "efeitos_48k.wav"))]
        if falta:
            log(f"separação 2/2: música × efeitos (BandIt Plus) — {len(falta)} vídeo(s) com o modelo carregado uma vez")
            ent, sai = os.path.join(tmp, "bandit_in"), os.path.join(tmp, "bandit")
            os.makedirs(ent)
            for i in falta:
                shutil.copy2(P(itens[i][1], "resto_48k.wav"), os.path.join(ent, f"v{i:03d}.wav"))
            cmd = [base.PY_CINE, os.path.join(base.CINE, "modelos-teste", "bancada", "rodar_msst_stub.py"),
                   "--model_type", "bandit", "--config_path", os.path.join(base.CINE, "msst", "configs", "config_dnr_bandit_bsrnn_multi_mus64.yaml"),
                   "--start_check_point", os.path.join(base.CINE, "modelos-teste", "bandit_plus", "model_bandit_plus_dnr_sdr_11.47.chpt"),
                   "--input_folder", ent, "--store_dir", sai]
            if not placa: cmd.append("--force_cpu")
            subprocess.run(cmd, check=True, capture_output=True, creationflags=base.SEM_JANELA)
            import librosa
            for i in falta:
                pasta = itens[i][1]
                try:
                    pa = os.path.join(sai, f"v{i:03d}")
                    mf = [f for f in os.listdir(pa) if "music" in f.lower() and f.endswith(".wav")][0]
                    mus, sr = sf.read(os.path.join(pa, mf), dtype="float32", always_2d=True)
                    if sr != 48000: mus = librosa.resample(mus.T, orig_sr=sr, target_sr=48000).T
                    r, _ = sf.read(P(pasta, "resto_48k.wav"), dtype="float32", always_2d=True); n = min(len(r), len(mus))
                    sf.write(parcial(pasta, "musica_48k.wav"), mus[:n], 48000, subtype="FLOAT")
                    sf.write(parcial(pasta, "efeitos_48k.wav"), r[:n] - mus[:n], 48000, subtype="FLOAT")
                    os.replace(parcial(pasta, "musica_48k.wav"), P(pasta, "musica_48k.wav")); os.replace(parcial(pasta, "efeitos_48k.wav"), P(pasta, "efeitos_48k.wav"))
                except Exception as e:
                    out[i] = e
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for i in vivos():
        out[i] = {k: P(itens[i][1], k + "_48k.wav") for k in ("mix", "voz", "resto", "musica", "efeitos")}
    return out


def rodar_varios(As, ctx, trabalho=None):
    """o lote: a separação PELO MODELO de vários vídeos (os de stems entregues vão pelo rodar() de sempre) → [resultado ou exceção]"""
    from . import preparo
    out, fazer = [None] * len(As), []
    for i, A in enumerate(As):
        s = preparo.caminho(A, "som48k")
        if not s: out[i] = {"sem_som": True, "stems": {}}
        else: fazer.append(i)
    res = separar_varios([(preparo.caminho(As[i], "som48k"), As[i].dir("separacao")) for i in fazer], ctx.placa, ctx.log, trabalho)
    for i, st in zip(fazer, res):
        out[i] = st if isinstance(st, Exception) else \
            {"sem_som": False, "stems": {k: os.path.relpath(v, As[i].pasta).replace("\\", "/") for k, v in st.items()}}
    return out


def versao_entregue(stems):
    """a «versão» da separação que veio PRONTA = a assinatura dos arquivos: outra voz/música → outra versão → o que depende dela refaz"""
    import hashlib
    from ..armazem import assinatura
    return "entregue-" + hashlib.sha1("|".join(f"{k}={assinatura(v)}" for k, v in sorted(stems.items())).encode()).hexdigest()[:10]


def completar(stems):
    """voz é obrigatória; o resto (tudo menos a voz) sai do que veio: resto, ou música (+ efeitos somados)"""
    st = {k: os.path.abspath(v) for k, v in (stems or {}).items() if v}
    if "voz" not in st:
        raise SystemExit("stems entregues sem a voz (voz=<arquivo>)")
    for k, v in st.items():
        if not os.path.exists(v): raise SystemExit(f"stem «{k}» não existe: {v}")
    if "resto" not in st and "musica" not in st:
        raise SystemExit("stems entregues sem o resto (resto=<arquivo> ou musica=<arquivo>)")
    if "efeitos" not in st and ("resto" in st) != ("musica" in st):
        # só voz + UM arquivo: ele é o resto E a música (01/11: «voz+musica» e «voz+resto» do mesmo arquivo davam versões diferentes e a
        # ficha da /sonoplastia remedia o V009 inteiro à toa)
        st["resto"] = st["musica"] = st.get("resto") or st.get("musica")
    return st


def entregar(A, stems, log=base.log):
    """01/11: voz e música que vieram PRONTAS (os stems da edição) valem como a separação — nenhum modelo roda, os arquivos são ligados
    (hardlink; noutro disco, cópia) em pecas\\separacao\\<versão>\\ e o resto das peças (fala com cada palavra no ms, rótulos, sinal…)
    roda em cima deles e fica GUARDADO como qualquer peça. Antes a /sonoplastia --stems chamava as funções soltas e jogava a medida fora."""
    import numpy as np, soundfile as sf
    from . import preparo
    st = completar(stems)
    d = os.path.join(A.dir("separacao"), versao_entregue(stems)); os.makedirs(d, exist_ok=True)
    out = {}
    for k, src in st.items():
        dst = os.path.join(d, k + os.path.splitext(src)[1].lower())
        if not os.path.exists(dst):
            try: os.link(src, dst)
            except OSError: shutil.copy2(src, dst)
        out[k] = dst
    if "resto" not in out:
        if "efeitos" in out:
            m, sr = sf.read(out["musica"], dtype="float32", always_2d=True); e, sr2 = sf.read(out["efeitos"], dtype="float32", always_2d=True)
            if sr != sr2: raise SystemExit("música e efeitos entregues em taxas diferentes")
            n = max(len(m), len(e)); r = np.zeros((n, max(m.shape[1], e.shape[1])), "float32"); r[:len(m), :m.shape[1]] += m; r[:len(e), :e.shape[1]] += e
            out["resto"] = os.path.join(d, "resto.wav"); sf.write(out["resto"], r, sr, subtype="FLOAT")
        else:
            out["resto"] = out["musica"]                     # só voz + música: o resto É a música
    if "mix" not in out and preparo.caminho(A, "som48k"):
        out["mix"] = preparo.caminho(A, "som48k")
    dur = A["preparo"].get("duracao") or 0
    avisos = []
    for k in ("voz", "resto"):
        dk = sf.info(out[k]).duration
        if dur and abs(dk - dur) > 0.1:
            avisos.append(f"{k} tem {dk:.2f} s e o vídeo {dur:.2f} s")
    for a in avisos: log("  aviso:", a)
    return {"sem_som": False, "entregue": {k: v for k, v in st.items()}, "avisos": avisos,
            "stems": {k: os.path.relpath(v, A.pasta).replace("\\", "/") for k, v in out.items()}}


def rodar(A, ctx):
    from . import preparo
    if getattr(ctx, "stems", None):
        return entregar(A, ctx.stems, ctx.log)
    s = preparo.caminho(A, "som48k")
    if not s:
        return {"sem_som": True, "stems": {}}
    st = separar(s, A.dir("separacao"), ctx.placa, ctx.log)
    return {"sem_som": False, "stems": {k: os.path.relpath(v, A.pasta).replace("\\", "/") for k, v in st.items()}}


def stem(A, nome):
    """caminho absoluto do stem (mix, voz, resto, musica, efeitos); None se o vídeo não tem som"""
    r = A["separacao"].get("stems", {}).get(nome)
    return os.path.join(A.pasta, r.replace("/", os.sep)) if r else None
