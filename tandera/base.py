# -*- coding: utf-8 -*-
"""O que todas as peças usam: caminhos, log, ffmpeg/ffprobe, quadro pelo número, gravar sem deixar arquivo pela metade, e a PLACA
(Premiere fechado, Ollama descarregado, aviso no Medidor, medida de memória e uso por peça)."""
import json, os, platform, subprocess, sys, threading, time

TANDERA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # apps\TANDERA
MODELOS = os.path.join(TANDERA, "modelos")
ANALISES = os.environ.get("TANDERA_ANALISES") or os.path.join(TANDERA, "analises")
# 01/11 (panelas de som): o Tandera acha as ferramentas pela MÁQUINA em que está. Linux = o servidor (RunPod, ou o WSL na prova): cada
# caminho vem de uma variável TANDERA_*; sem ela, o lugar onde o servidor\preparar_tandera.sh põe as coisas. Medidor, trava GPU_EM_USO e
# Premiere só existem no PC: no Linux ficam desligados.
# PACOTE DA FLY (02/11): no PC do Luan o ramo do Windows tinha os caminhos fixos dele; aqui ele também é TUDO por variável TANDERA_* (o
# jeito do servidor), e sem a variável vale o lugar dentro desta pasta. O MAC hoje cai no ramo de baixo (os.name == "posix", o mesmo do
# Linux) e no perfil "pc" (platform.system() == "Darwin"): o porte cria o 3º caminho aqui, no MESMO código (ver o 00-LEIA-PRIMEIRO).
_env = os.environ.get
if os.name == "nt":
    PY = _env("TANDERA_PY") or os.path.join(TANDERA, ".venv", "Scripts", "python.exe")
    PY_OCR = _env("TANDERA_PY_OCR") or os.path.join(TANDERA, ".venv-ocr", "Scripts", "python.exe")
    # pesos e ambientes que moram fora (não são código do Tandera: são os arquivos dos modelos e os ambientes que os rodam)
    PESOS = _env("TANDERA_PESOS") or os.path.join(TANDERA, "pesos")
    REGUA = _env("TANDERA_REGUA") or os.path.join(PESOS, "regua")   # modelos\ (cotracker3, sapiens2, openface3), repos\ (co-tracker, sapiens2)
    AUTOSHOT = _env("TANDERA_AUTOSHOT") or os.path.join(MODELOS, "autoshot.onnx")
    ROFO = _env("TANDERA_ROFO") or os.path.join(TANDERA, ".venv-sep", "Scripts", "audio-separator.exe")
    ROFO_MODELOS = _env("TANDERA_ROFO_MODELOS") or None          # None = o padrão do audio-separator (C:\tmp\audio-separator-models)
    CINE = _env("TANDERA_CINE") or os.path.join(TANDERA, "terceiros", "separador-cinema")   # msst\ + modelos-teste\ (bandit_plus, bancada)
    PY_CINE = _env("TANDERA_PY_CINE") or os.path.join(TANDERA, ".venv-cine", "Scripts", "python.exe")
    POSE_HEAVY = _env("TANDERA_POSE") or os.path.join(PESOS, "pose_landmarker_heavy.task")
    CED = _env("TANDERA_CED") or os.path.join(PESOS, "ced-base")
    CHAVE_GEMINI = _env("TANDERA_CHAVE_GEMINI") or os.path.join(os.path.expanduser("~"), ".gemini", "chave-api.txt")
    MEDIDOR = _env("TANDERA_MEDIDOR") or ""                      # o Medidor (a agenda da placa) é um app do PC do Luan: sem ele, nada a avisar
    FONTE = _env("TANDERA_FONTE") or r"C:\Windows\Fonts\arialbd.ttf"
