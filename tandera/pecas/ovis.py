# -*- coding: utf-8 -*-
"""OVIS: o retrato VÍDEO + SOM de cada trecho de 4 s (Ovis-Omni-Embedding-3B, Alibaba; base Qwen2.5-Omni-3B) — a FUNDAÇÃO da busca
do catálogo (venceu o PE-AV no servidor: 73,6% top10). Cada trecho entra como vídeo (2 q/s, 224×224 por quadro) com o áudio junto
(use_audio_in_video: imagem e som alinhados no tempo). Retrato = estado final no último token (formato qwen2_5_omni_emb do ms-swift).
Mesmo cálculo do motor do servidor (lote que divide ao meio em OutOfMemory, empty_cache por vídeo, processador preparando o próximo
lote enquanto a placa roda). No PC (5070, 12 GB, o Whisper do ditado na placa): a precisão e o lote saem da MEDIDA
(ver LEIA-ME: «Ovis no PC»); TANDERA_OVIS_PRECISAO=bf16|8bit|4bit e TANDERA_OVIS_LOTE mudam na mão."""
import os, subprocess
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from .. import base

os.environ.setdefault("FORCE_QWENVL_VIDEO_READER", "decord")
REPO = "ATH-MaaS/Ovis-Omni-Embedding-3B"
TRECHO_S = 4.0
SISTEMA = "Represent the user's input."
FPS = 2.0
MAX_PIX = 224 * 224
PRECISAO_PC = "8bit"         # medido 01/11 no V009 (24 trechos): 8 bits lote 4 = 0,34 s/trecho, placa 8,9 GB no total, cos 0,991 × bf16.
LOTE_PC = 4                  # bf16 = 0,27 s mas 11,2 GB no total (passa do teto); 4 bits = 0,27 s, 7,1 GB, cos 0,953 (perde retrato)
_m = {}


def carregar(precisao="bf16", dev="cuda"):
    k = (precisao, dev)
    if k not in _m:
        import torch
        from huggingface_hub import snapshot_download
        from transformers import Qwen2_5OmniProcessor, Qwen2_5OmniThinkerForConditionalGeneration
        pasta = os.path.join(snapshot_download(REPO, allow_patterns=["model/*"]), "model")
        proc = Qwen2_5OmniProcessor.from_pretrained(pasta)
        kw = {"torch_dtype": torch.bfloat16}
        if precisao in ("8bit", "4bit") and dev == "cuda":
            from transformers import BitsAndBytesConfig
            kw["quantization_config"] = (BitsAndBytesConfig(load_in_8bit=True) if precisao == "8bit" else
                                         BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16))
            kw["device_map"] = {"": 0}
            m = Qwen2_5OmniThinkerForConditionalGeneration.from_pretrained(pasta, **kw).eval()
        else:
            m = Qwen2_5OmniThinkerForConditionalGeneration.from_pretrained(pasta, **kw).to(dev).eval()
        # o extrator de áudio completa todo som até 300 s; o trecho é de 4 s → máximo 5 s (medido 30/10: retrato idêntico, cos = 1,0)
        fe = proc.feature_extractor
        fe.chunk_length = 5; fe.n_samples = 5 * fe.sampling_rate; fe.nb_max_frames = fe.n_samples // fe.hop_length
        proc.tokenizer.padding_side = "left"
        _m.clear(); _m[k] = (proc, m, dev)
    return _m[k]


def soltar():
    _m.clear(); base.liberar_torch()


def cortar(video, pasta, dur, threads=2):
    """trechos de 4 s com som (h264 baixo + aac 16 kHz), pro modelo ler vídeo e áudio do mesmo arquivo"""
    os.makedirs(pasta, exist_ok=True); out, t = [], 0.0
    while t < dur - 0.5:
        d = min(TRECHO_S, dur - t); p = os.path.join(pasta, f"{len(out):05d}.mp4")
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-threads", str(threads), "-ss", f"{t:.3f}", "-t", f"{d:.3f}", "-i", video,
               "-threads", str(threads), "-vf", "scale='if(gt(iw,ih),448,-2)':'if(gt(iw,ih),-2,448)'", "-r", "10", "-c:v", "libx264",
               "-preset", "ultrafast", "-crf", "28", "-c:a", "aac", "-ac", "1", "-ar", "16000", p]
        # 07/11: um pedaço CORROMPIDO do vídeo (2026_C0024, h264 com erro) derrubava o Ovis do vídeo inteiro → tenta de novo
        # descartando o quadro quebrado; se ainda falhar, pula SÓ esse trecho de 4 s (o resto do vídeo fica com retrato)
        try:
            base.run(cmd)
        except Exception:
            try:
                i = cmd.index("-ss"); base.run(cmd[:i] + ["-fflags", "+discardcorrupt", "-err_detect", "ignore_err"] + cmd[i:])
            except Exception:
                t += TRECHO_S; continue
        if not os.path.exists(p) or os.path.getsize(p) < 1000:
            t += TRECHO_S; continue
        out.append((p, t, t + d)); t += TRECHO_S
    return out


