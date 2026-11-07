# -*- coding: utf-8 -*-
"""PREPARO: abre o vídeo UMA vez e tira tudo que as outras peças leem (vindo do motor do servidor de 01/11, com os 3 consertos que o
catálogo pediu pra conferir na entrega):
  1. GIRO: -noautorotate -display_rotation 0 antes do -i e giro à mão (transpose por (−rotação) % 360) logo depois do scale
     (vídeo de iPhone em pé saía de lado e esticado);
  2. SOM: a 1ª trilha com codec que o ffmpeg abre (nunca -map 0:a / 0:a:0: o áudio espacial da Apple vem como «none»);
  3. vídeo > 60 s = select periódico; filtro complexo falhou = refaz saída por saída; arquivo sem imagem = sem quadros.
Sai (pecas\\preparo\\): q1\\00001.jpg… (1 quadro/s, lado menor 720) · mini\\0.jpg… (2/s, 256) · leve480.mp4 (com som) ·
fala16k.wav (mono) · som48k.wav (estéreo, float) · e o meta (fps, quadros, tamanho já girado, folga do AAC).
PLACA (02/11, trazido do lote do RunPod): a placa ABRE o vídeo (NVDEC) e, se falhar, o processador abre como sempre.
  PC: a placa só abre; o quadro desce inteiro (hwdownload) e o processador reduz com o MESMO filtro — saída igual byte a byte à do
      processador (medido: 4K AV1 de um cliente, VP9, H.264 e HEVC 10 bits girados), então a versão NÃO sobe. 4K AV1 de 176 s: 10,3 s e 51 s
      de processador × 11,9 s e 137 s. Só com a placa avisada no Medidor (a análise tem peça de placa) e o Premiere fechado; arquivo que
      começa com pré-rolo (pacote de tempo negativo) ou cujos 12 primeiros quadros saem diferentes da placa vai pelo processador (num
      corte -c copy a placa perdeu o 2º quadro e a cópia 480p saía 1 quadro adiantada). TANDERA_NVDEC=0 desliga.
  SERVIDOR: a placa abre E reduz (scale_cuda) e da mesma leitura saem os quadros pequenos dos cortes e do sinal (ver abaixo)."""
import json, os, shutil, subprocess, time

from .. import base

FPS_MINI = 2
_NV = None
import threading  # noqa: E402
_TRAVA = threading.Lock()


def _nvdec():
    """a placa abre vídeo? (o mesmo teste do Flynder — fly-brutos-teste\\servidor_teste\\motor.py, _nvdec_funciona: um vídeo de 1 s
    gerado aqui, aberto e reduzido na placa). Uma vez por processo. TANDERA_NVDEC=0 desliga."""
    global _NV
    with _TRAVA:                           # prova no WSL: 3 preparos juntos (threads) — um via «não» enquanto o outro ainda testava
        if _NV is None:
            ok = False
            if os.environ.get("TANDERA_NVDEC", "1") != "0":
                import tempfile
                t = os.path.join(tempfile.gettempdir(), f"_teste_nvdec_{os.getpid()}.mp4")
                try:
                    base.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:d=1", "-c:v", "libx264",
                              "-pix_fmt", "yuv420p", t])
                    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-hwaccel", "cuda", "-hwaccel_output_format", "cuda", "-i", t,
                                        "-vf", "scale_cuda=320:180:format=nv12,hwdownload,format=nv12", "-f", "null", "-"], capture_output=True, text=True,
                                       creationflags=base.SEM_JANELA)
                    ok = r.returncode == 0 and "Failed setup" not in r.stderr and "NO_DEVICE" not in r.stderr
                except Exception:
                    ok = False
                finally:
                    try: os.remove(t)
                    except OSError: pass
            _NV = ok
        return _NV


# PC (02/11): o formato em que o quadro aberto pela placa desce (só os medidos iguais byte a byte; outro = o processador abre)
_DESCE = {"yuv420p": "nv12", "yuv420p10le": "p010le"}