elif sys.platform == "darwin":
    # 04/11 (porte do Mac, Gu): o 3º caminho. Igual ao Windows, tudo por variável TANDERA_* e, sem ela, dentro desta pasta (.venv, .venv-sep,
    # pesos/). Sem placa NVIDIA o motor roda no processador (_tem_placa() = False); o MPS entra peça por peça, medido (MAC.md).
    PY = _env("TANDERA_PY") or os.path.join(TANDERA, ".venv", "bin", "python")
    PY_OCR = _env("TANDERA_PY_OCR") or os.path.join(TANDERA, ".venv-ocr", "bin", "python")
    PESOS = _env("TANDERA_PESOS") or os.path.join(TANDERA, "pesos")
    REGUA = _env("TANDERA_REGUA") or os.path.join(PESOS, "regua")
    AUTOSHOT = _env("TANDERA_AUTOSHOT") or os.path.join(MODELOS, "autoshot.onnx")
    ROFO = _env("TANDERA_ROFO") or os.path.join(TANDERA, ".venv-sep", "bin", "audio-separator")
    ROFO_MODELOS = _env("TANDERA_ROFO_MODELOS") or os.path.join(PESOS, "audio-separator")
    CINE = _env("TANDERA_CINE") or os.path.join(TANDERA, "terceiros", "separador-cinema")
    PY_CINE = _env("TANDERA_PY_CINE") or os.path.join(TANDERA, ".venv-cine", "bin", "python")
    POSE_HEAVY = _env("TANDERA_POSE") or os.path.join(PESOS, "pose_landmarker_heavy.task")
    CED = _env("TANDERA_CED") or os.path.join(PESOS, "ced-base")
    CHAVE_GEMINI = _env("TANDERA_CHAVE_GEMINI") or os.path.expanduser("~/.gemini/chave-api.txt")
    MEDIDOR = None
    FONTE = _env("TANDERA_FONTE") or "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
else:
    PESOS = _env("TANDERA_PESOS") or "/root/tandera_pesos"      # o disco local da máquina (o preparar copia do storage pra cá)
    PY = _env("TANDERA_PY") or os.path.join(TANDERA, ".venv", "bin", "python")
    PY_OCR = _env("TANDERA_PY_OCR") or "/root/venv_ocr/bin/python"
    REGUA = _env("TANDERA_REGUA") or os.path.join(PESOS, "regua")
    AUTOSHOT = _env("TANDERA_AUTOSHOT") or os.path.join(PESOS, "autoshot.onnx")
    ROFO = _env("TANDERA_ROFO") or "/root/venv_sep/bin/audio-separator"
    ROFO_MODELOS = _env("TANDERA_ROFO_MODELOS") or os.path.join(PESOS, "audio-separator")
    CINE = _env("TANDERA_CINE") or os.path.join(PESOS, "separador-cinema")   # msst\ + modelos-teste\ (bandit_plus, bancada\rodar_msst_stub.py)
    PY_CINE = _env("TANDERA_PY_CINE") or "/root/venv_cine/bin/python"
    POSE_HEAVY = _env("TANDERA_POSE") or os.path.join(PESOS, "pose_landmarker_heavy.task")
    CED = _env("TANDERA_CED") or os.path.join(PESOS, "ced-base")
    CHAVE_GEMINI = _env("TANDERA_CHAVE_GEMINI") or os.path.expanduser("~/.gemini/chave-api.txt")
    MEDIDOR = None
    FONTE = _env("TANDERA_FONTE") or "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"   # mesma medida da Arial Bold
OLLAMA = _env("TANDERA_OLLAMA") or "http://localhost:11434/api"
SEM_JANELA = 0x08000000 if os.name == "nt" else 0
# 04/11 (porte do Mac, Gu): a placa da Apple (MPS) só nas peças PROVADAS iguais ao processador. Hoje: o BandIt da separação (música ×
# efeitos 57 dB × processador num vídeo de 85 s; 118 s × 342 s). O BS-Roformer já usa o MPS sozinho (audio-separator). Desliga:
# TANDERA_SEM_MPS=1, ou esconder a placa (CUDA_VISIBLE_DEVICES vazio / -1, o jeito do --cpu da sonoplastia).
MAC_MPS = (sys.platform == "darwin" and platform.machine() == "arm64" and not _env("TANDERA_SEM_MPS")
           and _env("CUDA_VISIBLE_DEVICES") not in ("", "-1"))


def sem_janela():
    """sem console (pythonw ou filho escondido da fila): todo programa que ESTE processo abrir sai sem janela.
    04/11: o remendo morava só na fila.py; os filhos dela (python -m tandera, separação, medidor) não tinham, e o Terminal piscava.
    Agora vale em qualquer processo que importe o Tandera sem terminal na frente (no cmd/terminal dele, nada muda)."""
    if os.name != "nt" or getattr(subprocess.Popen.__init__, "_tandera_sem_janela", False):
        return
    if not (sys.stdout is None or not sys.stdout.isatty()) or os.environ.get("TANDERA_SEM_JANELA", "1") != "1":
        return
    orig = subprocess.Popen.__init__

    def init(self, *a, **k):
        if not k.get("creationflags"):
            k["creationflags"] = SEM_JANELA
        return orig(self, *a, **k)
    init._tandera_sem_janela = True
    subprocess.Popen.__init__ = init


