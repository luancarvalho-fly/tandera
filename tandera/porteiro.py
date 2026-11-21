# -*- coding: utf-8 -*-
"""O PORTEIRO da placa (20/11/2026, otimização Fase 1, itens 2 e 3). Só biblioteca padrão: o DUBX, o Freak, o Kakashi e o Flynder
importam com o Python que tiverem (sys.path → apps\\TANDERA; `from tandera import porteiro`).

A ordem dele (20/11 ~17h20): «é pra rodar tudo na placa de video po» · «com o Premiere aberto... E sem o Premiere, os dois tem que usar
full a placa de vídeo... Quem tem que saber essa lógica é você, pra isso ser nativo... É o modo padrão» · «tem que funcionar mesmo eu
usando o Premiere».

Como decide (a cada pedido, ~1 ms):
- mede a memória LIVRE da placa agora (NVML, a mesma conta do nvidia-smi, sem abrir programa);
- o pedido cabe na livre menos a folga (MARGEM_MIB)? → placa. O Premiere aberto NÃO manda ninguém pro processador: quem decide é a
  memória que sobra de verdade (o Premiere em uso ocupa ~9,4 de 12 GB; sobra ~2,6 GB e o que couber ali roda na placa);
- não cabe? → primeiro solta o que é NOSSO (modelos quentes do motor residente, modelo parado no Ollama que não é o do ditado) e espera
  um pouco outro trabalho nosso terminar; ainda não cabe → processador, com o aviso (`motivo`) pra tela da ferramenta mostrar.
  NUNCA deixa derramar pra memória comum (fica 4–14× mais lento, medido em 20/11: Ovis 15 → 213 s).
- trabalho de FUNDO (fila da noite, lote, análise que o Claude soltou sozinho — `fundo()`): continua com a regra 9 — só com o Premiere
  FECHADO ou PARADO (`agenda.py premiere-uso`), nunca com ele editando.
Cada decisão vai pro porteiro.log (trabalho\\porteiro.log), pra medir depois."""
import ctypes, json, os, subprocess, sys, threading, time

AQUI = os.path.dirname(os.path.abspath(__file__))
TANDERA = os.path.dirname(AQUI)
LOG = os.path.join(TANDERA, "trabalho", "porteiro.log")
MEDIDOR_DIR = os.environ.get("TANDERA_MEDIDOR") or ""   # pacote da Fly: o MEDIDOR é do PC do Luan; sem ele o porteiro olha só a memória livre
OLLAMA = os.environ.get("TANDERA_OLLAMA") or "http://127.0.0.1:11434/api"
MARGEM_MIB = 700            # folga: o Windows, o navegador e o desenho da tela variam ~0,5 GB de um segundo pro outro
PULO_PREMIERE_MIB = 5200    # o Premiere aberto e parado pula +5,1 GB de uma vez quando ele dá play (fase0\vram\RELATORIO.md)
ABRIR_PLACA_MIB = 214       # 21/11: abrir a placa num processo novo (contexto CUDA + cuBLAS), medido (fase3\ovis\contexto_cuda.txt)
OLLAMA_DO_DITADO = ("qwen2.5:7b",)   # o modelo que o ditado (OpenWhispr) usa pra limpar o texto: só sai se não tiver outro jeito
SEM_JANELA = 0x08000000 if os.name == "nt" else 0
_trava = threading.Lock()


def _anota(t):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%d/%m %H:%M:%S ") + t + "\n")
    except OSError:
        pass


# ------------------------------------------------------------------ a memória da placa
class _Mem(ctypes.Structure):
    _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong), ("used", ctypes.c_ulonglong)]


_NVML = None


def _nvml():
    """o NVML (a biblioteca do driver que o nvidia-smi usa) aberto uma vez; None se não tiver placa NVIDIA"""
    global _NVML
    if _NVML is None:
        try:
            lib = ctypes.CDLL("nvml.dll" if os.name == "nt" else "libnvidia-ml.so.1")
            if lib.nvmlInit_v2() != 0:
                raise OSError("nvmlInit falhou")
            h = ctypes.c_void_p()
            if lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(h)) != 0:
                raise OSError("sem placa 0")
            _NVML = (lib, h)
        except Exception:
            _NVML = False
    return _NVML or None


def vram():
    """{usada, total, livre} em MiB agora (None se não der pra ler)"""
    n = _nvml()
    if n:
        m = _Mem()
        if n[0].nvmlDeviceGetMemoryInfo(n[1], ctypes.byref(m)) == 0:
            return {"usada": m.used // 2 ** 20, "total": m.total // 2 ** 20, "livre": m.free // 2 ** 20}
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"], capture_output=True,
                             text=True, timeout=10, creationflags=SEM_JANELA).stdout.strip().splitlines()[0]
        u, t = (int(x) for x in out.split(","))
        return {"usada": u, "total": t, "livre": t - u}
    except Exception:
        return None


