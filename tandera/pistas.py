# -*- coding: utf-8 -*-
"""AS PISTAS do Tandera (B6, 02/11/2026): um motor só, e cada trabalho escolhe a PISTA = quais pistões (peças) ligam. Peça desligada não
carrega modelo nem placa. Ele (01/11 ~19h10): «tudo é uma coisa só, não é para ter dois motores. A não ser se não der para desligar
essas panelas... se der para fazer um motor só, e você sabe quando desligar e ligar um pistão, é isso».
Antes daqui eram dois programas: o Tandera (PC) e o motor do catálogo da Fly (fly-brutos-teste\\servidor_teste\\motor.py, que foi pro
Gu em 02/11). O que aquele motor fazia de próprio na ANÁLISE virou a pista «bruto» (fotos inclusive); baixar do Drive, fila de máquinas
e subir mídia na ARDI eram do RunPod da Fly e não entram (o Flynder do Luan é LOCAL, material dele, na RTX 5070 — 02/11 ~23h30:
«a gente vai usar o Flinder aqui também. Mas de maneira local, no meu PC... não tem nada a ver com o Flinder do Gu»).
As receitas do lote do RunPod (estudo\\reanalise-2026-11-01\\receitas.json) eram as pistas escritas fora do motor: agora moram aqui
(o receitas.json só diz que GRUPO do levantamento vai em que pista).

  tandera.cmd pistas                                  a lista
  tandera.cmd analisar <vídeo ou foto> --pista bruto  as peças da pista (+ as de que dependem; o guardado não roda)
  tandera.cmd fila <fila.json> | --pista X <arquivos/pastas>   vários, peça por peça (tandera\\fila.py)"""
import os

from .manifesto import PECAS, padrao

FOTOS = (".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp")
VIDEOS = (".mp4", ".mov", ".m4v", ".mts", ".mxf", ".mkv", ".avi", ".webm")

PISTAS = {
    "bruto": dict(
        o_que="BRUTO de câmera/celular pro Flynder local (busca no material): o que o motor do catálogo fazia — fala no ms, rostos "
              "(quem + expressão), texto na tela, retrato da imagem e do som, Ovis (a fundação da busca), diário do Gemini e o índice "
              "da busca; cortes porque o bruto do Luan tem take emendado. Sem separação/batida/música (bruto não tem mixagem)",
        pecas=["preparo", "cortes", "fala", "rostos", "texto", "imagem", "som", "ovis", "diario", "busca"],
        fotos=["preparo", "rostos", "texto", "imagem", "diario", "busca"],
        nota="fala depende da separação no manifesto; no bruto a separação ENTREGUE é o próprio som (voz = resto = mix, custa 0), "
             "igual ao motor do catálogo, que transcrevia o som inteiro"),
    "editado": dict(
        o_que="vídeo EDITADO do Luan (Plexus, vlog, cliente, curso): tudo o que o PC roda por padrão, menos o olho (Gemma, ~metade do "
              "tempo de máquina: ele, 01/11 ~20h30, ligou o olho só em tutorial e Kakashi; o diário do Gemini já descreve o vídeo)",
        pecas=[p for p in padrao() if p != "olho"]),
    "plexus-stems": dict(
        o_que="Plexus com os stems da mixagem (separação = os stems, custa 0); efeitos = qual arquivo da biblioteca tocou",
        pecas=["cortes", "fala", "separacao", "musica", "batida", "rotulos", "sinal", "efeitos", "ovis"], idioma="pt",
        stems={"voz": ["PLEXUS", "VOZES"], "musica": ["MUSICAS"], "efeitos": ["SFX", "DESIGNED"]}),
    "plexus": dict(
        o_que="Plexus sem stems (o separador faz voz/música/efeitos)",
        pecas=["cortes", "fala", "separacao", "musica", "batida", "rotulos", "sinal", "efeitos", "ovis"], idioma="pt"),
    "tutorial": dict(
        o_que="tutorial de som de outro criador (ex.: a aula de um curso de som): fala/texto/rótulos no vídeo inteiro, o pesado só nas janelas de exemplo",
        pecas=["fala", "texto", "rotulos"], idioma="en", exemplos=True),
    "trailer": dict(
        o_que="trailer/vídeo de referência de som",
        pecas=["cortes", "fala", "separacao", "musica", "batida", "rotulos", "sinal", "efeitos", "ovis"], idioma="en"),
    "kakashi": dict(
        o_que="sessão do Kakashi (tela + microfone + som do PC prontos): sem separação, cortes nem batida",
        pecas=["fala", "texto", "olho", "rotulos", "ovis"], idioma="pt", video="tela.mp4", stems_kakashi={"voz": "fala.wav", "resto": "pc.wav"}),
}

