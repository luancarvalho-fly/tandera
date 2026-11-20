# -*- coding: utf-8 -*-
"""O TANDERA — o motor de análise de vídeo e som do Luan. UM só, sempre o mais novo (lei dele, 01/11/2026): toda skill e todo app que
analisa vídeo chama ISTO, nunca uma versão com número. Melhoria de peça entra aqui (manifesto.py) e todo mundo sobe junto.

Como biblioteca (de qualquer Python; o que é pesado roda no ambiente do Tandera sozinho):
    import sys; sys.path.insert(0, r"<a pasta do tandera>")
    import tandera
    A = tandera.analisar(r"C:\\...\\video.mp4")                  # as peças padrão; só roda o que falta ou o que mudou de versão
    A = tandera.analisar(video, pecas=["cortes", "fala"])        # só essas (+ as de que elas dependem)
    A["cortes"]["cortes"], A["fala"]["palavras"], A.pasta        # o resultado guardado de cada peça
    tandera.transcrever(r"...\\audio.wav", idioma="pt", dispositivo="cpu")   # só a fala (Kakashi, CORRETOR, ficha --cpu)
    tandera.versao()                                              # o manifesto (peça · modelo · versão)
    tandera.sinal.ataques(wav) / .movimento(video, cortes_s) / .folha(...)   # contas leves, rodam em qualquer Python
Na linha de comando: apps\\TANDERA\\tandera.cmd analisar <vídeo> [--pecas ...]  ·  tandera.cmd versao"""
import json, os, subprocess, sys

from . import base                                   # leve: só biblioteca padrão (o Kakashi importa com o Python do sistema, sem numpy)
from .armazem import Analise, pasta_do_video
from .manifesto import PECAS, ORDEM, TROCAS, VERSAO_MOTOR, padrao

__all__ = ["analisar", "abrir", "transcrever", "rotular", "rotular_varios", "batidas", "dispositivo_auto", "versao", "Analise", "sinal", "PECAS", "ORDEM",
           "padrao", "no_ambiente", "residente"]


def no_ambiente():
    """True se este Python é o do Tandera (as peças pesadas rodam aqui mesmo). O ambiente é o do base.PY: no PC o .venv de sempre; no
    Linux o que TANDERA_PY disser (servidor: /root/venv_tandera)"""
    return os.path.normcase(os.path.realpath(sys.prefix)) == os.path.normcase(os.path.realpath(os.path.dirname(os.path.dirname(base.PY))))


def _cli(args, capturar=False):
    env = dict(os.environ); env["PYTHONIOENCODING"] = "utf-8"
    if os.environ.get("CUDA_VISIBLE_DEVICES", None) in ("", "-1") and "--sem-placa" not in args and args[0] == "analisar":
        args = args + ["--sem-placa"]                   # quem chamou escondeu a placa (ex.: /sonoplastia --cpu): respeita
    # 01/11: sem janela (regra dele: nada de janela na tela dele) — apps sem console (pythonw) chamam isto a cada áudio.
    # Quem tem console (terminal, agente) continua vendo o andamento do `analisar` no mesmo console.
    sem_janela = getattr(subprocess, "CREATE_NO_WINDOW", 0) if (capturar or sys.stdout is None) else 0
    r = subprocess.run([base.PY, "-m", "tandera", *args], cwd=base.TANDERA, env=env, capture_output=capturar, text=True, encoding="utf-8",
                       errors="replace", creationflags=sem_janela)
    if r.returncode:
        raise RuntimeError(f"o Tandera falhou (código {r.returncode})" + (f": {(r.stderr or r.stdout)[-800:]}" if capturar else ""))
    return r.stdout


