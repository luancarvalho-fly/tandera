# -*- coding: utf-8 -*-
"""O MANIFESTO do Tandera: uma peça por tarefa, cada uma com o MODELO e a VERSÃO. Quando uma peça melhora, muda aqui a versão
(e o código da peça) e todo mundo que chama o Tandera sobe junto; a próxima análise de um vídeo já analisado roda SÓ essa peça
(e as que dependem dela) e soma no que estava guardado.

Regra (01/11/2026, Luan): «o Tandera sempre foi uma coisa só, ele só melhorou». Não existe Tandera 1, 2, 3 vivo: existe o
Tandera, e a versão de cada peça. Melhoria de peça entra AQUI, nunca num motor à parte.

Dois perfis (decisão dele, 31/10): «o melhor que roda no PC fica no PC; o servidor alugado tem a sua própria lista».
  pc        = RTX 5070 12 GB (Windows). Total na placa <= ~10 GB (o Whisper do ditado fica nela).
  servidor  = o PRÓPRIO Tandera no RunPod (Linux, RTX PRO 4500; 01/11 «panelas de som»: servidor\\preparar_tandera.sh monta, servidor\\
              rodar_lote.py roda a fila): preparo, cortes, separação, fala, batida, música, rótulos, sinal, texto, ovis, olho.
              Ficam SÓ NO PC: entonação, câmera, corpo, boca (OpenFace pelo WSL), rostos, imagem, som, diário, busca, efeitos, pisada
              (não foram pedidas pro lote de som, e cada uma traz repositório/pesos/chave próprios que o instalador não monta).
              02/11 (B6): o motor do CATÁLOGO da Fly (fly-brutos-teste\\servidor_teste\\motor.py) foi pro Gu; o que ele fazia na
              análise virou a PISTA «bruto» daqui (tandera\\pistas.py), pro Flynder LOCAL do Luan. Um motor só.
Cada peça: o_que · modelo · versao · onde (placa/cpu/nuvem) · depende (as peças cuja saída ela usa) · perfis · vram_gb (medido no PC).
`padrao`=False: só roda quando pedida (--pecas) — cara demais pra todo vídeo ou depende de coisa de fora."""

VERSAO_MOTOR = "2026-11-02"

