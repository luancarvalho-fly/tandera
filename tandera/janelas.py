# -*- coding: utf-8 -*-
"""JANELAS DE EXEMPLO — a receita «só nos exemplos» dos tutoriais (lote do som no RunPod, 01/11/2026: servidor\\janelas.py +
receitas.json → tutorial.so_nos_exemplos; no PC desde 02/11). Ele, 01/11 ~21h55: «por que você usaria o separador de voz e música? É só
em alguns lugares... tem que pensar com a cabeça».
  1ª passada no vídeo INTEIRO só com fala, texto da tela e rótulos (CED: a chance de MÚSICA a cada 0,5 s). A separação dessa passada é
     a «entregue» com o PRÓPRIO som do vídeo (voz = resto = mix: custa 0; o falatório do apresentador não passa pelo separador). Vídeo que
     já tem separação de verdade (o separador rodou) fica com ela;
  JANELA DE EXEMPLO = trecho com música (CED musica ≥ 0,5) ou onde a fala chama o exemplo (GATILHOS), vãos < 3 s juntados, 2 s de folga;
  2ª passada (as peças pesadas: cortes, separação, música, batida, sinal, ovis, olho — e a fala/rótulos da própria janela, que o sinal e
     o olho leem) SÓ nas janelas, cortadas do vídeo com o INÍCIO guardado.
A análise de cada janela fica DENTRO da análise do vídeo: <pasta>\\janelas\\<janela>\\ (janela.json: início/fim no vídeo original — o
tempo t da janela = t + inicio_s no vídeo). <pasta>\\janelas.json lista todas, com o motivo e a cobertura. Os cortes (.mkv) ficam em
apps\\TANDERA\\trabalho\\janelas\\<pasta do vídeo>\\ (com a data do vídeo: cortar de novo dá a mesma assinatura e acha a mesma análise).
02/11 (B0, LICOES.md 1): «with» e «without» SAÍRAM dos gatilhos — sozinhos abriram 430 janelas sem música e as janelas cobriram em média
72% de cada vídeo de um curso de som, quando a ideia era só os exemplos (são palavras de toda frase, não chamam exemplo nenhum).
  tandera.cmd exemplos <vídeo> [--so-contar] [--sem-placa] [--sem-olho] [--idioma en]"""
import json, os, re, subprocess, time

from . import base

GATILHOS = ["check this out", "here is", "listen", "before", "after"]
GATILHOS_RUNPOD = GATILHOS + ["without", "with"]          # os de 01/11 (o lote do RunPod): só pra comparar
MUSICA_MIN, JUNTA, FOLGA = 0.5, 3.0, 2.0
PASSADA1 = ["fala", "texto", "rotulos"]                     # receitas.json → tutorial.pecas
PASSADA2 = ["cortes", "separacao", "musica", "batida", "sinal", "ovis", "olho"]   # receitas.json → tutorial.so_nos_exemplos.pecas


def _norm(p):
    return re.sub(r"[^a-z']", "", (p or "").lower())


def _ler(pasta, peca):
    a = os.path.join(pasta, "pecas", peca + ".json")
    if not os.path.exists(a): return None
    r = json.load(open(a, encoding="utf-8"))
    return r.get("resultado", r)


def achar(pasta, musica_min=MUSICA_MIN, junta=JUNTA, folga=FOLGA, gatilhos=None):
    """→ (janelas [{ini, fim, motivos {motivo: n}}], dur). Lê pecas\\rotulos.json e pecas\\fala.json da 1ª passada."""
    gatilhos = GATILHOS if gatilhos is None else gatilhos
    pr = _ler(pasta, "preparo") or {}
    A = json.load(open(os.path.join(pasta, "analise.json"), encoding="utf-8")) if os.path.exists(os.path.join(pasta, "analise.json")) else {}
    dur = float(pr.get("duracao") or (A.get("pecas", {}).get("preparo") or {}).get("duracao") or 0)
    trechos = []
    R = _ler(pasta, "rotulos")
    if R:
        jan = R.get("janela", 1.0)
        for j in R.get("janelas", []):
            if j.get("musica", 0) >= musica_min: trechos.append([j["t"] - jan / 2, j["t"] + jan / 2, "música"])
    F = _ler(pasta, "fala")
    if F:
        pal = F.get("palavras") or []
        ws = [_norm(w.get("p")) for w in pal]
        for i, w in enumerate(pal):
            for g in gatilhos:
                gs = g.split()
                if ws[i:i + len(gs)] == gs:
                    trechos.append([w["ini"], pal[i + len(gs) - 1]["fim"], "fala: " + g]); break
    trechos.sort()
    jan = []
    for a, b, m in trechos:                                   # vãos < 3 s juntados
        if jan and a - jan[-1]["fim"] < junta:
            jan[-1]["fim"] = max(jan[-1]["fim"], b); jan[-1]["motivos"][m] = jan[-1]["motivos"].get(m, 0) + 1
        else:
            jan.append({"ini": a, "fim": b, "motivos": {m: 1}})
    out = []
    for j in jan:                                             # 2 s de folga (e junta o que a folga encostou)
        a, b = max(0.0, j["ini"] - folga), (min(dur, j["fim"] + folga) if dur else j["fim"] + folga)
        if out and a <= out[-1]["fim"]:
            out[-1]["fim"] = max(out[-1]["fim"], b)
            for m, n in j["motivos"].items(): out[-1]["motivos"][m] = out[-1]["motivos"].get(m, 0) + n
        else:
            out.append({"ini": round(a, 3), "fim": round(b, 3), "motivos": dict(j["motivos"])})
    for j in out: j["ini"], j["fim"] = round(j["ini"], 3), round(j["fim"], 3)
    return out, dur