sem_janela()


def perfil_da_maquina():
    """pc = o PC do Luan (Windows, RTX 5070); servidor = Linux (RunPod; o WSL na prova das panelas, 01/11)"""
    if os.environ.get("TANDERA_PERFIL"): return os.environ["TANDERA_PERFIL"]
    return "servidor" if platform.system() == "Linux" else "pc"


def log(*a):
    print(time.strftime("[%H:%M:%S]"), *a, flush=True)


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=SEM_JANELA, **kw)
    if r.returncode: raise RuntimeError(f"{os.path.basename(str(cmd[0]))} falhou: {(r.stderr or r.stdout)[-600:]}")
    return r.stdout


def ffprobe(v, *args):
    return subprocess.run(["ffprobe", "-v", "error", *args, v], capture_output=True, text=True, creationflags=SEM_JANELA).stdout.strip()


def salvar_json(arq, v):
    """grava ao lado e troca no fim: processo morto no meio não deixa JSON pela metade"""
    import numpy as np

    def conv(o):
        if isinstance(o, np.integer): return int(o)
        if isinstance(o, np.floating): return float(o)
        if isinstance(o, np.ndarray): return o.tolist()
        if isinstance(o, set): return sorted(o)
        return str(o)
    os.makedirs(os.path.dirname(arq), exist_ok=True)
    tmp = f"{arq}.{os.getpid()}.parcial"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(v, f, ensure_ascii=False, indent=1, default=conv)
    os.replace(tmp, arq)


def ler_audio(caminho, sr=16000, mono=True, ini=None, fim=None):
    """qualquer arquivo → float32 pelo ffmpeg (o leitor do faster-whisper quebra com o pacote av novo)"""
    import numpy as np
    cmd = ["ffmpeg", "-nostdin", "-v", "error"] + (["-ss", f"{ini:.4f}"] if ini else []) + ["-i", caminho] + \
          (["-t", f"{fim - (ini or 0):.4f}"] if fim else []) + ["-vn", "-ac", "1" if mono else "2", "-ar", str(sr), "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True, creationflags=SEM_JANELA)
    return np.frombuffer(r.stdout, np.float32).copy()


def quadro(video, f, fps, w=None):
    """um quadro pelo NÚMERO (-ss (F−0,5)/fps; -ss F/fps dá 1 quadro adiantado), BGR"""
    import cv2, numpy as np
    vf = ["-vf", f"scale={w}:-2"] if w else []
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", "%.5f" % max(0.0, (f - 0.5) / fps), "-i", video, "-frames:v", "1", *vf,
                        "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, creationflags=SEM_JANELA)
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR) if r.stdout else None


def ler_quadros(video, a, b, fps, larg, alt, w=512):
    """quadros a..b−1 pelo NÚMERO, RGB, largura w (altura na proporção, par)"""
    import numpy as np
    H = max(2, int(round(w * alt / larg / 2)) * 2)
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", "%.5f" % max(0.0, (a - 0.5) / fps), "-i", video, "-frames:v", str(max(1, b - a)),
                        "-map", "0:v:0", "-an", "-vf", f"scale={w}:{H}", "-fps_mode", "passthrough", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
                       capture_output=True, creationflags=SEM_JANELA)
    n = len(r.stdout) // (w * H * 3)
    return np.frombuffer(r.stdout[: n * w * H * 3], np.uint8).reshape(n, H, w, 3)


def gravar_jpg(dst, im, q=90):
    import cv2
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst[:-4] + f".parcial{os.getpid()}.jpg"
    cv2.imwrite(tmp, im, [cv2.IMWRITE_JPEG_QUALITY, q]); os.replace(tmp, dst)