def _entrada(proc, mp4):
    from qwen_omni_utils import process_mm_info
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", mp4, "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                       capture_output=True, creationflags=base.SEM_JANELA)
    pcm = np.frombuffer(r.stdout, dtype=np.float32) if r.stdout else np.zeros(16000, np.float32)
    if len(pcm) < 1600: pcm = np.zeros(16000 * int(TRECHO_S), np.float32)          # trecho mudo: silêncio do mesmo tamanho
    conv = [{"role": "system", "content": [{"type": "text", "text": SISTEMA}]},
            {"role": "user", "content": [{"type": "video", "video": mp4, "fps": FPS, "max_pixels": MAX_PIX, "min_pixels": 112 * 112}]}]
    return proc.apply_chat_template(conv, add_generation_prompt=True, tokenize=False) + "<|endoftext|>", process_mm_info(conv, use_audio_in_video=False)[2][0], pcm


def retratos(trechos, precisao="bf16", lote=4, dev="cuda", log=None):
    import torch
    proc, m, dev = carregar(precisao, dev)

    @torch.no_grad()
    def um_lote(itens):
        x = proc(text=[t for t, _, _ in itens], audio=[a for _, _, a in itens], videos=[v for _, v, _ in itens], return_tensors="pt",
                 padding=True, use_audio_in_video=True).to(dev)
        for k, v in x.items():
            if torch.is_tensor(v) and v.is_floating_point(): x[k] = v.to(torch.bfloat16)
        o = m(**x, use_audio_in_video=True, output_hidden_states=True, return_dict=True, logits_to_keep=1)
        return torch.nn.functional.normalize(o.hidden_states[-1][:, -1].float(), dim=-1).cpu().numpy()

    def seguro(itens):
        try:
            return list(um_lote(itens))
        except torch.OutOfMemoryError:
            torch.cuda.empty_cache()
            if len(itens) == 1: raise
            h = len(itens) // 2
            if log: log(f"ovis: o lote de {len(itens)} não coube na placa — divide ao meio")
            return seguro(itens[:h]) + seguro(itens[h:])
    emb = []
    with ThreadPoolExecutor(4) as pool:
        fut = [pool.submit(_entrada, proc, p) for p, _, _ in trechos]
        for i in range(0, len(fut), lote):
            emb.extend(seguro([f.result() for f in fut[i:i + lote]]))
    return np.array(emb, np.float32).reshape(-1, 2048)


def texto(frases, precisao="bf16", dev="cuda",
          instrucao="Find the video moment that matches the description, considering both what is seen and what is heard."):
    """frase(s) → retrato no mesmo espaço dos trechos (pra busca)"""
    import torch
    proc, m, dev = carregar(precisao, dev); out = []
    for f in frases:
        conv = [{"role": "system", "content": [{"type": "text", "text": instrucao}]}, {"role": "user", "content": [{"type": "text", "text": f}]}]
        x = proc(text=proc.apply_chat_template(conv, add_generation_prompt=True, tokenize=False) + "<|endoftext|>", return_tensors="pt", padding=True).to(dev)
        with torch.no_grad():
            o = m(**x, output_hidden_states=True, return_dict=True, logits_to_keep=1)
        out.append(torch.nn.functional.normalize(o.hidden_states[-1][0, -1].float(), dim=-1).cpu().numpy())
    return np.stack(out)


def _precisao_lote(ctx):
    return (os.environ.get("TANDERA_OVIS_PRECISAO") or (PRECISAO_PC if ctx.perfil == "pc" else "bf16"),
            int(os.environ.get("TANDERA_OVIS_LOTE") or (LOTE_PC if ctx.perfil == "pc" else 16)))


def aquecer(ctx):
    carregar(_precisao_lote(ctx)[0], "cuda" if ctx.placa else "cpu")


def rodar(A, ctx):
    from . import preparo
    p = A["preparo"]; mp4 = preparo.caminho(A, "leve480")
    if not mp4: return {"trechos": 0}
    precisao, lote = _precisao_lote(ctx)
    tr = cortar(mp4, os.path.join(A.dir("ovis"), "trechos"), p["duracao"])
    emb = retratos(tr, precisao, lote, "cuda" if ctx.placa else "cpu", ctx.log)
    np.savez_compressed(os.path.join(A.dir("ovis"), "retratos.npz"), emb=emb.astype(np.float16), t0=np.array([x[1] for x in tr]), t1=np.array([x[2] for x in tr]))
    for f in os.listdir(os.path.join(A.dir("ovis"), "trechos")): os.remove(os.path.join(A.dir("ovis"), "trechos", f))
    if not base.SEGURAR:                       # no lote o Ovis fica na placa pro próximo vídeo (o lote solta no fim da peça)
        soltar()
    return {"trechos": len(tr), "precisao": precisao, "lote": lote, "arquivo": "pecas/ovis/retratos.npz", "dim": 2048}