def dispositivo_auto():
    """'cuda' por padrão, com o Premiere aberto ou fechado (20/11, ele: «é pra rodar tudo na placa de video po... tem que funcionar
    mesmo eu usando o Premiere»). Quem divide a placa com o Premiere é o PORTEIRO (porteiro.vaga), peça por peça, pela memória livre
    de verdade. 'cpu' só quando: quem chamou escondeu a placa (CUDA_VISIBLE_DEVICES vazio), ou é trabalho de FUNDO (fila, lote, o
    Claude sozinho) com ele usando o Premiere (regra 9).
    Antes (até 20/11): 'cpu' sempre que o Premiere estivesse aberto — a rodada de 22 s de 4K ia de 123 s pra 244 s."""
    from . import porteiro
    if porteiro.escondida() or (porteiro.fundo() and not porteiro.liberada_pro_fundo()):
        return "cpu"
    return "cuda"


def analisar(video, pecas=None, perfil=None, refazer=(), placa=True, idioma=None, pasta=None, stems=None):
    """roda (ou relê) a análise do vídeo e devolve a Analise guardada. placa: True (padrão: na placa, com o Premiere aberto ou fechado; o
    porteiro manda pro processador só a peça que não couber na memória livre), False (processador) ou "auto" (= dispositivo_auto()).
    (20/11: antes, com o Premiere aberto, True RECUSAVA e "auto" ia tudo pro processador.)
    stems = {"voz": wav, "resto" ou "musica": wav[, "efeitos", "mix"]} quando a voz/música vieram PRONTAS (01/11): valem como a separação,
    e a fala (cada palavra no ms), os rótulos e o sinal medidos neles ficam GUARDADOS — rodar de novo só lê."""
    if placa == "auto":
        placa = dispositivo_auto() == "cuda"
    # 20/11 (otimização, item 3): o MOTOR QUENTE (tandera\residente.py, porta 7797) de pé = a análise roda nele, com os modelos já
    # abertos (o porteiro decide quanto cabe na placa). Fora do ar / caiu no meio = o jeito de sempre (o que ele já guardou não roda de novo).
    from . import residente
    if residente.usar():
        try:
            residente.analisar_remoto(video, pecas, perfil, refazer, placa and os.environ.get("CUDA_VISIBLE_DEVICES", None) not in ("", "-1"),
                                      idioma, pasta, stems, mostrar=(print if sys.stdout is not None else None))
            return Analise(video, pasta)
        except residente.Caiu:
            pass
    else:
        residente.ligar()                                # não estava de pé: sobe escondido pro PRÓXIMO pedido (este vai do jeito de sempre)
    if no_ambiente():
        from . import motor
        return motor.rodar(video, pecas, perfil, refazer, placa and os.environ.get("CUDA_VISIBLE_DEVICES", None) not in ("", "-1"), idioma, pasta,
                           stems=stems)
    a = ["analisar", os.path.abspath(video)]
    if pecas: a += ["--pecas", ",".join(pecas)]
    if perfil: a += ["--perfil", perfil]
    if refazer: a += ["--refazer", ",".join(refazer)]
    if not placa: a += ["--sem-placa"]
    if idioma: a += ["--idioma", idioma]
    if pasta: a += ["--pasta", os.path.abspath(pasta)]
    for k, v in (stems or {}).items():
        if v: a += ["--stem", f"{k}={os.path.abspath(v)}"]
    _cli(a)
    return Analise(video, pasta)