PECAS = {
    "preparo": dict(
        o_que="abre o vídeo UMA vez: meta, giro à mão, 1ª trilha de som que abre, quadros 1/s (720), miniaturas 2/s, cópia 480p, som 16k/48k",
        modelo="ffmpeg (-noautorotate + transpose à mão; select periódico > 60 s; saída por saída se o filtro falhar)",
        versao="2026-11-01", onde="cpu", depende=[], perfis=["pc", "servidor"], vram_gb=0),
    "cortes": dict(
        o_que="corte no quadro exato (1ª opinião) + 2ª opinião + possível jump cut",
        modelo="AutoShot (onnx do CUTX, limiar 0,296) + TransNetV2 (transnetv2-pytorch) + diferença de pixel",
        versao="2026-11-01", onde="placa", depende=["preparo"], perfis=["pc", "servidor"], vram_gb=0.6),
    "separacao": dict(
        o_que="separa voz / música / efeitos",
        modelo="BS-Roformer ep317 (audio-separator, placa) → BandIt Plus DnR (música × efeitos)",
        versao="2026-10-21", onde="placa", depende=["preparo"], perfis=["pc", "servidor"], vram_gb=3.3),
    "fala": dict(
        o_que="fala com tempo de cada palavra no milissegundo",
        modelo="Whisper large-v3-turbo (faster-whisper fp16; sem VAD; só os trechos COM SOM pela energia RELATIVA; sem herdar o texto do trecho anterior; filtro de laço) + MMS_FA (torchaudio) + conferência na onda",
        versao="2026-11-01c", onde="placa", depende=["separacao"], perfis=["pc", "servidor"], vram_gb=2.5),
    "entonacao": dict(
        o_que="altura da voz no começo/fim de cada trecho, final (sobe/desce), sílabas por segundo",
        modelo="Praat (parselmouth)", versao="2026-10-18", onde="cpu", depende=["separacao", "fala"], perfis=["pc", "servidor"], vram_gb=0),
    "batida": dict(
        o_que="batidas e tempos fortes no ataque (ms), grade fechada na onda, corte × batida",
        modelo="Beat This! (final0) + ataque na onda + grade reta ajustada",
        versao="2026-10-20", onde="placa", depende=["separacao", "cortes"], perfis=["pc", "servidor"], vram_gb=0.8),
    "musica": dict(
        o_que="seções da música (partes, subidas, drops, viradas, respiros), energia e brilho",
        modelo="medidor de música (Beat This! + librosa: matriz de semelhança, sem modelo de emoção por decisão dele)",
        versao="2026-10-19", onde="placa", depende=["separacao"], perfis=["pc", "servidor"], vram_gb=0.8),
    "camera": dict(
        o_que="movimento de câmera por plano (a CURVA: deslocamento e escala quadro a quadro)",
        modelo="CoTracker3 offline (scaled, autocast fp16 na placa) + geometria (RANSAC)", versao="2026-11-01b", onde="placa", depende=["cortes"],
        perfis=["pc", "servidor"], vram_gb=2.0),
    "corpo": dict(
        o_que="corpo / fase da repetição por plano (articulação que mais mexe, reps, entra/sai)",
        modelo="Sapiens2-1B fp16 (308 pontos) + DETR-R101", versao="2026-11-01", onde="placa", depende=["cortes"],
        perfis=["pc", "servidor"], vram_gb=5.5, padrao=False),
    "pisada": dict(
        o_que="esqueleto quadro a quadro pra achar pisada (ferramenta: o /sonoplastia pisadas.py chama por trecho)",
        modelo="MediaPipe Pose Landmarker heavy (CPU) — venceu RTMW-x (0/4) na F2: 4/4", versao="2026-11-01", onde="cpu",
        depende=[], perfis=["pc"], vram_gb=0, padrao=False, ferramenta=True),
    "rostos": dict(
        o_que="rostos 1/s: caixa, digital (quem é), expressão",
        modelo="SCRFD 10G (buffalo_l) + AdaFace IR-101 WebFace12M + EmotiEffLib enet_b0_8_best_vgaf (ONNX)",
        versao="2026-11-01", onde="placa", depende=["preparo"], perfis=["pc", "servidor"], vram_gb=1.5),
    "boca": dict(
        o_que="boca × fala por plano (a boca mexe junto da fala medida?)",
        modelo="OpenFace 3.0 (WSL Ubuntu-24.04)", versao="2026-10-21", onde="placa", depende=["cortes", "fala"],
        perfis=["pc", "servidor"], vram_gb=1.0, padrao=False),
    "texto": dict(
        o_que="texto na tela (quadros 1/s + 2 por plano)",
        modelo="PaddleOCR 3.7 (PP-OCRv5, paddlepaddle-gpu, ambiente .venv-ocr)", versao="2026-11-01", onde="placa",
        # 02/11 (do lote RunPod de 01/11): o texto.rodar() só lê os quadros 1/s do preparo — com «cortes» aqui o tutorial cortava o vídeo
        # inteiro só pra ler o texto (os cortes do tutorial rodam só nas janelas de exemplo). Vale nos dois perfis; não muda nenhum resultado
        depende=["preparo"], perfis=["pc", "servidor"], vram_gb=1.5),
    "diario": dict(
        o_que="diário do vídeo inteiro (o que se vê E ouve, falas de ouro, reações, momentos, etiquetas, trecho SENSÍVEL); foto = o mesmo diário de 1 item",
        modelo="Gemini Flash, vídeo 480p com som / foto 1600 px (PC: chave grátis, o Flash mais novo que a conta tiver, revezando na cota; "
               "servidor: a mesma chave grátis revezando os Flash, ou a da Fly se GEMINI_API_KEY vier); sem cota ou sem chave, com a placa: "
               "Gemma 4 12B no Ollama (16 quadros com o tempo + a fala + o texto da tela; 04/11)", versao="2026-11-02", onde="nuvem",
        depende=["preparo"], perfis=["pc", "servidor"], vram_gb=0),   # 06/11: servidor também (Luan: «a opção de fazer pelo RunPod ou pelo computador»)
    "busca": dict(
        o_que="índice de busca no diário (frase → momento)",
        modelo="BM25 + Qwen3-Embedding-8B (4 bits na 5070)", versao="2026-11-01", onde="placa", depende=["diario"],
        perfis=["pc", "servidor"], vram_gb=6.0),   # 06/11: servidor também (o mesmo nf4, pra a busca sair igual à do PC)
    "olho": dict(
        o_que="ficha de cada plano (quem, onde, ação, linha do tempo) olhando 2–3 quadros com o tempo escrito",
        modelo="Gemma 4 12B (Ollama gemma4:12b, think desligado, semente fixa)", versao="2026-10-23", onde="placa",
        depende=["cortes", "fala"], perfis=["pc", "servidor"], vram_gb=8.0),
    "ovis": dict(
        o_que="retrato vídeo+som de cada trecho de 4 s (a fundação da busca)",
        modelo="Ovis-Omni-Embedding-3B (ATH-MaaS), trechos de 4 s — PC: 8 bits lote 4 (medido); servidor: bf16 lote 16", versao="2026-11-01",
        onde="placa", depende=["preparo"], perfis=["pc", "servidor"], vram_gb=5.9),
    "som": dict(
        o_que="retrato do som em janelas de 5 s a cada 2,5 s (som parecido, busca por frase em inglês)",
        modelo="CLAP laion/larger_clap_general", versao="2026-11-01", onde="placa", depende=["preparo"],
        perfis=["pc", "servidor"], vram_gb=1.2),
    "rotulos": dict(
        o_que="etiquetas AudioSet do som SEM a voz, a cada 0,5 s (porta, motor, multidão...)",
        modelo="CED-Base (mispeech/ced-base, AudioSet 527) — melhor etiquetador do teste de 01/11 (75% × YAMNet 55%)",
        versao="2026-11-01", onde="placa", depende=["separacao"], perfis=["pc", "servidor"], vram_gb=0.6),
    "imagem": dict(
        o_que="retrato de cada quadro 1/s (imagem parecida, busca por frase)",
        modelo="SigLIP 2 so400m-patch14-384", versao="2026-11-01", onde="placa", depende=["preparo"], perfis=["pc", "servidor"], vram_gb=2.0),
    "sinal": dict(
        o_que="ataques do som (10 ms), picos de movimento, voz soando, vãos sem fala, eventos candidatos (som + imagem + etiqueta)",
        modelo="conta pura (fluxo espectral com limiar local; diferença de quadro); cortes do AutoShot", versao="2026-11-01",
        onde="cpu", depende=["separacao", "cortes", "rotulos", "fala"], perfis=["pc", "servidor"], vram_gb=0),
    "efeitos": dict(
        o_que="qual efeito da biblioteca tocou e onde (arquivo exato)",
        modelo="encaixe na onda contra a biblioteca (8 kHz, placa, coerência no tempo)", versao="2026-10-20", onde="placa",
        depende=["separacao"], perfis=["pc"], vram_gb=3.0, padrao=False),
}

