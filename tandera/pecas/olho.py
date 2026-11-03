# -*- coding: utf-8 -*-
"""OLHO local: a FICHA de cada plano (descrição, quem está onde, quem parece falar, linha do tempo) pelo Gemma 4 12B no Ollama
(gemma4:12b, think desligado, temperatura 0,15, semente fixa: a mesma entrada dá a mesma resposta). 2–3 quadros por plano, pelo NÚMERO,
com o tempo escrito no canto; a fala medida do plano vai junto (só pra saber QUANDO alguém fala). A câmera NÃO é com ele (é a curva).
Antes de chamar: tira da placa o que estiver no Ollama e o torch do próprio Tandera (um modelo por vez)."""
import base64, json, os, re, time, urllib.request

import numpy as np

from .. import base

MODELO = "gemma4:12b"
SEMENTE = 20261021
FONTE = base.FONTE           # PC: Arial Bold · Linux: Liberation Sans Bold (mesma medida)


def quadros_do_plano(a, b):
    n = b - a
    if n <= 1: return [a]
    if n <= 4: return [a, b - 1]
    if n <= 12: return [a + 1, b - 2]
    return [a + 2, (a + b) // 2, b - 3]


def quadro_com_tempo(im_bgr, dst, rotulo, largura=512):
    from PIL import Image, ImageDraw, ImageFont
    import cv2
    im = Image.fromarray(cv2.cvtColor(im_bgr, cv2.COLOR_BGR2RGB))
    im = im.resize((largura, max(2, int(round(im.size[1] * largura / im.size[0])))), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    try: f = ImageFont.truetype(FONTE, max(14, largura // 26))
    except OSError: f = ImageFont.load_default()
    l, t, r, b = d.textbbox((6, 6), rotulo, font=f); d.rectangle([l - 4, t - 3, r + 4, b + 3], fill=(0, 0, 0)); d.text((6, 6), rotulo, font=f, fill=(255, 255, 255))
    os.makedirs(os.path.dirname(dst), exist_ok=True); im.save(dst, format="JPEG", quality=90)
    return dst


def sem_repeticao(texto):
    out = []
    for l in texto.splitlines():
        vistas, frases = set(), []
        for f in re.split(r"(?<=[.!?])\s+", l):
            k = re.sub(r"\W+", " ", f.lower()).strip()
            if k and k in vistas: continue
            vistas.add(k); frases.append(f)
        out.append(" ".join(frases))
    return "\n".join(out)


def prompt_ficha(cab, n_quadros, falas=None):
    fal = (f"\n\nFALA MEDIDA NO ÁUDIO deste trecho (Whisper + MMS; serve só pra saber QUANDO alguém fala, não QUEM):\n{falas}") if falas else ""
    return f"""{cab}

As {n_quadros} imagens são QUADROS EM ORDEM deste plano (do começo ao fim dele). Cada quadro tem o número, o tempo e o quadro escritos no canto
(ex.: "3 · 0:02.29 · q55" = imagem 3, aos 2,29 s, quadro 55).{fal}

Responda em português, nesta ordem, com estes títulos (seja curto: cada seção uma vez só, sem repetir):
1. DESCRIÇÃO — UM parágrafo de 3 a 5 frases: enquadramento (e se muda), QUEM está no quadro, a ação do começo ao fim, efeitos visuais, lugar e luz.
2. QUEM ESTÁ ONDE — uma linha por personagem: posição no quadro (esquerda/centro/direita, frente/fundo) e de que tempo a que tempo aparece.
3. QUEM FALA — quem parece estar falando (boca aberta ou mexendo) e em que tempo. Você não ouve o som: diga só o que dá para ver.
4. LINHA DO TEMPO — "de X a Y — o que é", com os tempos escritos nos quadros.

Regras: quem não for reconhecível, descreva a aparência sem inventar nome. Descreva SÓ o que está nos quadros, não invente. Não fale do
movimento de câmera (ele é medido à parte). Cite os tempos como estão escritos nos quadros."""


def perguntar(texto, imagens=(), num_predict=700, temperatura=0.15):
    num_ctx = int(min(32768, max(8192, 4096 * np.ceil((len(texto) // 3 + 1100 * len(imagens) + num_predict + 200) / 4096))))
    t0 = time.time()
    corpo = {"model": MODELO, "prompt": texto, "images": [base64.b64encode(open(a, "rb").read()).decode() for a in imagens], "stream": False,
             "keep_alive": "5m", "think": False, "options": {"temperature": temperatura, "num_predict": num_predict, "num_ctx": num_ctx,
                                                             "repeat_penalty": 1.12, "seed": SEMENTE}}
    req = urllib.request.Request(f"{base.OLLAMA}/generate", data=json.dumps(corpo).encode(), headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=1800).read())
    return {"texto": sem_repeticao(r.get("response", "").strip()), "s": round(time.time() - t0, 1), "tokens_entrada": r.get("prompt_eval_count"),
            "tokens_saida": r.get("eval_count"), "modelo": MODELO}


def rodar(A, ctx):
    c, p = A["cortes"], A["preparo"]
    if not p["tem_imagem"]: return {"planos": []}
    fps = c["fps"]; pal = (A.get("fala") or {}).get("palavras") or []
    folga = p.get("folga_aac_s", 0.0)
    base.liberar_torch()
    for m in base.ollama_carregados():
        if m != MODELO: base.ollama_descarrega(m)
    pasta = A.dir("olho"); out = []
    for n, (a, b) in enumerate(c["planos"], 1):
        ims = []
        for k, f in enumerate(quadros_do_plano(a, b), 1):
            q = base.quadro(A.video, f, fps)
            if q is None: continue
            ims.append(quadro_com_tempo(q, os.path.join(pasta, f"p{n:03d}_{k}_q{f}.jpg"), f"{k} · {base.mmss(f / fps)} · q{f}"))
        ws = [w for w in pal if a / fps <= w["ini"] - folga < b / fps]
        falas = " ".join(f"[{base.mmss(w['ini'] - folga)}] {w['p']}" if i == 0 or w["ini"] - ws[i - 1]["fim"] > 0.4 else w["p"] for i, w in enumerate(ws)) or None
        cab = f"plano {n} de {len(c['planos'])} · de {base.mmss(a / fps)} a {base.mmss(b / fps)} · vídeo de {base.mmss(p['duracao'])}"
        r = perguntar(prompt_ficha(cab, len(ims), falas), ims, 1600)
        out.append({"plano": n, "de_q": a, "ate_q": b, "quadros": [os.path.relpath(i, A.pasta).replace("\\", "/") for i in ims], **r})
        if ctx.log and n % 10 == 0: ctx.log(f"olho: {n}/{len(c['planos'])} planos")
    if not base.SEGURAR:                       # no lote o Gemma fica no Ollama pro próximo vídeo (o lote tira no fim da peça)
        base.ollama_descarrega(MODELO)
    return {"planos": out, "modelo": MODELO}


def aquecer(ctx):
    """o lote: sobe o Gemma no Ollama uma vez (pedido vazio só carrega o modelo)"""
    base.liberar_torch()
    for m in base.ollama_carregados():
        if m != MODELO: base.ollama_descarrega(m)
    base._ollama("generate", {"model": MODELO, "keep_alive": "10m"}, timeout=900)


def soltar():
    base.ollama_descarrega(MODELO)