def _placa_pc(ctx):
    """PC: a placa abre o vídeo só se esta análise já avisou a placa no Medidor (motor: placa_avisada — com --sem-placa, ou só peças de
    processador, não avisa e o preparo fica no processador) e o Premiere continua fechado"""
    return bool(getattr(ctx, "placa_avisada", False)) and not base.premiere_aberto() and _nvdec()


def _prerolo(v):
    """o 1º pacote de vídeo começa com tempo negativo (pré-rolo descartado: corte -c copy fora do quadro-chave)? sem tempo = não arrisca"""
    o = base.ffprobe(v, "-select_streams", "v:0", "-show_entries", "packet=pts", "-read_intervals", "%+#1", "-of", "csv=p=0").split()
    try: return int(o[0]) < 0
    except (ValueError, IndexError): return True


def _inicio(v, hw, vf, n=12):
    """os tempos (pts) dos n primeiros quadros que saem desse jeito de abrir"""
    import re
    r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-noautorotate", *hw, "-i", v, "-map", "0:v:0", "-frames:v", str(n), "-vf", vf,
                        "-fps_mode", "passthrough", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       creationflags=base.SEM_JANELA)
    return [int(x) for x in re.findall(r"n:\s*\d+ pts:\s*(-?\d+)", r.stderr)] if r.returncode == 0 else None