def mmss(seg, casas=2):
    seg = max(0.0, float(seg)); m = int(seg // 60)
    return f"{m}:{seg - 60 * m:0{3 + casas}.{casas}f}"


# ------------------------------------------------------------------------------------------------ a placa
def _nvml():
    try:
        import pynvml
        pynvml.nvmlInit(); return pynvml, pynvml.nvmlDeviceGetHandleByIndex(0)
    except Exception:
        return None, None


def placa_agora():
    """memória usada (GB, a placa inteira) e uso (%) agora"""
    nv, h = _nvml()
    if not nv: return None
    m = nv.nvmlDeviceGetMemoryInfo(h); u = nv.nvmlDeviceGetUtilizationRates(h)
    return {"usada_gb": round(m.used / 2 ** 30, 2), "total_gb": round(m.total / 2 ** 30, 2), "uso_pct": u.gpu}


class Medida:
    """mede a placa enquanto uma peça roda (a cada 0,2 s): pico de memória da placa inteira, quanto a peça somou ao que já estava,
    uso médio e máximo. É o número que a regra «placa sempre no máximo, medida» pede."""
    def __init__(self):
        self.nv, self.h = _nvml(); self.am = []; self.ok = True; self.t = None

    def __enter__(self):
        # 01/11 (panelas): cronômetro monotônico — o relógio do WSL pulou ~2 min pra trás no meio da prova; a duração não pode depender dele
        self.antes = placa_agora(); self.t0 = time.monotonic()
        if self.nv:
            self.t = threading.Thread(target=self._loop, daemon=True); self.t.start()
        return self

    def _loop(self):
        while self.ok:
            try:
                m = self.nv.nvmlDeviceGetMemoryInfo(self.h); u = self.nv.nvmlDeviceGetUtilizationRates(self.h)
                self.am.append((m.used / 2 ** 30, u.gpu))
            except Exception:
                pass
            time.sleep(0.2)

    def __exit__(self, *e):
        self.ok = False
        if self.t: self.t.join(timeout=1)
        self.s = time.monotonic() - self.t0
        return False

    def resumo(self):
        r = {"s": round(self.s, 1)}
        if self.am and self.antes:
            pico = max(x[0] for x in self.am); usos = [x[1] for x in self.am]
            r.update({"placa_pico_gb": round(pico, 2), "placa_antes_gb": self.antes["usada_gb"], "peca_somou_gb": round(pico - self.antes["usada_gb"], 2),
                      "uso_medio_pct": round(sum(usos) / len(usos)), "uso_max_pct": max(usos)})
        return r


def nomes_dos_processos():
    """os nomes dos programas abertos, lidos direto do Windows (CreateToolhelp32Snapshot), SEM abrir programa nenhum.
    04/11: o `tasklist` que ficava aqui abriu o Terminal na tela dele a cada bloco da fila («não quero essa tela do terminal piscando»)."""
    if os.name != "nt":
        return []
    import ctypes
    from ctypes import wintypes

    class PE(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", ctypes.c_wchar * 260)]
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snap = k.CreateToolhelp32Snapshot(0x2, 0)              # TH32CS_SNAPPROCESS
    if not snap or snap == wintypes.HANDLE(-1).value:
        return []
    nomes, pe = [], PE()
    pe.dwSize = ctypes.sizeof(PE)
    try:
        ok = k.Process32FirstW(snap, ctypes.byref(pe))
        while ok:
            nomes.append(pe.szExeFile)
            ok = k.Process32NextW(snap, ctypes.byref(pe))
    finally:
        k.CloseHandle(snap)
    return nomes


def premiere_aberto():
    return any("premiere" in n.lower() for n in nomes_dos_processos())


def _ollama(rota, corpo=None, timeout=60):
    import urllib.request
    req = urllib.request.Request(f"{OLLAMA}/{rota}", data=json.dumps(corpo).encode() if corpo is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def ollama_carregados():
    try:
        return [m["name"] for m in _ollama("ps")["models"]]
    except Exception:
        return []


def ollama_descarrega(modelo=None):
    """tira da placa (o mesmo que `ollama stop`): um modelo, ou todos os carregados"""
    for m in ([modelo] if modelo else ollama_carregados()):
        try: _ollama("generate", {"model": m, "keep_alive": 0})
        except Exception: pass


class Placa:
    """UM trabalho de placa por vez: Premiere fechado, a trava GPU_EM_USO.txt (o Medidor escreve), o aviso no Medidor no começo e o
    «terminou» no fim, o Ollama descarregado antes de cada peça que não é o olho."""
    def __init__(self, usar, o_que, dura_min=20, vram=8):
        self.usar, self.o_que, self.dura, self.vram, self.id = usar, o_que, dura_min, vram, None

    def __enter__(self):
        if not self.usar: return self
        if premiere_aberto():
            raise SystemExit("PREMIERE ABERTO — o Tandera não usa a placa com o Premiere aberto. Feche e rode de novo (o que já foi medido fica guardado).")
        trava = _env("TANDERA_TRAVA_PLACA") or os.path.join(TANDERA, "GPU_EM_USO.txt")   # pacote da Fly: era a trava fixa do PC do Luan
        if os.name == "nt" and os.path.exists(trava) and "tandera" not in open(trava, encoding="utf-8", errors="replace").read().lower():
            raise SystemExit("A PLACA ESTÁ EM USO por outro trabalho: " + open(trava, encoding="utf-8", errors="replace").read().strip()[:200])
        if os.name == "nt" and os.path.exists(MEDIDOR) and not os.environ.get("TANDERA_SEM_MEDIDOR"):
            try:
                py = os.environ.get("TANDERA_PY_MEDIDOR") or "python"
                r = subprocess.run([py, MEDIDOR, "comecou", self.o_que, "--gpu", "--vram", str(self.vram), "--dura", str(self.dura),
                                    "--quem", "tandera unico"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   creationflags=SEM_JANELA)
                self.id = (r.stdout.strip().splitlines() or [None])[-1]
            except Exception as e:
                log("aviso: não consegui avisar no Medidor:", e)
        ollama_descarrega()
        return self

    def __exit__(self, *e):
        if self.id:
            subprocess.run([os.environ.get("TANDERA_PY_MEDIDOR") or "python", MEDIDOR, "terminou", self.id], capture_output=True,
                           creationflags=SEM_JANELA)
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass
        return False


def ort_sessao(arq, placa=True, opcoes=None):
    """sessão do onnxruntime NA PLACA de verdade: no Windows o onnxruntime-gpu não acha sozinho as DLLs do CUDA/cuDNN (vêm com o torch)
    e cai no processador sem avisar (01/11: o AutoShot rodou no processador). preload_dlls() carrega as do torch antes."""
    import onnxruntime as ort
    if placa:
        try: ort.preload_dlls()
        except Exception: pass
    s = ort.InferenceSession(arq, providers=([("CUDAExecutionProvider", opcoes or {"arena_extend_strategy": "kSameAsRequested"})] if placa else [])
                             + ["CPUExecutionProvider"])
    if placa and s.get_providers()[0] != "CUDAExecutionProvider":
        log(f"ATENÇÃO: {os.path.basename(arq)} no PROCESSADOR em vez da placa ({s.get_providers()})")
    return s


def liberar_torch():
    try:
        import gc, torch
        gc.collect(); torch.cuda.empty_cache()
    except Exception:
        pass


# ------------------------------------------------------------------------------------------------ o lote (01/11: «um motor só»)
# No LOTE do servidor (tandera\lote.py, chamado pelo servidor\rodar_lote.py) cada peça carrega o modelo UMA vez e passa o bloco de vídeos
# inteiro; só depois o lote solta e vai pra próxima peça. Fora do lote (o PC, tandera.analisar de um vídeo) SEGURAR fica False e
# segurado() só chama o carregar() — exatamente o que cada peça fazia antes.
SEGURAR = False
_SEGURADOS = {}


def segurado(chave, carregar):
    """o modelo da peça: no lote, carrega na 1ª vez e devolve o MESMO nas próximas; fora do lote, carrega toda vez (o jeito de sempre)"""
    if not SEGURAR:
        return carregar()
    if chave not in _SEGURADOS:
        _SEGURADOS[chave] = carregar()
    return _SEGURADOS[chave]


def largar(chave):
    """tira um modelo segurado (o lote, quando ele quebrou no meio: o próximo vídeo carrega de novo)"""
    o = _SEGURADOS.pop(chave, None)
    if hasattr(o, "fechar"):
        try: o.fechar()
        except Exception: pass


def soltar_segurados(manter=()):
    """o lote acabou a peça: solta os modelos (menos os de `manter`, que a próxima peça usa) e limpa a placa"""
    for k in [k for k in _SEGURADOS if k not in manter]:
        largar(k)
    liberar_torch()