def frases(A):
    """cada frase com começo e fim NO MILISSEGUNDO (01/11): a mesma receita das legendas e do lip sync — o Whisper só dá o texto, o tempo vem
    das palavras alinhadas pelo MMS_FA e conferidas na onda (peça «fala»). Frase = segmento do Whisper; ini = começo da 1ª palavra, fim = fim
    da ÚLTIMA palavra (onde a energia da voz cai). [{ini, fim, txt, palavras:[{p, ini, fim}], ultima:{p, ini, fim}, como}]
    («como» = mms | whisper (fala rápida demais pro alinhador) | segmento (sem palavra alinhada: o tempo do Whisper, ±0,3 s))"""
    f = A.get("fala") or {}
    segs, pal = f.get("segmentos", []), f.get("palavras", [])
    grupos = [[] for _ in segs]
    for w in pal:                                    # cada palavra vai pra frase mais perto do meio dela
        m = (w["ini"] + w["fim"]) / 2
        if segs:
            i = min(range(len(segs)), key=lambda j: (max(segs[j]["ini"] - m, 0, m - segs[j]["fim"]), j))
            grupos[i].append(w)
    out = []
    for s, ws in zip(segs, grupos):
        if ws:
            ws = sorted(ws, key=lambda w: w["ini"])
            out.append({"ini": ws[0]["ini"], "fim": ws[-1]["fim"], "txt": s["txt"],
                        "palavras": [{"p": w["p"], "ini": w["ini"], "fim": w["fim"]} for w in ws],
                        "ultima": {"p": ws[-1]["p"], "ini": ws[-1]["ini"], "fim": ws[-1]["fim"]},
                        "como": "mms" if all(w.get("como") == "mms" for w in ws) else "whisper"})
        else:
            out.append({"ini": s["ini"], "fim": s["fim"], "txt": s["txt"], "palavras": [], "ultima": None, "como": "segmento"})
    return out


def abrir(video, pasta=None):
    """a análise já guardada (sem rodar nada)"""
    return Analise(video, pasta)


def transcrever(audio, idioma=None, dispositivo="cuda", palavras=False, rapido=False, modelo="turbo", srt=None, max_len=70):
    """só a FALA (Whisper large-v3-turbo do Tandera): {idioma, segmentos:[{ini, fim, txt}], descartados, modelo}.
    rapido=True (01/11): pra resposta na hora (apps de chat e de ditado) — as MESMAS regras do Tandera em cima do motor que já
    está carregado (whisper-server 8178 do ditado); se ele estiver fora do ar, o Whisper do Tandera. Todo app transcreve por AQUI.
    modelo="large" (01/11): o large-v3 da dublagem (DUBX, decisão dele de 23/08), sempre pelo servidor próprio na 8899.
    srt=<caminho>: grava a legenda SRT (max_len ≤ 1 = uma palavra por bloco)."""
    # 20/11 (item 3): o Whisper do Tandera (turbo, na placa) pelo MOTOR QUENTE — já aberto, sem pagar o abrir. O rápido (8178) e o large
    # (8899) já são servidores quentes; o processador pedido de propósito (Kakashi --cpu) fica aqui mesmo.
    from . import residente
    if modelo == "turbo" and not rapido and dispositivo == "cuda" and isinstance(audio, str) and residente.usar():
        try:
            return residente.pedir("/transcrever", {"audio": os.path.abspath(audio), "idioma": idioma, "palavras": palavras,
                                                    "srt": os.path.abspath(srt) if srt else None, "max_len": max_len})["r"]
        except residente.Caiu:
            pass
    if no_ambiente():
        from .pecas import fala
        try:
            if modelo == "large" or rapido:
                r = fala.transcrever_rapido(audio, idioma, dispositivo, palavras or bool(srt), modelo=modelo, max_len=max_len if srt else None)
            else:
                r = fala.transcrever(audio, idioma, dispositivo, palavras or bool(srt))
            if srt:
                open(srt, "w", encoding="utf-8").write(fala.para_srt(r["segmentos"], max_len))
            return r
        finally:
            fala.soltar()
    a = ["fala", os.path.abspath(audio), "--dispositivo", dispositivo, "--json"] + (["--idioma", idioma] if idioma else [])
    a += (["--palavras"] if palavras else []) + (["--rapido"] if rapido else []) + (["--modelo", modelo] if modelo != "turbo" else [])
    a += (["--srt", os.path.abspath(srt), "--max-len", str(int(max_len))] if srt else [])
    return json.loads(_cli(a, capturar=True).strip().splitlines()[-1])