def _por_que_nao_placa(v, desce):
    """PC: None = a placa pode abrir este arquivo; senão o motivo (vai pelo processador, a saída é a mesma)"""
    if not desce: return "formato de quadro que não foi medido igual na placa"
    if _prerolo(v): return "começa com pré-rolo (pacote de tempo negativo)"
    a, b = _inicio(v, [], "showinfo"), _inicio(v, ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"], f"hwdownload,format={desce},showinfo")
    if not a or a != b: return f"os primeiros quadros da placa saem diferentes ({(b or [])[:4]} × {(a or [])[:4]})"
    return None


def _primeiro_pts(v, hw):
    import re
    vf = "hwdownload,format=nv12,showinfo" if hw else "showinfo"
    r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", *hw, "-noautorotate", "-i", v, "-map", "0:v:0", "-frames:v", "3", "-vf", vf,
                        "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"n:\s*0 .*?pts_time:\s*([-\d.]+)", r.stderr)
    return float(m.group(1)) if m else None


def _recolocar(v, fps, raw):
    """os quadros pequenos da placa → no número de quadro do jeito de sempre (ver o preparo). → quantos buracos foram preenchidos
    (None = não deu pra conferir: sem tempos, ou vídeo de quadros/s variável — fica como veio)"""
    import numpy as np
    try:
        ts = [float(l.split()[1]) for l in open(raw["c48"] + ".pts") if len(l.split()) == 2]
        t0 = _primeiro_pts(v, [])
        if not ts or t0 is None or not fps: return None
        idx = np.array([int(round((t - t0) * fps)) for t in ts])
        if len(idx) > 1 and np.mean(np.diff(idx) == 1) < 0.98: return None        # quadros/s variável: o número não sai do tempo
        if idx[0] == 0 and np.all(np.diff(idx) == 1): return 0
        n = int(idx.max()) + 1
        fonte = np.zeros(n, int); j = 0
        for i in range(n):                                   # cada número → o último quadro entregue com número ≤ i
            while j + 1 < len(idx) and idx[j + 1] <= i: j += 1
            fonte[i] = j
        for k, c in raw.items():
            t = {"c48": 48 * 27 * 3, "c96": 96 * 54, "m170": 96 * 170}[k]
            q = np.fromfile(c, np.uint8); q = q[: q.size // t * t].reshape(-1, t)
            q[np.minimum(fonte, len(q) - 1)].tofile(c + ".tmp"); os.replace(c + ".tmp", c)
        return int(n - len(set(fonte.tolist())))
    except Exception:
        return None


def _raw(A):
    """onde ficam os quadros pequenos (fora da pasta da análise: são grandes e não voltam pro PC) — só no servidor (TANDERA_TRABALHO)"""
    tr = os.environ.get("TANDERA_TRABALHO")
    if os.name == "nt" or not tr or os.environ.get("TANDERA_RAW", "1") == "0": return None
    d = os.path.join(tr, "_raw", os.path.basename(A.pasta)); os.makedirs(d, exist_ok=True)
    return {k: os.path.join(d, k + ".raw") for k in ("c48", "c96", "m170")}


def raw(A, nome, w, h, c=1):
    """os quadros pequenos que o preparo tirou da mesma leitura (None se não há: o PC, ou outra máquina fez o preparo)"""
    import numpy as np
    r = (A.get("preparo") or {}).get("raw") or {}
    p = r.get(nome)
    if not p or not os.path.exists(p): return None
    q = np.fromfile(p, np.uint8); t = w * h * c
    q = q[: q.size // t * t]
    return q.reshape(-1, h, w, c) if c > 1 else q.reshape(-1, h, w)


def _dims(v, lado):
    j = json.loads(base.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                             "stream=width,height,avg_frame_rate,r_frame_rate,nb_frames:stream_side_data=rotation", "-of", "json", v]))["streams"][0]
    w, h = j["width"], j["height"]
    rot = next((int(float(s["rotation"])) for s in j.get("side_data_list", []) if "rotation" in s), 0)
    giro = {90: "transpose=clock,", 270: "transpose=cclock,", 180: "hflip,vflip,"}.get((-rot) % 360, "")
    n, _, dd = (j.get("r_frame_rate") or j.get("avg_frame_rate") or "0/1").partition("/"); fps = float(n) / float(dd or 1) if float(dd or 1) else 0
    if w >= h: W, H = max(2, round(w * lado / h / 2) * 2), lado
    else: W, H = lado, max(2, round(h * lado / w / 2) * 2)
    em_pe = abs(rot) in (90, 270)
    return dict(W=W, H=H, giro=giro, fps=fps, rot=rot, largura=h if em_pe else w, altura=w if em_pe else h, nb=int(j.get("nb_frames") or 0))


def foto(A):
    """FOTO (02/11, pista bruto — o preparar_foto do motor do catálogo, que foi pro Gu): abre (HEIC do iPhone também, com o pillow-heif),
    endireita pela orientação da câmera, lê data, aparelho e GPS de dentro dela e gera o que o vídeo gera pras peças de imagem: q1\\00001.jpg
    (lado menor 720: rostos, texto, imagem), mini\\0.jpg (256), foto1600.jpg (o que o diário manda pro Gemini). Sem som, sem cópia 480p."""
    from PIL import Image, ImageOps
    try:
        import pillow_heif; pillow_heif.register_heif_opener()
    except ImportError:
        pass
    P = A.dir("preparo")
    with Image.open(A.video) as im0:
        ex = im0.getexif(); sub = ex.get_ifd(0x8769); gi = ex.get_ifd(0x8825)
        im = ImageOps.exif_transpose(im0).convert("RGB")
    W, H = im.size
    data = str(sub.get(36867) or ex.get(306) or "").strip()              # DateTimeOriginal / DateTime: «2025:02:19 10:01:30»
    gps = ""
    try:
        if gi and 2 in gi and 4 in gi:
            dms = lambda v_, r: (float(v_[0]) + float(v_[1]) / 60 + float(v_[2]) / 3600) * (-1 if r in ("S", "W") else 1)   # noqa: E731
            gps = f"{dms(gi[2], gi.get(1, 'N')):+.4f}{dms(gi[4], gi.get(3, 'E')):+.4f}/"
    except Exception:
        pass

    def lado(img, maior):
        f = maior / max(img.size); return img if f >= 1 else img.resize((max(1, round(img.size[0] * f)), max(1, round(img.size[1] * f))))
    menor = 720 / min(W, H)
    (im if menor >= 1 else im.resize((round(W * menor), round(H * menor)))).save(os.path.join(P, "q1", "00001.jpg"), quality=92)
    lado(im, 256).save(os.path.join(P, "mini", "0.jpg"), quality=80)
    lado(im, 1600).save(os.path.join(P, "foto1600.jpg"), quality=86)
    return {"tipo": "foto", "duracao": 0, "tem_imagem": True, "tem_som": False, "trilha_som": None, "fps": 1, "quadros": 1,
            "largura": W, "altura": H, "q1": 1,
            "criado": (data[:10].replace(":", "-") + ("T" + data[11:16] if len(data) >= 16 else "")) if data else None,
            "aparelho": " ".join(x for x in (str(ex.get(271) or "").strip(), str(ex.get(272) or "").strip()) if x), "gps": gps,
            "arquivos": {"q1": "pecas/preparo/q1", "mini": "pecas/preparo/mini", "leve480": None, "fala16k": None, "som48k": None,
                         "foto": "pecas/preparo/foto1600.jpg"}}


def rodar(A, ctx):
    v = A.video; P = A.dir("preparo")
    for d in ("q1", "mini"):
        shutil.rmtree(os.path.join(P, d), ignore_errors=True); os.makedirs(os.path.join(P, d))
    from ..pistas import eh_foto
    if eh_foto(v): return foto(A)
    fmt = json.loads(base.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", v]))
    dur = round(float((fmt.get("format") or {}).get("duration") or 0), 3)
    tags = (fmt.get("format") or {}).get("tags") or {}
    tem_imagem = any(s.get("codec_type") == "video" for s in fmt["streams"])
    trilhas = [s for s in fmt["streams"] if s.get("codec_type") == "audio"]
    boa = next((s for s in trilhas if s.get("codec_name") not in (None, "", "none", "unknown")), None)
    som = f"0:{boa['index']}" if boa else None
    folga = 0.0
    if boa and boa.get("codec_name") == "aac" and not int(boa.get("initial_padding") or 0):
        folga = 1024 / float(boa.get("sample_rate") or 48000)          # o áudio do export AAC vem ~21 ms atrasado (régua, 17/10)
    meta = {"duracao": dur, "tem_imagem": tem_imagem, "tem_som": bool(som), "trilha_som": som, "codec_som": boa.get("codec_name") if boa else None,
            "folga_aac_s": round(folga, 6), "criado": tags.get("com.apple.quicktime.creationdate") or tags.get("creation_time") or "",
            "aparelho": " ".join(x for x in (tags.get("com.apple.quicktime.make"), tags.get("com.apple.quicktime.model")) if x)}
    if not tem_imagem:
        meta.update(fps=0, quadros=0)
    else:
        D = _dims(v, 720)
        meta.update(fps=D["fps"], largura=D["largura"], altura=D["altura"], rotacao_metadado=D["rot"],
                    quadros=D["nb"] or int(round(dur * D["fps"])))
        f30 = "fps=30," if D["fps"] > 31 else ""
        esc = lambda L: f"scale='if(gt(iw,ih),-2,{L})':'if(gt(iw,ih),{L},-2)'"          # noqa: E731
        ramos = (f"split=3[a][c][e];[a]{esc(480)}[s480];[c]fps=1[q1];"
                 f"[e]fps={FPS_MINI},scale='if(gt(iw,ih),256,-2)':'if(gt(iw,ih),-2,256)'[mini]")
        leve = os.path.join(P, "leve480.mp4")
        com_som = ["-map", som] if som else []
        saidas = ["-map", "[s480]", *com_som, "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-c:a", "aac", "-ac", "1", "-b:a", "96k",
                  "-movflags", "+faststart", leve + ".tmp.mp4",
                  "-map", "[q1]", "-q:v", "3", os.path.join(P, "q1", "%05d.jpg"),
                  "-map", "[mini]", "-q:v", "6", os.path.join(P, "mini", "m%06d.jpg")]
        entrada = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-noautorotate", "-display_rotation", "0", "-i", v]
        # PC (02/11): a placa só ABRE; o quadro desce inteiro e o filtro é o MESMO do processador (saída igual byte a byte: a versão fica)
        if os.name == "nt" and _placa_pc(ctx):
            vs = next(s for s in fmt["streams"] if s.get("codec_type") == "video")
            desce = _DESCE.get(vs.get("pix_fmt"))
            nao = _por_que_nao_placa(v, desce)
            if nao:
                meta["placa_nao_abriu"] = nao
            else:
                try:
                    t0 = time.monotonic()
                    base.run(entrada[:-2] + ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"] + entrada[-2:] +
                             ["-filter_complex", f"[0:v]hwdownload,format={desce},{f30}scale={D['W']}:{D['H']},{D['giro']}format=yuv420p,{ramos}"] + saidas)
                    meta["aberto"] = "NVDEC (a placa abre, o processador reduz igual) · uma leitura"; meta["abrir_s"] = round(time.monotonic() - t0, 1)
                except RuntimeError as e:
                    meta.setdefault("abrir_falhou", []).append(f"NVDEC: {str(e)[-200:]}")
                    for d in ("q1", "mini"):
                        shutil.rmtree(os.path.join(P, d), ignore_errors=True); os.makedirs(os.path.join(P, d))
        # SERVIDOR (lote RunPod 01/11): o 4K é lido UMA vez — pelo chip da placa (NVDEC, reduz na placa)
        # quando dá — e da mesma leitura saem também os quadros pequenos que os CORTES (48×27 cor, 96×54 cinza) e o SINAL (96×170 cinza)
        # liam abrindo o vídeo de novo (no piloto: preparo + cortes = 378 s com a placa a 1%, tudo decodificando AV1 no processador)
        raw = _raw(A)                       # os quadros pequenos (TANDERA_RAW=0: não — ex. a 1ª passada do tutorial, que não corta)
        if os.name != "nt" and (raw or _nvdec()):
            ramos_raw = ("split=2[base][rw];[rw]split=3[r1][r2][r3];[r1]scale=48:27:flags=bilinear,format=rgb24[c48];"
                         "[r2]scale=96:54:flags=bilinear,format=gray[c96];[r3]scale=96:170:flags=bilinear,format=gray[m170];[base]") if raw else ""
            saidas_raw = ["-map", "[c48]", "-fps_mode", "passthrough", "-stats_enc_pre", raw["c48"] + ".pts", "-stats_enc_pre_fmt", "{n} {t}",
                          "-f", "rawvideo", raw["c48"] + ".tmp",
                          "-map", "[c96]", "-fps_mode", "passthrough", "-f", "rawvideo", raw["c96"] + ".tmp",
                          "-map", "[m170]", "-fps_mode", "passthrough", "-f", "rawvideo", raw["m170"] + ".tmp"] if raw else []
            jeitos = []
            if _nvdec():
                jeitos.append(("NVDEC (placa abre e reduz) · uma leitura", ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"],
                               f"[0:v]scale_cuda={D['W']}:{D['H']}:format=nv12,hwdownload,format=nv12,"))
            if raw: jeitos.append(("processador · uma leitura", [], f"[0:v]scale={D['W']}:{D['H']},"))
            for nome, hw, ini in jeitos:
                try:
                    t0 = time.monotonic()
                    base.run(entrada[:-2] + hw + entrada[-2:] +
                             ["-filter_complex", f"{ini}{D['giro']}{ramos_raw}{f30}format=yuv420p,{ramos}"] + saidas + saidas_raw)
                    meta["aberto"] = nome; meta["abrir_s"] = round(time.monotonic() - t0, 1)
                    if not raw: break
                    for k, c in raw.items(): os.replace(c + ".tmp", c)
                    if hw:
                        # prova no WSL (01/11): num trecho AV1 a placa NÃO entregou o 2º quadro (pts 1001) que o processador entrega → todo
                        # corte saía 1 quadro adiantado. O tempo de cada quadro entregue foi gravado (-stats_enc_pre); cada um volta pro
                        # NÚMERO que teria no jeito de sempre (vídeo de quadros/s fixo: (t − t do 1º quadro do processador) × fps) e o buraco
                        # é preenchido com o quadro anterior (corte nunca cai num quadro repetido: a diferença dele é 0).
                        meta["nvdec_repostos"] = _recolocar(v, D["fps"], raw)
                    try: os.remove(raw["c48"] + ".pts")
                    except OSError: pass
                    meta["raw"] = dict(raw, n=os.path.getsize(raw["c48"]) // (48 * 27 * 3))
                    break
                except RuntimeError as e:
                    meta.pop("aberto", None)
                    meta.setdefault("abrir_falhou", []).append(f"{nome}: {str(e)[-200:]}")
                    for d in ("q1", "mini"):
                        shutil.rmtree(os.path.join(P, d), ignore_errors=True); os.makedirs(os.path.join(P, d))
        try:
            if meta.get("aberto"): pass
            else:
                t0 = time.monotonic()
                base.run(entrada + ["-filter_complex", f"[0:v]{f30}scale={D['W']}:{D['H']},{D['giro']}format=yuv420p,{ramos}"] + saidas)
                meta["aberto"] = "uma leitura (filtro complexo)"; meta["abrir_s"] = round(time.monotonic() - t0, 1)
        except RuntimeError:
            # plano C: uma saída por vez (vídeo de menos de 1 s não dá quadro de 1/s e o filtro derrubava tudo)
            for d in ("q1", "mini"):
                shutil.rmtree(os.path.join(P, d), ignore_errors=True); os.makedirs(os.path.join(P, d))
            base.run(entrada + ["-vf", f"{f30}{D['giro']}{esc(480)}", "-map", "0:v:0", *com_som] + saidas[saidas.index("-c:v"):saidas.index(leve + ".tmp.mp4") + 1])
            for vf, resto in ((f"fps=1,scale={D['W']}:{D['H']},{D['giro']}null", ["-q:v", "3", os.path.join(P, "q1", "%05d.jpg")]),
                              (f"fps={FPS_MINI},{D['giro']}scale='if(gt(iw,ih),256,-2)':'if(gt(iw,ih),-2,256)'", ["-q:v", "6", os.path.join(P, "mini", "m%06d.jpg")])):
                try: base.run(entrada + ["-vf", vf, "-map", "0:v:0"] + resto)
                except RuntimeError: pass
            meta["aberto"] = "saída por saída (o filtro complexo falhou)"
        os.replace(leve + ".tmp.mp4", leve)
        for f in os.listdir(os.path.join(P, "mini")):
            if f.startswith("m"): os.replace(os.path.join(P, "mini", f), os.path.join(P, "mini", f"{int(f[1:7]) - 1}.jpg"))
    if som:
        base.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", v, "-map", som, "-ac", "1", "-ar", "16000", os.path.join(P, "fala16k.wav")])
        base.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", v, "-map", som, "-ac", "2", "-ar", "48000", "-c:a", "pcm_f32le",
                  os.path.join(P, "som48k.wav")])
    meta["q1"] = len(os.listdir(os.path.join(P, "q1"))) if tem_imagem else 0
    meta["arquivos"] = {"q1": "pecas/preparo/q1", "mini": "pecas/preparo/mini", "leve480": "pecas/preparo/leve480.mp4" if tem_imagem else None,
                        "fala16k": "pecas/preparo/fala16k.wav" if som else None, "som48k": "pecas/preparo/som48k.wav" if som else None}
    return meta


def caminho(A, nome):
    """caminho absoluto de um arquivo do preparo (q1, mini, leve480, fala16k, som48k).
    06/11 (ele: «isso aí você pode apagar»): o som48k (a cópia do áudio do vídeo, 25 GB somando tudo) não fica guardado — sumiu, é refeito
    na hora do vídeo, com a MESMA trilha e o mesmo comando do preparo, pra peça que precisar (separação de verdade, som, o «mix»)"""
    r = A["preparo"]["arquivos"].get(nome)
    if not r: return None
    p = os.path.join(A.pasta, r.replace("/", os.sep))
    if nome == "som48k" and not os.path.exists(p):
        trilha = A["preparo"].get("trilha_som")
        if not trilha or not os.path.exists(A.video):
            raise SystemExit(f"o som48k saiu da análise e não dá pra refazer (vídeo {'sem trilha' if not trilha else 'fora do lugar'}): {A.video}")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        base.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", A.video, "-map", trilha, "-ac", "2", "-ar", "48000", "-c:a", "pcm_f32le", p + ".tmp.wav"])
        os.replace(p + ".tmp.wav", p)
        base.log(f"  som48k refeito do vídeo ({os.path.basename(A.video)})")
    return p