def _sonda(v):
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", v],
                                  capture_output=True, text=True, creationflags=base.SEM_JANELA).stdout or "{}")
    s = (j.get("streams") or [{}])[0]
    return s.get("width"), s.get("height")


def cortar(video, ini, fim, dst, lado=1080, placa=True):
    """o trecho [ini, fim) do vídeo → dst (.mkv: H.264 1080 + FLAC 48 kHz). -ss antes do -i com recodificação = começa no tempo certo
    (o ffmpeg decodifica desde o quadro-chave e descarta). Pela placa (NVDEC + scale_cuda) se dá e se placa=True; senão o processador."""
    w, h = _sonda(video)
    if w and h and min(w, h) > lado:
        W, H = (round(w * lado / h / 2) * 2, lado) if w >= h else (lado, round(h * lado / w / 2) * 2)
    else:
        W, H = w, h
    som = ["-map", "0:a:0?", "-c:a", "flac", "-ar", "48000"]
    cmd0 = ["ffmpeg", "-nostdin", "-v", "error", "-y"]
    # 01/11 23:28 (RunPod som-2): o NVENC daquele ffmpeg pedia driver ≥ 610 e as máquinas tinham 595.91 → o corte caía INTEIRO pro
    # processador (decodificando o 4K AV1 de novo). A placa ABRE e REDUZ (NVDEC + scale_cuda) e o processador só codifica o 1080 (x264
    # ultrafast): 30 s de 4K AV1 = 3,6 s / 7,7 s de CPU × 13,7 s / 49,5 s. -fps_mode cfr: o quadro que a placa pula é repetido (o
    # número do quadro da janela continua = quadro do vídeo − round(início × fps)).
    jeitos = [("placa (NVDEC) + x264", ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"],
               ["-vf", f"scale_cuda={W}:{H}:format=nv12,hwdownload,format=nv12,format=yuv420p", "-fps_mode", "cfr",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-threads", "4"])] if placa else []
    jeitos.append(("processador", [], ["-vf", f"scale={W}:{H}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]))
    erro = ""
    for nome, hw, vid in jeitos:
        r = subprocess.run(cmd0 + hw + ["-ss", f"{ini:.3f}", "-i", video, "-t", f"{fim - ini:.3f}", "-map", "0:v:0", *vid, *som, dst + ".tmp.mkv"],
                           capture_output=True, text=True, creationflags=base.SEM_JANELA)
        if r.returncode == 0:
            os.replace(dst + ".tmp.mkv", dst); return nome
        erro = r.stderr[-300:]
    raise RuntimeError(f"não cortou a janela {ini:.1f}–{fim:.1f}: {erro}")


def cobertura(jan, dur):
    cob = sum(j["fim"] - j["ini"] for j in jan)
    return {"janelas": len(jan), "dur": dur, "cobertura_s": round(cob, 1), "cobertura_pct": round(100 * cob / dur, 1) if dur else None}


def exemplos(video, placa=True, idioma=None, so_contar=False, olho=True, log=base.log):
    """a receita inteira num vídeo do PC: 1ª passada → janelas → 2ª passada em cada janela. → {janelas.json + o que rodou}"""
    from . import motor
    from .armazem import Analise, assinatura, nome_da_pasta
    video = os.path.abspath(video)
    A = Analise(video)
    T = os.path.join(base.TANDERA, "trabalho", "janelas", os.path.basename(A.pasta)); os.makedirs(T, exist_ok=True)
    mt = os.stat(video).st_mtime
    # 1ª passada: a separação entregue = o próprio som (se o vídeo ainda não tem uma separação de verdade)
    stems = None
    if not A.tem("separacao") or str(A.versao("separacao") or "").startswith("entregue-"):
        mix = os.path.join(T, "mix48k.wav")
        if not os.path.exists(mix):
            base.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", video, "-map", "0:a:0", "-ac", "2", "-ar", "48000", "-c:a", "pcm_f32le",
                      "-bitexact", mix + ".tmp.wav"])
            os.replace(mix + ".tmp.wav", mix); os.utime(mix, (mt, mt))
        stems = {"voz": mix, "resto": mix}
    log(f"1ª passada (vídeo inteiro): {', '.join(PASSADA1)}" + (" · separação = o próprio som" if stems else " · separação já feita fica"))
    A = motor.rodar(video, PASSADA1, placa=placa, idioma=idioma, stems=stems, log=log)
    jan, dur = achar(A.pasta)
    c = cobertura(jan, dur)
    log(f"{c['janelas']} janelas de exemplo · {c['cobertura_s']:.0f} de {dur:.0f} s ({c['cobertura_pct']}%)")
    regra = {"musica_min": MUSICA_MIN, "gatilhos": GATILHOS, "junta_s": JUNTA, "folga_s": FOLGA,
             "de": "receitas.json → tutorial.so_nos_exemplos (01/11 ~21h55); sem «with/without» (B0, 02/11)"}
    if so_contar:
        return dict(c, regra=regra, lista=jan)
    pecas2 = [p for p in PASSADA2 if olho or p != "olho"]
    nomes = [os.path.join(T, f"{os.path.splitext(os.path.basename(video))[0][:40]}_j{n:02d}_{j['ini']:.1f}-{j['fim']:.1f}.mkv") for n, j in enumerate(jan, 1)]
    falta = [i for i, d in enumerate(nomes) if not os.path.exists(d)]
    comos = ["já cortada"] * len(jan)
    if falta:
        usar = placa and not base.premiere_aberto()           # com o Premiere aberto o corte vai pelo processador (a saída é outra cópia, não erro)
        from concurrent.futures import ThreadPoolExecutor
        t0 = time.monotonic()
        with base.Placa(usar, f"Tandera: cortando {len(falta)} janelas de {os.path.basename(video)}", dura_min=5, vram=1), \
                ThreadPoolExecutor(4) as ex:                  # 01/11 23:35 (RunPod): 4 cortes ao mesmo tempo (o chip que abre vídeo foi de 31% a 99%)
            feitos = list(ex.map(lambda i: cortar(video, jan[i]["ini"], jan[i]["fim"], nomes[i], placa=usar), falta))
        for i, como in zip(falta, feitos):
            comos[i] = como; os.utime(nomes[i], (mt, mt))
        log(f"{len(falta)} janelas cortadas em {time.monotonic() - t0:.1f} s (4 juntas)")
    lista = []
    for n, (j, clip, como) in enumerate(zip(jan, nomes, comos), 1):
        wp = os.path.join(A.pasta, "janelas", nome_da_pasta(os.path.basename(clip), assinatura(clip)))
        os.makedirs(wp, exist_ok=True)
        jj = os.path.join(wp, "janela.json")
        if not os.path.exists(jj) or como != "já cortada":
            base.salvar_json(jj, {"inicio_s": j["ini"], "fim_s": j["fim"], "motivos": j["motivos"], "video_pc": video, "pasta_do_video": os.path.basename(A.pasta),
                                  "corte": clip, "cortada_pela": como,
                                  "como_ler": "tempo t desta análise = t + inicio_s no vídeo original (quadro q = q + round(inicio_s × fps))"})
        log(f"— janela {n}/{len(jan)}: {j['ini']:.1f}–{j['fim']:.1f} s ({', '.join(f'{k} ×{v}' for k, v in j['motivos'].items())})")
        W = motor.rodar(clip, pecas2, placa=placa, idioma=idioma, pasta=wp, log=log)
        r = W.d["rodadas"][-1]
        lista.append({"n": n, **j, "pasta": os.path.basename(wp), "rodou": sorted(r["rodou"]), "falhou": r["falhou"], "pulou": r["pulou"], "s": r["s"]})
    out = dict(c, regra=regra, janelas=lista, pecas_janela=pecas2, quando=time.strftime("%Y-%m-%d %H:%M:%S"))
    base.salvar_json(os.path.join(A.pasta, "janelas.json"), out)
    log(f"pronto: {len(lista)} janelas analisadas → {os.path.join(A.pasta, 'janelas.json')}")
    return out
