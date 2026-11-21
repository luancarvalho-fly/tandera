# -*- coding: utf-8 -*-
"""O MOTOR QUENTE do Tandera (20/11/2026, otimização Fase 1, item 3) — UM motor só (ele: «tudo é uma coisa só, não é para ter dois
motores»): um programa escondido (pythonw, liga com o Windows pela pasta Inicializar) que fica de pé na porta 7797 e segura os modelos
QUENTES (abertos na placa) entre um pedido e outro. Atende o Tandera (analisar, fala, rótulos, batidas), o FREAK (ouvir e alinhar a
legenda) e o DUBX (pede pra ele soltar a placa quando precisa dela).

Analogia: antes, cada pedido montava a cozinha inteira, cozinhava e desmontava. Agora a cozinha fica montada; o PORTEIRO (porteiro.py)
olha quanto espaço sobra na bancada (a memória da placa, medida) e tira da bancada o que não cabe.

Regras de memória (12 GB; números medidos em fase0\\vram\\RELATORIO.md):
- Premiere FECHADO: segura quentes até a memória livre medida (menos a folga de 0,7 GB), na ordem de prioridade abaixo.
- Premiere ABERTO (parado, em uso, trabalhando ou dúvida): só o «quente pequeno» (alinhador MMS, rótulos CED, Beat This!, rostos), e
  só o que couber DEPOIS de descontar o pulo do Premiere no play (+5,1 GB) — o porteiro nunca deixa a placa transbordar pra memória
  comum (4–14× mais lento). Não solta tudo a cada play (o cético mostrou que isso anula o ganho): solta pela memória medida.
- Ovis, Gemma (olho), busca e corpo: grandes demais pra ficar — rodam e soltam no fim do pedido.
- 15 min sem pedido: solta tudo e o programa renasce limpo (nem o «crachá» do CUDA fica na placa).
- Outro trabalho travou a placa (o GPU_EM_USO.txt da pasta do Tandera, fila da noite, medição): solta tudo e não segura nada.
- Um pedido de placa por vez (a trava _JOB). O trabalho de FUNDO (a fila, o lote, o Claude sozinho) que chega por aqui leva a marca
  e continua seguindo a regra 9 (porteiro.fundo).
Medido 20/11: o Whisper do Tandera (CTranslate2) SÓ devolve a placa com unload_model() — agora fala.soltar() faz isso (2.153 → 1 MiB);
o Ovis devolve inteiro com ovis.soltar() (5.271 → 6 MiB). Por isso dá pra ser um processo só.

Cliente (biblioteca padrão; o __init__ do Tandera, o FREAK e o porteiro usam): usar(), pedir(rota, corpo), analisar_remoto(...),
soltar_remoto(...), ligar(). Desliga o uso: TANDERA_SEM_RESIDENTE=1.
Ligar na mão (escondido): apps\\TANDERA\\.venv\\Scripts\\pythonw.exe -m tandera.residente   (pasta apps\\TANDERA)"""
import json, os, sys, threading, time, traceback, urllib.request

PORTA = int(os.environ.get("TANDERA_RESIDENTE_PORTA") or 7797)
URL = f"http://127.0.0.1:{PORTA}"
DENTRO = os.environ.get("TANDERA_RESIDENTE") == "1"          # True só dentro do próprio motor quente
OCIOSO_S = 15 * 60                                            # receita do Edu: 15 min parado = solta tudo
TICK_S = 2.0
PISO_EM_USO_MIB = 600                                          # com o Premiere em uso: folga extra acima da do porteiro (ver _excesso)
TRAVA = os.environ.get("TANDERA_TRAVA_PLACA") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "GPU_EM_USO.txt")
AQUI = os.path.dirname(os.path.abspath(__file__))
TANDERA = os.path.dirname(AQUI)
LOG = os.path.join(TANDERA, "trabalho", "residente.log")
SEM_JANELA = 0x08000000 if os.name == "nt" else 0


# ================================================================== CLIENTE (biblioteca padrão)
class Caiu(Exception):
    """o motor quente não respondeu (fora do ar ou caiu no meio): quem chamou faz do jeito antigo"""


_visto = [0.0, False]


def no_ar(timeout=0.4):
    """o motor quente está de pé? (resposta guardada 3 s)"""
    agora = time.time()
    if agora - _visto[0] < 3:
        return _visto[1]
    try:
        with urllib.request.urlopen(URL + "/saude", timeout=timeout) as r:
            ok = json.loads(r.read()).get("nome") == "tandera residente"
    except Exception:
        ok = False
    _visto[:] = [agora, ok]
    return ok