def escondida():
    """quem chamou escondeu a placa (CUDA_VISIBLE_DEVICES vazio ou -1, o jeito do --cpu)"""
    return os.environ.get("CUDA_VISIBLE_DEVICES", None) in ("", "-1")


# ------------------------------------------------------------------ o Premiere
_premiere_cache = [0.0, None]


def premiere():
    """'fechado' · 'em uso' · 'trabalhando' · 'parado' · 'duvida' — a régua do MEDIDOR (agenda.py premiere-uso), lida no máximo a cada 5 s"""
    agora = time.time()
    if _premiere_cache[1] and agora - _premiere_cache[0] < 5:
        return _premiere_cache[1]
    est = "fechado"
    try:
        from . import base
        if base.premiere_aberto():
            est = "duvida"
            if MEDIDOR_DIR not in sys.path:
                sys.path.append(MEDIDOR_DIR)
            import premiere_uso
            est = premiere_uso.situacao().get("estado", "duvida")
    except Exception:
        pass
    _premiere_cache[:] = [agora, est]
    return est


def fundo():
    """trabalho de FUNDO = ninguém está esperando na frente da tela: a fila da noite e o lote (TANDERA_FUNDO=1) e o que o Claude roda
    sozinho num terminal dele (CLAUDECODE=1), menos quando o Claude está rodando a pedido dele agora (TANDERA_PEDIDO_DELE=1)"""
    if os.environ.get("TANDERA_PEDIDO_DELE") == "1":
        return False
    return os.environ.get("TANDERA_FUNDO") == "1" or os.environ.get("CLAUDECODE") == "1"


def liberada_pro_fundo():
    """regra 9 pro trabalho de fundo: placa só com o Premiere fechado ou parado"""
    return premiere() in ("fechado", "parado")


# ------------------------------------------------------------------ quem pode soltar memória
_SOLTADORES = []          # funções que soltam modelos NOSSOS quentes (o motor residente registra a dele): f(mib_que_falta) -> None
pedindo = ""              # quem está pedindo agora (o soltador do motor quente protege o modelo dessa peça)


def ja_quente(peca):
    """MiB que a peça já tem abertos neste processo (o motor quente troca esta função pela dele; fora dele = 0)"""
    return 0


def registrar_soltador(f):
    if f not in _SOLTADORES:
        _SOLTADORES.append(f)