# TRAVA DO OVIS (03/11, ele: «você deu mole de não ter usado o OVS no RunPod... o OVS é um modelo de embedding... o melhor pra gente»;
# 31/10: «O OVIS É A FUNDAÇÃO... da onde que você tirou que poderia ignorar o Ovis»): toda pista que analisa vídeo liga o Ovis. O tutorial
# liga ele nas janelas de exemplo (janelas.PASSADA2), a decisão dele de 01/11 («o pesado só nos exemplos»).
for _n, _p in PISTAS.items():
    assert _p.get("exemplos") or "ovis" in (_p.get("pecas") or padrao()), f"pista {_n} sem o Ovis (a fundação da busca)"
for _n, _p in PISTAS.items():
    for _x in (_p.get("pecas") or []) + (_p.get("fotos") or []):
        assert _x in PECAS and not PECAS[_x].get("ferramenta"), f"pista {_n}: peça {_x} não existe no manifesto"


def eh_foto(arq):
    return arq.lower().endswith(FOTOS)


def pecas_da(pista, arquivo=None):
    """as peças que a pista liga pra este arquivo (foto liga só as de imagem); None = as padrão do manifesto"""
    if pista not in PISTAS: raise SystemExit(f"pista desconhecida: {pista} (tem: {', '.join(PISTAS)})")
    P = PISTAS[pista]
    if arquivo and eh_foto(arquivo):
        if not P.get("fotos"): raise SystemExit(f"a pista {pista} não lê foto: {os.path.basename(arquivo)}")
        return list(P["fotos"])
    return list(P["pecas"]) if P.get("pecas") else padrao()


def stems_da(pista, arquivo, log=None):
    """stems que a pista entrega prontos pra este arquivo → (stems ou None, peças que caem). No bruto a separação é o PRÓPRIO som
    (voz = resto = o som do vídeo: custa 0; a fala transcreve o som inteiro, como no catálogo) — o mesmo jeito da 1ª passada das janelas
    (janelas.py): wav 48k tirado do vídeo, com a data do vídeo (cortar de novo dá a mesma assinatura). Vídeo que já tem separação de
    verdade fica com ela. Vídeo sem som: sem stems e sem as peças de som (fala, som)."""
    if pista == "kakashi" and arquivo:
        # a sessão do Kakashi já vem separada: microfone (fala.wav) e som do PC (pc.wav) ao lado da tela.mp4
        d = os.path.dirname(os.path.abspath(arquivo)); st = PISTAS["kakashi"]["stems_kakashi"]
        achou = {k: os.path.join(d, v) for k, v in st.items() if os.path.exists(os.path.join(d, v))}
        return (achou, []) if "voz" in achou and "resto" in achou else (None, ["fala", "rotulos"])
    if pista != "bruto" or not arquivo or eh_foto(arquivo): return None, []
    from . import base
    from .armazem import Analise
    video = os.path.abspath(arquivo)
    A = Analise(video)
    if A.tem("separacao") and not str(A.versao("separacao") or "").startswith("entregue-"): return None, []
    T = os.path.join(base.TANDERA, "trabalho", "som-proprio", os.path.basename(A.pasta)); os.makedirs(T, exist_ok=True)
    mix = os.path.join(T, "mix48k.wav")
    if not os.path.exists(mix):
        r = base.ffprobe(video, "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0")
        if not (r or "").strip():
            if log: log(f"{os.path.basename(video)}: sem trilha de som — fala e som ficam de fora")
            return None, ["fala", "som"]
        base.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", video, "-map", "0:a:0", "-ac", "2", "-ar", "48000", "-c:a", "pcm_f32le",
                  "-bitexact", mix + ".tmp.wav"])
        mt = os.stat(video).st_mtime
        os.replace(mix + ".tmp.wav", mix); os.utime(mix, (mt, mt))
    return {"voz": mix, "resto": mix}, []