def usar():
    """chamar o motor quente em vez de abrir os modelos aqui? (no PC, fora dele mesmo, sem TANDERA_SEM_RESIDENTE, e de pé)"""
    if DENTRO or os.name != "nt" or os.environ.get("TANDERA_SEM_RESIDENTE") == "1":
        return False
    return no_ar()


def _marcas():
    """o que o pedido carrega de quem chamou: trabalho de fundo (regra 9) e placa escondida (--cpu)"""
    try:
        from . import porteiro
        fundo = porteiro.fundo()
    except Exception:
        fundo = os.environ.get("TANDERA_FUNDO") == "1"
    return {"fundo": bool(fundo), "escondida": os.environ.get("CUDA_VISIBLE_DEVICES", None) in ("", "-1")}


def pedir(rota, corpo=None, timeout=1800):
    """POST JSON → JSON. Fora do ar / caiu = Caiu. Erro do trabalho = RuntimeError com a frase do motor."""
    dados = json.dumps(dict(corpo or {}, **_marcas()), ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(URL + rota, data=dados, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            res = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            res = json.loads(e.read().decode("utf-8"))
        except Exception:
            raise Caiu(f"motor quente respondeu {e.code}")
    except Exception as e:
        _visto[:] = [0.0, False]
        raise Caiu(str(e))
    if not res.get("ok"):
        raise RuntimeError(res.get("erro") or "o motor quente falhou")
    return res


def analisar_remoto(video, pecas=None, perfil=None, refazer=(), placa=True, idioma=None, pasta=None, stems=None, mostrar=None):
    """a análise rodando no motor quente; o andamento (as mesmas linhas do motor) vai pra `mostrar` (print, se tiver console)"""
    corpo = {"video": os.path.abspath(video), "pecas": list(pecas) if pecas else None, "perfil": perfil, "refazer": list(refazer or ()),
             "placa": bool(placa), "idioma": idioma, "pasta": os.path.abspath(pasta) if pasta else None,
             "stems": {k: os.path.abspath(v) for k, v in (stems or {}).items() if v} or None}
    dados = json.dumps(dict(corpo, **_marcas()), ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(URL + "/analisar", data=dados, headers={"Content-Type": "application/json"})
    fim = None
    try:
        with urllib.request.urlopen(req, timeout=6 * 3600) as r:
            for linha in r:
                t = linha.decode("utf-8", "replace").rstrip("\r\n")
                if t.startswith("FIM "):
                    fim = json.loads(t[4:])
                elif t.startswith("LOG ") and mostrar:
                    mostrar(t[4:])
    except Exception as e:
        _visto[:] = [0.0, False]
        raise Caiu(str(e))
    if fim is None:
        raise Caiu("o motor quente fechou a conversa sem terminar")
    if not fim.get("ok"):
        raise RuntimeError(fim.get("erro") or "o Tandera falhou no motor quente")
    return fim


def soltar_remoto(mib=None, tudo=False, timeout=5):
    """pede ao motor quente pra soltar a placa (o porteiro de OUTRO programa precisa de memória). Devolve MiB soltos (estimativa)."""
    if DENTRO or os.name != "nt" or not no_ar():
        return 0
    try:
        return int(pedir("/soltar", {"mib": mib, "tudo": tudo}, timeout=timeout).get("soltou_mib") or 0)
    except Exception:
        return 0


def ligar():
    """sobe o motor quente escondido (pythonw, sem janela), se não estiver de pé. Não espera."""
    if os.name != "nt" or DENTRO or os.environ.get("TANDERA_SEM_RESIDENTE") == "1" or no_ar(0.3):
        return False
    pyw = os.path.join(TANDERA, ".venv", "Scripts", "pythonw.exe")
    if not os.path.exists(pyw):
        return False
    import subprocess
    subprocess.Popen([pyw, "-m", "tandera.residente"], cwd=TANDERA, creationflags=SEM_JANELA | 0x00000008,   # DETACHED_PROCESS
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
    return True


# ================================================================== O MOTOR (só roda dentro do processo do motor quente)
_JOB = threading.Lock()
_estado = {"ultimo_pedido": time.time(), "pedidos": 0, "trabalhando": None, "inicio": time.time(), "torch": False}


def _anota(t):
    try:
        print(time.strftime("[%d/%m %H:%M:%S] ") + t, flush=True)
    except Exception:
        pass


# Os QUENTES: (nome, MiB parado medido/estimado, pequeno?, está segurando?, soltar). A ORDEM é a prioridade de ficar (o 1º fica por último).
# pequeno = None: NUNCA fica (grande demais: solta no fim de todo pedido e é o 1º a sair se uma peça precisar de memória no meio).
# MiB: fase0\vram\RELATORIO.md (MMS medido de novo 20/11 19:51: 1.204) · Whisper 2.155 e Ovis 5.271 (medidos 19:51).
def _quentes():
    from . import base
    from .pecas import fala, imagem, som

    def seg(*prefixos):
        return lambda: any(isinstance(k, tuple) and k[0] in prefixos for k in list(base._SEGURADOS))

    def largar(*prefixos):
        def f():
            for k in [k for k in list(base._SEGURADOS) if isinstance(k, tuple) and k[0] in prefixos]:
                base.largar(k)
        return f

    def modulo(nome, campo="_m"):
        m = sys.modules.get(f"tandera.pecas.{nome}")
        return (lambda: bool(m and getattr(m, campo, None))), (lambda: m and m.soltar())
    ovis_tem, ovis_solta = modulo("ovis")
    busca_tem, busca_solta = modulo("busca")
    corpo_tem, corpo_solta = modulo("corpo")
    return [
        ("alinhador MMS", 1250, True, seg("mms"), largar("mms")),
        ("rótulos CED", 420, True, seg("ced"), largar("ced")),
        ("Beat This!", 180, True, seg("beat_this"), largar("beat_this")),
        ("rostos", 900, True, seg("scrfd", "emo", "adaface"), largar("scrfd", "emo", "adaface")),
        ("cortes", 790, False, seg("autoshot", "transnet"), largar("autoshot", "transnet")),
        ("Whisper", 2155, False, lambda: bool(fala._modelos), fala.soltar),
        ("som CLAP", 1150, False, lambda: bool(som._m), som.soltar),
        ("imagem SigLIP", 1000, False, lambda: bool(imagem._m), imagem.soltar),
        ("texto OCR", 860, False, seg("ocr"), largar("ocr")),
        ("corpo", 1000, None, corpo_tem, corpo_solta),
        ("busca Qwen3", 5170, None, busca_tem, busca_solta),
        ("Ovis", 5271, None, ovis_tem, ovis_solta),
    ]


def _grandes_soltar(rodou=()):
    """os grandes nunca ficam: Ovis (5,3 GB), busca (Qwen3 8B), corpo; e o Gemma do olho (~9 GB, no Ollama) se o olho rodou"""
    _soltar([n for n, _, peq, tem, _ in _quentes() if peq is None and tem()], "grande: não fica quente")
    if "olho" in rodou:
        try:
            from .pecas import olho
            olho.soltar()
        except Exception:
            pass


def segurando():
    if not _estado["torch"]:
        return []
    try:
        return [(n, mib) for n, mib, _, tem, _ in _quentes() if tem()]
    except Exception:
        return []


def _soltar(nomes, porque):
    soltou = 0
    for n, mib, _, tem, solta in _quentes():
        if n in nomes and tem():
            try:
                solta(); soltou += mib
            except Exception as e:
                _anota(f"não consegui soltar {n}: {e}")
    if soltou:
        from . import base
        base.liberar_torch()
        _anota(f"soltei {', '.join(nomes)} (~{soltou} MiB) — {porque}")
    return soltou


def _excesso():
    """quanto (MiB) os quentes passam do que pode ficar AGORA (≤ 0 = cabe): memória livre medida, menos a folga, menos o pulo do Premiere
    no play quando ele está aberto e parado (com ele em uso/trabalhando/dúvida o pulo já aconteceu: conta só a folga)"""
    from . import porteiro
    v = porteiro.vram()
    if v is None:
        return 0
    falta = porteiro.MARGEM_MIB - v["livre"]
    prem = porteiro.premiere()
    if prem == "parado":
        falta += porteiro.PULO_PREMIERE_MIB
    elif prem != "fechado":
        # 20/11 20:27 (prova_regras_residente.txt): forçando a placa, a memória livre medida nunca caiu abaixo de ~0,9 GB — o driver
        # começa a jogar pra memória comum ANTES de zerar. Com o Premiere em uso, o piso tem que ficar acima disso: 0,7 + 0,6 = 1,3 GB.
        falta += PISO_EM_USO_MIB
    return falta


def _trava_de_outro():
    try:
        if not os.path.exists(TRAVA):
            return None
        t = open(TRAVA, encoding="utf-8", errors="replace").read().strip()
        b = t.lower()
        if ("tandera" in b and _estado["trabalhando"]) or "motor quente" in b or "residente" in b:
            return None                                       # a trava é deste motor (ou de quem está medindo ELE)
        return t[:120] or "trava"
    except Exception:
        return None


def arrumar(porque="vigia"):
    """a regra de memória: chamada a cada 2 s e no fim de cada pedido (nunca no meio de um pedido)"""
    if not _estado["torch"] or _estado["trabalhando"]:
        return
    from . import porteiro
    tem = segurando()
    if not tem:
        return
    nomes = [n for n, _ in tem]
    grandes = [n for n, _, peq, _, _ in _quentes() if peq is None and n in nomes]
    if grandes:
        _soltar(grandes, "grande: não fica quente")
        nomes = [n for n in nomes if n not in grandes]
    outro = _trava_de_outro()
    if outro:
        _soltar(nomes, f"a placa foi travada por outro trabalho ({outro})"); return
    if time.time() - _estado["ultimo_pedido"] > OCIOSO_S:
        _soltar(nomes, "15 min sem pedido"); return
    prem = porteiro.premiere()
    if prem != "fechado":                                    # Premiere aberto: só o quente pequeno
        pequenos = {n for n, _, peq, _, _ in _quentes() if peq}
        fora = [n for n in nomes if n not in pequenos]
        if fora:
            _soltar(fora, f"Premiere {prem}: fica só o quente pequeno")
            nomes = [n for n in nomes if n in pequenos]
    exc = _excesso()
    if exc > 0:                                              # não cabe: solta do fim da prioridade até cobrir
        ordem = [n for n, *_ in _quentes() if n in nomes][::-1]
        tirar, soma = [], 0
        for n in ordem:
            if soma >= exc:
                break
            tirar.append(n); soma += dict(tem)[n]
        _soltar(tirar, f"faltavam ~{exc} MiB de folga (Premiere {prem})")


def _carregadores():
    """como reabrir cada um do quente pequeno (o MESMO jeito que a peça abre: base.segurado com a mesma chave)"""
    from . import base
    from .pecas import batida, fala, rostos, rotulos
    return {"alinhador MMS": lambda: fala._mms("cuda"),
            "rótulos CED": lambda: base.segurado(("ced", "cuda"), lambda: rotulos.carregar("cuda")),
            "Beat This!": lambda: batida._beat_this(True),
            "rostos": lambda: (base.segurado(("scrfd", True), lambda: rostos.Scrfd(True)),
                               base.segurado(("emo", True), lambda: rostos.Expressao(True)),
                               base.segurado(("adaface", True), lambda: rostos.AdaFace("cuda")))}


def _reaquecer(nomes):
    """depois de um pedido GRANDE (o Ovis precisa da placa quase inteira e solta tudo), reabre o quente pequeno que estava quente ou
    que o pedido usou — um por vez, só se couber pela regra de memória (folga + pulo do Premiere parado) e sem trava de outro trabalho.
    Roda em 2º plano, DEPOIS da resposta: quem pediu não espera."""
    with _JOB:
        if not _estado["torch"] or _trava_de_outro():
            return
        tam = {n: mib for n, mib, peq, _, _ in _quentes() if peq}
        ja = dict(segurando())
        carregar = _carregadores()
        for n in [n for n, *_ in _quentes() if n in nomes and n in tam and n not in ja]:
            if _excesso() + tam[n] > 0:
                break
            t0 = time.monotonic()
            try:
                carregar[n]()
                _anota(f"reaqueci {n} em {time.monotonic() - t0:.1f} s (estava quente antes do pedido grande)")
            except Exception as e:
                _anota(f"não reaqueci {n}: {e}")


def _pequenos_do_pedido(antes, rodou=()):
    peq = {n for n, _, p, _, _ in _quentes() if p}
    usados = {q for p in rodou for q in DA_PECA.get(p, ())}
    return [n for n in (set(antes) | usados) if n in peq]


def _vigia():
    while True:
        time.sleep(TICK_S)
        try:
            if _JOB.acquire(blocking=False):
                try:
                    arrumar()
                    if (_estado["torch"] and time.time() - _estado["ultimo_pedido"] > OCIOSO_S and not segurando()):
                        _renascer("15 min sem pedido: renasce limpo (nem o crachá do CUDA fica na placa)")
                finally:
                    _JOB.release()
        except Exception as e:
            _anota(f"vigia: {type(e).__name__}: {e}")


_SERVIDOR = [None]


def _renascer(porque):
    """sobe um motor quente NOVO (sem nada na placa) e este sai; o novo espera a porta ficar livre"""
    import subprocess
    _anota(f"renascendo — {porque}")
    pyw = os.path.join(TANDERA, ".venv", "Scripts", "pythonw.exe")
    subprocess.Popen([pyw if os.path.exists(pyw) else sys.executable, "-m", "tandera.residente", "--depois-de", str(os.getpid())], cwd=TANDERA,
                     creationflags=SEM_JANELA | 0x00000008, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     close_fds=True)
    try:
        _SERVIDOR[0].server_close()
    finally:
        os._exit(0)


def _preparar_torch():
    """a 1ª vez que um pedido usa a placa neste processo"""
    if not _estado["torch"]:
        _estado["torch"] = True
        from . import base, porteiro
        porteiro.registrar_soltador(_soltador_porteiro)
        porteiro.ja_quente = ja_quente
        base.SEGURAR = True                                  # as peças seguram o modelo entre pedidos (o mesmo jeito do lote da noite)


# peça do Tandera → os quentes que ela usa (o porteiro desconta o que já está aberto e nunca solta o modelo de quem está pedindo)
DA_PECA = {"fala": ("alinhador MMS", "Whisper"), "cortes": ("cortes",), "rostos": ("rostos",), "rotulos": ("rótulos CED",),
           "batida": ("Beat This!",), "musica": ("Beat This!",), "texto": ("texto OCR",), "imagem": ("imagem SigLIP",),
           "som": ("som CLAP",), "ovis": ("Ovis",), "busca": ("busca Qwen3",), "corpo": ("corpo",)}


def _da_peca(quem):
    """«Tandera fala» → ("alinhador MMS", "Whisper")"""
    p = (quem or "").split()[-1] if quem else ""
    return DA_PECA.get(p, ())


def ja_quente(peca):
    """MiB que a peça já tem ABERTOS aqui (o porteiro não pede de novo)"""
    tem = dict(segurando())
    return sum(tem.get(n, 0) for n in DA_PECA.get(peca, ()))


def _soltar_medindo(falta_mib, porque, proteger=()):
    """solta do fim da prioridade, UM POR VEZ, medindo a memória livre de verdade depois de cada um, até sobrar `falta_mib` a mais do
    que tinha. 20/11 20:08 (medido): soltar pela ESTIMATIVA de tamanho parava cedo (o SigLIP/CLAP/cortes parados ocupam menos que o
    pico) — o Ovis ficou 0,2 GB curto e foi pro processador (+42 s). Devolve os MiB que voltaram de verdade."""
    from . import porteiro
    v0 = porteiro.vram()
    if v0 is None or falta_mib <= 0:
        return 0
    alvo = v0["livre"] + falta_mib
    tem = dict(segurando())
    livre = v0["livre"]
    for n in [n for n, *_ in _quentes() if n in tem and n not in proteger][::-1]:
        if livre >= alvo:
            break
        _soltar([n], porque)
        for _ in range(6):                                    # o driver leva um instante pra devolver
            time.sleep(0.1)
            v = porteiro.vram()
            if v and v["livre"] > livre:
                livre = v["livre"]
                break
        else:
            livre = (porteiro.vram() or {"livre": livre})["livre"]
    return max(0, livre - v0["livre"])


def _soltador_porteiro(falta_mib):
    """o porteiro (neste processo) precisa de memória pra uma peça: solta do fim da prioridade até a memória MEDIDA cobrir
    (nunca o modelo da própria peça que está pedindo)"""
    from . import porteiro
    quem = getattr(porteiro, "pedindo", "")
    _soltar_medindo(falta_mib, f"o porteiro pediu ~{falta_mib} MiB pra «{quem}»", proteger=_da_peca(quem))


def _ambiente_do_pedido(c):
    """as marcas de quem chamou valem só durante o pedido (um por vez)"""
    for k in ("TANDERA_FUNDO", "TANDERA_PEDIDO_DELE", "CLAUDECODE", "CUDA_VISIBLE_DEVICES"):
        os.environ.pop(k, None)
    if c.get("fundo"):
        os.environ["TANDERA_FUNDO"] = "1"


def _placa_ok(c):
    return not c.get("escondida") and c.get("placa", True) is not False


# ---------------------------------------------------------------- os trabalhos
def trabalho_analisar(c, escrever):
    from . import base, motor
    from .manifesto import PECAS
    _preparar_torch()

    def log(*a):
        t = " ".join(str(x) for x in a)
        _anota(t); escrever("LOG " + time.strftime("[%H:%M:%S] ") + t)
    A = motor.rodar(c["video"], c.get("pecas"), c.get("perfil"), tuple(c.get("refazer") or ()), _placa_ok(c), c.get("idioma"), c.get("pasta"),
                    log=log, stems=c.get("stems"))
    r = A.d["rodadas"][-1] if A.d.get("rodadas") else {}
    _grandes_soltar(set(r.get("rodou") or {}))
    return {"pasta": A.pasta, "s": r.get("s"), "rodou": list((r.get("rodou") or {}).keys()), "falhou": r.get("falhou"), "avisos": r.get("avisos"),
            "guardada": r.get("guardada")}


def _dispositivo(c, mib, quem, ja_quente):
    from . import porteiro
    if not _placa_ok(c) or c.get("dispositivo") == "cpu":
        return "cpu", "pedido no processador"
    if ja_quente:
        return "cuda", "quente"
    ok, motivo = porteiro.vaga(mib, quem)
    return ("cuda" if ok else "cpu"), motivo


def trabalho_transcrever(c):
    """o Whisper do Tandera. via: «tandera» (padrão: o próprio Whisper turbo, quente se der) · «quente» (o que já estiver quente: o do
    Tandera; senão o do ditado 8178, que já está na placa; senão abre o do Tandera) · «placa» (20/11 noite, o Kakashi ao vivo: o do
    Tandera NA PLACA; o porteiro sem vaga = o do ditado 8178, nunca o processador se o 8178 estiver no ar)"""
    from . import base
    from .pecas import fala
    _preparar_torch()
    x16 = base.ler_audio(c["audio"], 16000, ini=c.get("ini"), fim=c.get("fim"))
    quente = bool(fala._modelos.get("cuda"))
    if c.get("via") == "quente" and not quente and fala.rapido_no_ar():
        r = fala._transcrever_servidor(x16, c.get("idioma"), bool(c.get("palavras")))
        r["como"] = "Whisper do ditado (8178), já quente"
        return {"r": r}
    dev, motivo = _dispositivo(c, 2300, "residente Whisper", quente)
    if c.get("via") == "placa" and dev != "cuda" and fala.rapido_no_ar():
        # 20/11 noite (o Kakashi transcrevendo DURANTE a gravação): pediu o Whisper do Tandera na placa e o porteiro não deu vaga (o
        # Premiere pesado) — o do ditado (8178) já está na placa, sem pedir memória nova: melhor que ir pro processador
        r = fala._transcrever_servidor(x16, c.get("idioma"), bool(c.get("palavras")))
        r["como"] = "Whisper do ditado (8178) — sem vaga na placa pro do Tandera (%s)" % motivo
        return {"r": r}
    t0 = time.monotonic()
    r = fala.transcrever(x16, c.get("idioma"), dev, bool(c.get("palavras")) or bool(c.get("srt")))
    if c.get("srt"):
        open(c["srt"], "w", encoding="utf-8").write(fala.para_srt(r["segmentos"], int(c.get("max_len") or 70)))
    r["como"] = f"Whisper do Tandera ({'quente' if quente else 'abriu agora'}, {dev}) · {time.monotonic() - t0:.1f} s"
    if dev != "cuda":
        r["aviso"] = motivo
    if dev == "cpu":
        fala._modelos.pop("cpu", None)
    return {"r": r}


def trabalho_alinhar(c):
    from . import base
    from .pecas import fala
    _preparar_torch()
    x16 = base.ler_audio(c["audio"], 16000, ini=c.get("ini"), fim=c.get("fim"))
    quente = any(isinstance(k, tuple) and k[0] == "mms" and k[1] == "cuda" for k in base._SEGURADOS)
    dev, motivo = _dispositivo(c, 1300, "residente MMS", quente)
    t0 = time.monotonic()
    ws = fala.alinhar(x16, c["segmentos"], dev, c.get("idioma"))
    return {"palavras": ws, "como": f"MMS na {'placa' if dev == 'cuda' else 'processador'} ({'quente' if quente else 'abriu agora'}) · "
                                    f"{time.monotonic() - t0:.1f} s", **({"aviso": motivo} if dev != "cuda" else {})}


def trabalho_rotular(c):
    from . import base
    from .pecas import rotulos
    _preparar_torch()
    quente = any(isinstance(k, tuple) and k[0] == "ced" and k[1] == "cuda" for k in base._SEGURADOS)
    dev, _ = _dispositivo(c, 500, "residente CED", quente)
    modelo = base.segurado(("ced", dev), lambda: rotulos.carregar(dev))
    js = rotulos.etiquetar(base.ler_audio(c["wav"], 16000), dev, modelo=modelo, liberar=False)
    if dev == "cpu":
        base.largar(("ced", "cpu"))
    return {"r": {"modelo": "mispeech/ced-base", "passo": 0.5, "janela": 1.0, "janelas": js}}


def trabalho_batidas(c):
    import numpy as np
    from . import base
    from .manifesto import PECAS
    from .pecas import batida
    _preparar_torch()
    quente = any(isinstance(k, tuple) and k[0] == "beat_this" and k[1] is True for k in base._SEGURADOS)
    dev, _ = _dispositivo(c, 300, "residente Beat This!", quente)
    b = batida.batidas(c["wav"], dev == "cuda")
    if dev == "cpu":
        base.largar(("beat_this", False))
    r = dict(b)
    if not c.get("so_batidas"):
        g = batida.grade_na_onda(c["wav"], b["batidas"])
        bpm = round(60 / float(np.median(np.diff(b["batidas"]))), 2) if len(b["batidas"]) > 2 else None
        r.update(grade=g, bpm=g.get("bpm") or bpm, modelo=PECAS["batida"]["modelo"], versao=PECAS["batida"]["versao"])
    return {"r": r}


def trabalho_soltar(c):
    tem = segurando()
    if c.get("tudo"):
        return {"soltou_mib": _soltar([n for n, _ in tem], "pediram tudo")}
    falta = int(c.get("mib") or 0)
    return {"soltou_mib": _soltar_medindo(falta, f"outro programa pediu ~{falta} MiB")}


ROTAS = {"/transcrever": trabalho_transcrever, "/alinhar": trabalho_alinhar, "/rotular": trabalho_rotular, "/batidas": trabalho_batidas}


def _estado_json():
    from . import porteiro
    return {"nome": "tandera residente", "pid": os.getpid(), "porta": PORTA, "desde": time.strftime("%d/%m %H:%M:%S", time.localtime(_estado["inicio"])),
            "pedidos": _estado["pedidos"], "trabalhando": _estado["trabalhando"],
            "parado_min": round((time.time() - _estado["ultimo_pedido"]) / 60, 1),
            "quentes": [{"modelo": n, "mib": m} for n, m in segurando()], "vram": porteiro.vram(), "premiere": porteiro.premiere()}


def servir():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Pedido(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, cod, obj):
            b = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(cod); self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

        def do_GET(self):
            if self.path in ("/", "/saude", "/estado"):
                try:
                    obj = {"nome": "tandera residente", "pid": os.getpid()} if self.path == "/saude" else _estado_json()
                    self._json(200, obj)
                except Exception as e:
                    self._json(500, {"ok": False, "erro": str(e)})
            else:
                self._json(404, {"ok": False, "erro": "rota desconhecida"})

        def do_POST(self):
            try:
                n = int(self.headers.get("Content-Length") or 0)
                c = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            except Exception as e:
                return self._json(400, {"ok": False, "erro": f"pedido ilegível: {e}"})
            if self.path == "/soltar":
                if not _JOB.acquire(timeout=0.2):            # no meio de um pedido não solta (o modelo pode estar em uso)
                    return self._json(200, {"ok": True, "soltou_mib": 0, "ocupado": _estado["trabalhando"]})
                try:
                    return self._json(200, dict(ok=True, **trabalho_soltar(c)))
                finally:
                    _JOB.release()
            if self.path == "/analisar":
                return self._analisar(c)
            f = ROTAS.get(self.path)
            if not f:
                return self._json(404, {"ok": False, "erro": "rota desconhecida"})
            with _JOB:
                antes = [n for n, _ in segurando()]
                _estado["trabalhando"] = self.path[1:]; _estado["pedidos"] += 1
                t0 = time.monotonic()
                try:
                    _ambiente_do_pedido(c)
                    res = dict(ok=True, **f(c))
                except BaseException as e:
                    _anota(f"{self.path} falhou: {traceback.format_exc()[-1500:]}")
                    res = {"ok": False, "erro": f"{type(e).__name__}: {str(e)[:600]}"}
                finally:
                    _estado["trabalhando"] = None; _estado["ultimo_pedido"] = time.time()
                    _anota(f"{self.path} em {time.monotonic() - t0:.2f} s")
                    try:
                        arrumar("fim do pedido")
                    except Exception:
                        pass
            self._json(200, res)
            falta = [n for n in _pequenos_do_pedido(antes) if n not in dict(segurando())]
            if falta:
                threading.Thread(target=_reaquecer, args=(falta,), daemon=True).start()

        def _analisar(self, c):
            self.send_response(200); self.send_header("Content-Type", "text/plain; charset=utf-8"); self.end_headers()
            vivo = [True]
            tr = threading.Lock()                            # a peça «ao lado» (motor.py) também escreve: uma linha por vez

            def escrever(t):
                if not vivo[0]:
                    return
                try:
                    with tr:
                        self.wfile.write((t.replace("\n", " ") + "\n").encode("utf-8")); self.wfile.flush()
                except Exception:
                    vivo[0] = False                          # quem pediu desistiu: o trabalho termina e fica guardado
            with _JOB:
                antes = [n for n, _ in segurando()]
                _estado["trabalhando"] = "analisar " + os.path.basename(c.get("video") or ""); _estado["pedidos"] += 1
                t0 = time.monotonic()
                try:
                    _ambiente_do_pedido(c)
                    fim = dict(ok=True, **trabalho_analisar(c, escrever))
                except BaseException as e:
                    _anota(f"/analisar falhou: {traceback.format_exc()[-1500:]}")
                    fim = {"ok": False, "erro": f"{type(e).__name__}: {str(e)[:600]}"}
                finally:
                    _estado["trabalhando"] = None; _estado["ultimo_pedido"] = time.time()
                    _anota(f"/analisar em {time.monotonic() - t0:.1f} s")
                    try:
                        arrumar("fim do pedido")
                    except Exception:
                        pass
            escrever("FIM " + json.dumps(fim, ensure_ascii=False, default=str))
            falta = [n for n in _pequenos_do_pedido(antes, fim.get("rodou") or ()) if n not in dict(segurando())]
            if falta:
                threading.Thread(target=_reaquecer, args=(falta,), daemon=True).start()

    class Servidor(ThreadingHTTPServer):
        allow_reuse_address = False                           # no Windows o «reuse» deixaria dois motores na mesma porta
        daemon_threads = True

    espera_ate = time.time() + (30 if "--depois-de" in sys.argv else 0)
    while True:
        try:
            srv = Servidor(("127.0.0.1", PORTA), Pedido); break
        except OSError:
            if time.time() >= espera_ate:
                _anota(f"a porta {PORTA} já está em uso (outro motor quente de pé?) — saindo"); return
            time.sleep(0.5)
    _SERVIDOR[0] = srv
    _anota(f"motor quente de pé na {URL} (pid {os.getpid()})")
    threading.Thread(target=_vigia, daemon=True).start()
    threading.Thread(target=_aquecer_imports, daemon=True).start()
    srv.serve_forever()


def _aquecer_imports():
    """importa as bibliotecas pesadas logo ao ligar (sem tocar na placa: nada de memória da placa até o 1º pedido)"""
    try:
        t0 = time.monotonic()
        import numpy, torch, torchaudio, transformers  # noqa: F401
        from .pecas import fala, imagem, som, rotulos, batida  # noqa: F401
        _anota(f"bibliotecas prontas em {time.monotonic() - t0:.1f} s (placa intocada)")
    except Exception as e:
        _anota(f"aquecer as bibliotecas: {e}")


def main():
    os.environ["TANDERA_RESIDENTE"] = "1"
    global DENTRO
    DENTRO = True
    for k in ("CLAUDECODE", "TANDERA_FUNDO", "TANDERA_PEDIDO_DELE"):
        os.environ.pop(k, None)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    if sys.stdout is None or not sys.stdout.isatty():         # pythonw: o andamento vai pro trabalho\residente.log
        try:                                                  # o registro não cresce sem fim: passou de 5 MB, o velho vira .1
            if os.path.getsize(LOG) > 5 * 2 ** 20:
                os.replace(LOG, LOG + ".1")
        except OSError:
            pass
        f = open(LOG, "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = f
    import warnings
    warnings.filterwarnings("ignore", message=".*MatMul8bitLt.*")   # o Ovis em 8 bits avisa isso a cada lote (enchia o registro)
    from . import base  # noqa: F401  (cache de compilação próprio e «sem janela» valem pra este processo e os filhos)
    servir()


if __name__ == "__main__":
    main()