def _ollama(rota, corpo=None, timeout=10):
    import urllib.request
    req = urllib.request.Request(f"{OLLAMA}/{rota}", data=json.dumps(corpo).encode() if corpo is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def soltar_ollama(ate_o_do_ditado=False, menos=()):
    """tira da placa os modelos parados no Ollama (o do ditado só se ate_o_do_ditado); devolve os nomes soltos"""
    soltos = []
    try:
        for m in _ollama("ps").get("models", []):
            nome = m.get("name", "")
            if nome in menos or (nome in OLLAMA_DO_DITADO and not ate_o_do_ditado):
                continue
            try:
                _ollama("generate", {"model": nome, "keep_alive": 0}, timeout=30); soltos.append(nome)
            except Exception:
                pass
    except Exception:
        pass
    return soltos


# ------------------------------------------------------------------ a decisão
def _espera_caber(mib, ate_s):
    """olha a memória livre a cada 0,5 s por até ate_s (o driver leva um instante pra devolver o que foi solto)"""
    t0 = time.monotonic()
    while True:
        v = vram()
        if v and v["livre"] - MARGEM_MIB >= mib:
            return v
        if time.monotonic() - t0 >= ate_s:
            return None
        time.sleep(0.5)


def vaga(mib, quem, espera_s=20, menos_ollama=()):
    """o pedido de `mib` MiB cabe na placa agora? Se não: (1) solta os nossos quentes e o Ollama parado, (2) solta também o modelo do
    ditado no Ollama (ele recarrega sozinho no próximo ditado em ~2 s — o Tandera antigo soltava esse modelo antes de TODA peça),
    (3) espera até espera_s outro trabalho terminar. Medido 20/11 17:55: esperar antes de soltar o do ditado custava ~24 s por peça.
    Devolve (True, motivo) → placa · (False, motivo) → processador; o motivo é a frase pra tela da ferramenta.
    (21/11: é o vaga_escolhe com uma opção só — mesmo passo a passo e mesmo registro de antes.)"""
    ok, motivo, _ = vaga_escolhe([(mib, None)], quem, espera_s=espera_s, menos_ollama=menos_ollama)
    return ok, motivo


def vaga_escolhe(opcoes, quem, espera_s=20, menos_ollama=()):
    """21/11 (otimização Fase 3, ele: «Otimiza tudo»): a peça que pode rodar em TAMANHOS diferentes (o Ovis: lote 4, 2 ou 1) diz
    quanto cada um pede — `opcoes` = [(MiB, valor), ...] — e o porteiro devolve o MAIOR que cabe, sem nunca ir pro processador se o
    menor couber. Passo a passo (o mesmo do vaga):
    0) o maior cabe agora → ele;
    1) não cabe → solta os nossos quentes e o Ollama parado (o que faltar pro MAIOR) → o maior que couber;
    2) nem o MENOR coube → solta também o modelo do ditado (só por isso: não tira o ditado pra ganhar lote) → o maior que couber;
    3) ainda nada → espera até espera_s outro trabalho terminar (pelo menor);
    nada → processador, com o aviso. Devolve (True, motivo, valor) · (False, motivo, None)."""
    opcoes = sorted([(int(max(m, 0)), val) for m, val in opcoes], key=lambda o: -o[0])
    maior, menor = opcoes[0][0], opcoes[-1][0]
    if escondida():
        return False, "quem chamou pediu o processador", None
    if fundo() and not liberada_pro_fundo():
        return False, f"trabalho de fundo com o Premiere {premiere()} (regra 9: a placa é dele enquanto ele edita)", None

    def melhor(v):
        for m, val in opcoes:
            if v and v["livre"] - MARGEM_MIB >= m:
                return m, val
        return None

    def txt(m, val):
        return f"{m} MiB" + (f" (lote {val}; o maior pedia {maior})" if val is not None and m != maior else "")

    with _trava:
        v = vram()
        if v is None:
            return False, "sem placa NVIDIA nesta máquina", None
        b = melhor(v)
        if b and b[0] == maior:
            _anota(f"placa · {quem} · pede {maior} MiB · livre {v['livre']} de {v['total']}")
            return True, f"na placa ({v['livre'] / 1024:.1f} GB livres)", b[1]
        t0 = time.monotonic()
        falta = maior + MARGEM_MIB - v["livre"]
        global pedindo
        pedindo = quem                                      # o motor quente não solta o modelo de quem está pedindo
        for f in list(_SOLTADORES):                         # 1) os nossos quentes (motor residente, quando é ele que pede)
            try: f(falta)
            except Exception: pass
        remoto = 0
        try:                                                #    ou o motor quente (outro processo: DUBX, fila, Freak) solta os dele
            from . import residente
            remoto = residente.soltar_remoto(falta)
        except Exception:
            pass
        soltos = soltar_ollama(menos=menos_ollama)          #    e o Ollama parado que não é o do ditado
        ok = _espera_caber(maior, 1.5 if (soltos or _SOLTADORES or remoto) else 0)
        b = melhor(ok or vram())
        if not b:                                           # 2) nem o menor coube: o do ditado também
            soltos += soltar_ollama(ate_o_do_ditado=True, menos=menos_ollama)
            ok = _espera_caber(menor, 1.5 if soltos else 0)
            b = melhor(ok or vram())
        if not b:                                           # 3) outro trabalho na placa: espera um pouco ele terminar
            ok = _espera_caber(menor, espera_s)
            b = melhor(ok or vram()) if ok else None
        if b:
            livre = (ok or vram() or v)["livre"]
            _anota(f"placa · {quem} · pede {txt(*b)} · livre {livre} depois de soltar {soltos or 'nada'} ({time.monotonic() - t0:.1f} s)")
            return True, f"na placa ({livre / 1024:.1f} GB livres)" + (f" · lote {b[1]}" if b[1] is not None and b[0] != maior else ""), b[1]
        v = vram() or v
        prem = premiere()
        motivo = (f"placa sem memória agora (precisa {menor / 1024:.1f} GB, livres {max(v['livre'] - MARGEM_MIB, 0) / 1024:.1f} GB; "
                  f"Premiere {prem}) — rodando no PROCESSADOR, mais lento")
        _anota(f"PROCESSADOR · {quem} · {motivo}")
        return False, motivo, None


def folga_pra_segurar():
    """quanto dá pra deixar QUENTE (modelo aberto esperando o próximo pedido) sem atrapalhar o Premiere: com o Premiere aberto e parado,
    desconta o pulo do play (+5,1 GB); em uso / trabalhando / dúvida = só o que já está quente e pequeno (o motor decide)"""
    v = vram()
    if v is None:
        return 0
    prem = premiere()
    livre = v["livre"] - MARGEM_MIB
    if prem == "parado":
        livre -= PULO_PREMIERE_MIB
    elif prem in ("em uso", "trabalhando", "duvida"):
        livre = min(livre, 0)
    return max(livre, 0)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    t = time.perf_counter(); v = vram(); dt = time.perf_counter() - t
    print(json.dumps({"vram_mib": v, "leitura_ms": round(dt * 1000, 2), "premiere": premiere(), "fundo": fundo(),
                      "folga_pra_segurar_mib": folga_pra_segurar()}, ensure_ascii=False))