ORDEM = ["preparo", "cortes", "separacao", "fala", "entonacao", "batida", "musica", "rotulos", "sinal", "camera", "corpo", "boca",
         "rostos", "texto", "imagem", "som", "ovis", "diario", "busca", "olho", "efeitos"]
assert set(ORDEM) | {"pisada"} == set(PECAS), "ORDEM e PECAS divergem"

# O que mudou de peça (o histórico curto — o que substituiu o quê). Quem chama o Tandera nunca escolhe a peça velha.
TROCAS = [
    ("cortes", "histograma do Tandera de agosto (perdia 17 de 59 no V009)", "AutoShot + TransNetV2"),
    ("fala", "whisper-server 8178 / large-v3", "large-v3-turbo (empatou com o large-v3 em 31/10: 18,0 × 17,8 de erro) + MMS no ms"),
    ("fala", "2026-11-01: VAD + corte de energia em −40 dB absoluto (comia fala de microfone baixo: 304 palavras)", "2026-11-01b: sem VAD, energia relativa ao arquivo (421 palavras na mesma sessão do Kakashi)"),
    ("rostos", "YuNet + SFace/ArcFace/FaceNet + HSEmotion (catálogo antigo); OpenFace só pra boca", "SCRFD (+30% rostos) + AdaFace (95% × 79%)"),
    ("texto", "PP-OCRv6 no RapidOCR (processador) / RapidOCR do catálogo", "PaddleOCR 3.7 na placa (67% × 50%)"),
    ("olho", "qwen2.5vl:7b (agosto) / Qwen3-VL 8B", "Gemma 4 12B (8/10)"),
    ("rotulos", "AST (MIT/ast-finetuned-audioset) / YAMNet", "CED-Base"),
    ("ovis", "PE-AV (testado no servidor)", "Ovis-Omni 3B (73,6% × 69% top10)"),
    ("busca", "—", "BM25 + Qwen3-Embedding-8B sobre o diário do Gemini (95,4% top50)"),
    ("diario", "2026-11-01: sem «sensivel», só vídeo", "2026-11-02: o pedido do catálogo com «sensivel» (01/11) + foto (B6, pista bruto)"),
]


def padrao():
    """as peças que rodam quando ninguém diz quais"""
    return [p for p in ORDEM if PECAS[p].get("padrao", True)]


def com_dependencias(pecas):
    """as peças pedidas + tudo de que elas dependem, na ORDEM"""
    quero = set()

    def pega(p):
        if p in quero: return
        quero.add(p)
        for d in PECAS[p]["depende"]: pega(d)
    for p in pecas: pega(p)
    return [p for p in ORDEM if p in quero]