def rotular(wav, dispositivo="cuda"):
    """etiquetas AudioSet (CED-Base, a peça «rotulos») de um arquivo de som qualquer — pra stems que vieram prontos: {janelas:[{t, db, musica, rotulos}]}"""
    from . import residente
    if dispositivo == "cuda" and residente.usar():           # 20/11 (item 3): o CED quente no motor quente
        try:
            return residente.pedir("/rotular", {"wav": os.path.abspath(wav)})["r"]
        except residente.Caiu:
            pass
    if no_ambiente():
        from .pecas import rotulos
        return {"modelo": "mispeech/ced-base", "passo": 0.5, "janela": 1.0, "janelas": rotulos.etiquetar(base.ler_audio(wav, 16000), dispositivo)}
    return json.loads(_cli(["rotular", os.path.abspath(wav), "--dispositivo", dispositivo], capturar=True).strip().splitlines()[-1])


def rotular_varios(wavs, dispositivo="cpu"):
    """o mesmo do rotular() pra muitos arquivos, carregando o CED-Base uma vez só: {caminho: [janelas]}"""
    wavs = [os.path.abspath(w) for w in wavs]
    if not wavs:
        return {}
    if no_ambiente():
        from .pecas import rotulos
        return rotulos.etiquetar_varios(wavs, dispositivo)
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(wavs, f)
    try:
        return json.loads(_cli(["rotular-varios", f.name, "--dispositivo", dispositivo], capturar=True).strip().splitlines()[-1])
    finally:
        os.remove(f.name)


def batidas(wav, dispositivo="cuda"):
    """batidas de um arquivo de som (a peça «batida»: Beat This! + ataque na onda + grade fechada) SEM separar — pra música que já vem
    sozinha: {batidas, tempos_fortes, grade, bpm}"""
    from . import residente
    if dispositivo == "cuda" and residente.usar():           # 20/11 (item 3): o Beat This! quente no motor quente
        try:
            return residente.pedir("/batidas", {"wav": os.path.abspath(wav)})["r"]
        except residente.Caiu:
            pass
    if no_ambiente():
        from .pecas import batida
        b = batida.batidas(wav, dispositivo == "cuda"); g = batida.grade_na_onda(wav, b["batidas"]); base.liberar_torch()
        import numpy as np
        bpm = round(60 / float(np.median(np.diff(b["batidas"]))), 2) if len(b["batidas"]) > 2 else None
        return {**b, "grade": g, "bpm": g.get("bpm") or bpm, "modelo": PECAS["batida"]["modelo"], "versao": PECAS["batida"]["versao"]}
    return json.loads(_cli(["batidas", os.path.abspath(wav), "--dispositivo", dispositivo], capturar=True).strip().splitlines()[-1])


def versao():
    return {"motor": VERSAO_MOTOR, "perfil_desta_maquina": base.perfil_da_maquina(),
            "pecas": {p: {k: PECAS[p].get(k) for k in ("o_que", "modelo", "versao", "onde", "depende", "perfis", "vram_gb")} for p in PECAS}}


# ------------------------------------------------------------------ a TRAVA do Tandera antigo (agosto: tandera.py / sonoro.py na raiz)
_ANTIGOS = {"ouvir", "medir", "ver", "analisa", "escreve_dossie", "FFMPEG", "FFPROBE", "WHISPER_BIN", "MODELO_VISAO", "le_srt", "prepara_entrada",
            "duracao", "tem_video", "porta_viva", "perfis_disponiveis", "carrega_elenco", "NIVEIS_VISAO", "IDIOMAS", "SAIDA_PADRAO", "roda"}


def __getattr__(nome):
    if nome == "sinal":                                  # as contas leves (numpy/OpenCV) só carregam quando alguém pede
        import importlib
        return importlib.import_module(".sinal", __name__)
    if nome in _ANTIGOS:
        raise ImportError(f"«tandera.{nome}» era do Tandera antigo (agosto), que foi DESLIGADO em 01/11/2026 — o Tandera é um só agora. "
                          f"Use tandera.analisar(video, pecas=[...]) / tandera.transcrever(audio) / tandera.sinal (LEIA-ME do apps\\TANDERA).")
    raise AttributeError(nome)
