# -*- coding: utf-8 -*-
"""O PAINEL DO CHECKLIST (04/11/2026): a grade de cada vídeo × cada peça do motor, numa página local.
O Luan (04/11): «o que ele quer é só aquele checklist do Tandera... pra ele conseguir gerenciar as análises com peça de motor».
Mesmo desenho do painel do PC do Luan (03/11, desenhado por ele): abas = os grupos do checklist; cada vídeo é uma coluna com a capa em
cima; as peças do motor são as linhas; bolinha ✓ = feita na versão atual (embaixo, quem fez o diário: Gemini ou Gemma) · ✕ = falta ·
↻ = a peça do motor atualizou (refaz) · vermelho = falhou (o motivo no mouse) · ponto apagado = não é desta pista. «rodando agora» à
esquerda: o vídeo da fila, a peça de agora, % e quanto falta. ▶ roda AGORA um vídeo, o grupo ou tudo o que falta (uma fila por vez; a
fila respeita as travas de sempre: Premiere aberto / placa em uso = ela espera e diz por quê).

  tandera painel [--porta 7822] [--sem-abrir]      liga em http://127.0.0.1:7822 e abre no navegador (já ligado = só abre)

Só LÊ o que o motor grava: checklist\\checklist.json (`tandera checklist`, e no fim de cada fila) e trabalho\\filas\\*\\ (estado.json +
log.txt). Automático: a cada minuto, se alguma análise (analises\\*\\analise.json) ou o manifesto mudou depois do último checklist, ele
se refaz sozinho (sem janela). Nada de botão «atualizar».
GET  /api/estado               → grupos, arquivos (peça por peça), a fila de agora/última, a próxima noite
GET  /api/capa?a=<assinatura>  → a capa do vídeo (o quadro que o preparo guardou; senão um do vídeo, guardado em trabalho\\painel-capas)
POST /api/rodar {assinatura} | {grupo} | {}  → uma fila AGORA (um vídeo, o grupo, ou tudo o que falta)"""
import datetime, glob, json, os, re, subprocess, sys, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

from . import base

T = base.TANDERA
CHECK = os.path.join(T, "checklist", "checklist.json")
FILAS = os.path.join(T, "trabalho", "filas")
CAPAS = os.path.join(T, "trabalho", "painel-capas")
PAGINA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "painel.html")
PORTA = int(os.environ.get("TANDERA_PAINEL_PORTA") or 7822)
TRABALHO = ("completo", "falta peça", "nunca analisado")
_trava = threading.Lock()
_atualizando = [0.0]


def _py():
    """o Python deste ambiente; no Windows o pythonw (os filhos saem sem janela)"""
    if os.name == "nt":
        w = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if os.path.isfile(w):
            return w
    return sys.executable


def _solto(args):
    """roda um `python -m tandera ...` solto (sobrevive ao painel), sem janela no Windows"""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONPATH=T + os.pathsep + os.environ.get("PYTHONPATH", ""))
    if os.name == "nt":
        subprocess.Popen([_py(), "-m", "tandera"] + args, cwd=T, env=env, close_fds=True,
                         creationflags=base.SEM_JANELA | 0x00000200 | 0x00000008)       # sem janela · grupo novo · solto
    else:
        subprocess.Popen([_py(), "-m", "tandera"] + args, cwd=T, env=env, close_fds=True, start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _ler(p, padrao):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return padrao


def _nome_grupo(g, info):
    """o nome que aparece na aba: o «nome» do grupo no checklist, senão o id sem o número da frente («2-cursos-aulas» → «cursos aulas»)"""
    return info.get("nome") or re.sub(r"^\d+-", "", g).replace("-", " ")


def _fila():
    """a fila mais nova: rodando? o que está rodando, quantos feitos/falharam, por que parou"""
    ests = sorted(glob.glob(os.path.join(FILAS, "*", "estado.json")), key=os.path.getmtime)
    if not ests:
        return None
    E = _ler(ests[-1], {})
    its = E.get("itens", [])
    cont = {}
    for i in its:
        cont[i.get("estado") or "na fila"] = cont.get(i.get("estado") or "na fila", 0) + 1
    log = os.path.join(os.path.dirname(ests[-1]), "log.txt")
    vivo = bool(not E.get("parou") and os.path.exists(log) and time.time() - os.path.getmtime(log) < 1800)
    rodando = [os.path.basename(i["arquivo"]) for i in its if i.get("estado") == "rodando"]
    return {"nome": E.get("nome"), "comecou": E.get("comecou"), "parou": E.get("parou"), "porque": E.get("porque"), "contagem": cont,
            "rodando": rodando if vivo else [], "viva": vivo, "agora": _agora(os.path.dirname(ests[-1]), its) if vivo else []}


def _agora(pasta, its):
    """pro vídeo que está rodando: as peças que faltavam (checklist), as que já fecharam (✓ no log), a de agora (▶ no log, desde quando) e
    a conta do que falta pela velocidade medida de cada peça (s de máquina por s de vídeo, do checklist)"""
    try:
        log = open(os.path.join(pasta, "log.txt"), encoding="utf-8", errors="replace").read().splitlines()[-600:]
    except OSError:
        return []
    C = _ler(CHECK, {}) or {}
    vel = C.get("velocidade_s_por_s") or {}
    porc = {a["caminho"]: a for a in C.get("arquivos", [])}
    hoje = datetime.date.today()
    out = []
    for i in its:
        if i.get("estado") != "rodando":
            continue
        nome = os.path.basename(i["arquivo"]); a = porc.get(i["arquivo"]) or {}
        dur = float(i.get("dur") or a.get("duracao_s") or 0)
        pecas = list(a.get("falta") or [])
        feitas, falhou, atual, desde = [], [], None, None
        for l in log:
            m = re.match(r"\[(\d\d:\d\d:\d\d)\]\s+(✓|✗|✕|▶)\s+(.+?): (\w+)", l)
            if not m or m.group(3) != nome:
                continue
            hora, sinal, peca = m.group(1), m.group(2), m.group(4)
            if peca not in pecas:
                pecas.append(peca)
            if sinal == "▶":
                atual, desde = peca, hora
            elif sinal == "✓":
                feitas.append(peca); atual = None if atual == peca else atual
            else:
                falhou.append(peca); atual = None if atual == peca else atual
        esp = lambda p: max(3.0, dur * float(vel.get(p, 0.1)))
        total = sum(esp(p) for p in pecas) or 1.0
        passou = 0.0
        if atual and desde:
            try:
                t0 = datetime.datetime.combine(hoje, datetime.datetime.strptime(desde, "%H:%M:%S").time())
                passou = max(0.0, (datetime.datetime.now() - t0).total_seconds())
            except ValueError:
                pass
        feito_s = sum(esp(p) for p in feitas + falhou) + (min(passou, esp(atual) * 0.95) if atual else 0)
        resto = [p for p in pecas if p not in feitas and p not in falhou and p != atual]
        falta_s = sum(esp(p) for p in resto) + (max(esp(atual) - passou, esp(atual) * 0.05) if atual else 0)
        out.append({"nome": nome, "assinatura": a.get("assinatura"), "dur": dur, "pecas": pecas, "feitas": feitas, "falhou": falhou,
                    "atual": atual, "desde": desde, "passou_s": round(passou), "pct": min(99, round(100 * feito_s / total)), "falta_s": round(falta_s)})
    return out


def _proxima_noite():
    agora = datetime.datetime.now()
    d = agora.replace(hour=1, minute=0, second=0, microsecond=0)
    if agora >= d:
        d += datetime.timedelta(days=1)
    return d.strftime("%d/%m %H:%M")


def _rodando_ck():
    """o checklist está se refazendo agora? (pedido há menos de 90 s e o arquivo ainda não foi reescrito depois do pedido)"""
    ini = _atualizando[0]
    return time.time() - ini < 90 and not (os.path.exists(CHECK) and os.path.getmtime(CHECK) >= ini)


def estado():
    C = _ler(CHECK, None)
    if not C:
        return {"ok": True, "sem_checklist": True, "fila": _fila(), "proxima": _proxima_noite(), "atualizando": _rodando_ck()}
    G = C.get("grupos", {})
    grupos = []
    for g in sorted(G, key=lambda k: G[k].get("prioridade", 99)):
        its = [a for a in C["arquivos"] if a["grupo"] == g]
        validos = [a for a in its if a.get("situacao") in TRABALHO]
        dur = sum(float(a.get("duracao_s") or 0) for a in validos)
        arqs = [{"nome": os.path.basename(a["caminho"]), "caminho": a["caminho"], "dur": a.get("duracao_s"), "situacao": a.get("situacao"),
                 "falta": a.get("falta") or [], "motivos": a.get("motivos") or {}, "fontes": a.get("fontes") or {}, "maquina_s": a.get("maquina_s", 0),
                 "assinatura": a.get("assinatura"), "pecas": a.get("pecas") or {}} for a in validos]
        ordem = {"falta peça": 0, "nunca analisado": 1, "completo": 2}
        arqs.sort(key=lambda a: (ordem.get(a["situacao"], 3), a["nome"].lower()))
        grupos.append({"grupo": g, "nome": _nome_grupo(g, G[g]), "pista": G[g].get("pista"), "prioridade": G[g].get("prioridade"),
                       "pedir_ok": bool(G[g].get("pedir_ok")), "arquivos": arqs, "fora": len(its) - len(validos), "horas": round(dur / 3600, 2),
                       "completos": sum(1 for a in validos if a["situacao"] == "completo"),
                       "falta_peca": sum(1 for a in validos if a["situacao"] == "falta peça"),
                       "nunca": sum(1 for a in validos if a["situacao"] == "nunca analisado"),
                       "maquina_h": round(sum(a.get("maquina_s", 0) for a in validos) / 3600, 1)})
    tot = {k: sum(x[k] for x in grupos) for k in ("completos", "falta_peca", "nunca")}
    tot["arquivos"] = sum(len(x["arquivos"]) for x in grupos)
    tot["maquina_h"] = round(sum(x["maquina_h"] for x in grupos if not x["pedir_ok"]), 1)
    return {"ok": True, "atualizado": C.get("atualizado"), "grupos": grupos, "total": tot, "fila": _fila(), "proxima": _proxima_noite(),
            "atualizando": _rodando_ck()}


def _item(assinatura):
    C = _ler(CHECK, {}) or {}
    return next((a for a in C.get("arquivos", []) if a.get("assinatura") == assinatura), None)


def capa(assinatura):
    """(bytes jpg) a capa do vídeo: o quadro que o preparo guardou (pecas/preparo/mini); senão um quadro a 10% do vídeo, tirado UMA vez
    (ffmpeg no processador, 480 px) e guardado em trabalho/painel-capas"""
    if not re.fullmatch(r"[0-9a-f]{6,40}", assinatura or ""):
        return None
    c = os.path.join(CAPAS, assinatura + ".jpg")
    if os.path.isfile(c):
        return open(c, "rb").read()
    a = _item(assinatura)
    if not a:
        return None
    os.makedirs(CAPAS, exist_ok=True)
    mini = sorted(glob.glob(os.path.join(a.get("analise") or "", "pecas", "preparo", "mini", "*.jpg")))
    if mini:
        src = mini[len(mini) // 10] if len(mini) > 10 else mini[0]
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", "scale=480:-2", c]
    elif os.path.isfile(a["caminho"]) and a["caminho"].lower().endswith((".jpg", ".jpeg", ".png", ".heic", ".webp")):
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", a["caminho"], "-vf", "scale=480:-2", "-frames:v", "1", c]
    elif os.path.isfile(a["caminho"]):
        t0 = max(0.0, float(a.get("duracao_s") or 0) * 0.1)
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", "%.2f" % t0, "-i", a["caminho"], "-frames:v", "1", "-vf", "scale=480:-2", c]
    else:
        return None
    try:
        subprocess.run(cmd, timeout=40, creationflags=base.SEM_JANELA, capture_output=True)
    except Exception:
        return None
    return open(c, "rb").read() if os.path.isfile(c) else None


def rodar(corpo):
    """uma fila AGORA: um vídeo (assinatura), um grupo, ou tudo o que falta (--checklist). Uma fila por vez."""
    f = _fila()
    if f and f.get("viva"):
        raise ValueError("já tem uma fila rodando (%s): espera ela acabar" % (f.get("nome") or ""))
    C = _ler(CHECK, {}) or {}
    quando = time.strftime("%Y%m%d-%H%M%S")
    if corpo.get("assinatura") or corpo.get("grupo"):
        its = [a for a in C.get("arquivos", []) if a.get("situacao") in ("falta peça", "nunca analisado")
               and (a.get("assinatura") == corpo.get("assinatura") if corpo.get("assinatura") else a.get("grupo") == corpo.get("grupo"))]
        if not its:
            raise ValueError("nada pra rodar aqui: já está tudo analisado")
        nome = "painel-" + ("video" if corpo.get("assinatura") else re.sub(r"[^\w-]", "", corpo["grupo"])) + "-" + quando
        d = os.path.join(T, "trabalho", "filas-painel"); os.makedirs(d, exist_ok=True)
        fj = os.path.join(d, nome + ".json")
        with open(fj, "w", encoding="utf-8") as fh:
            json.dump({"nome": nome, "itens": [{"arquivo": a["caminho"], "pista": a.get("pista") or "editado"} for a in its]},
                      fh, ensure_ascii=False, indent=1)
        _solto(["fila", fj, "--nome", nome])
        msg = "%d vídeo%s na fila agora" % (len(its), "" if len(its) == 1 else "s")
    else:
        _solto(["fila", "--checklist", "--nome", "painel-tudo-" + quando])
        msg = "fila de tudo o que falta, agora"
    e = estado(); e["aviso"] = msg
    return e


def _refazer():
    with _trava:
        if time.time() - _atualizando[0] > 90:
            _atualizando[0] = time.time()
            _solto(["checklist"])


def _vigia():
    """a cada minuto: alguma análise ou o manifesto do motor (peça nova/versão nova) mudou DEPOIS do último checklist → ele se refaz sozinho"""
    while True:
        try:
            ck = os.path.getmtime(CHECK) if os.path.exists(CHECK) else 0
            mud = max([os.path.getmtime(os.path.join(T, "tandera", "manifesto.py"))] +
                      [os.path.getmtime(a) for a in glob.glob(os.path.join(base.ANALISES, "*", "analise.json"))] + [0])
            if mud > ck + 2:
                _refazer()
        except Exception:
            pass
        time.sleep(60)


class _Pedido(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _manda(self, cod, corpo, tipo="application/json; charset=utf-8"):
        if isinstance(corpo, (dict, list)):
            corpo = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        self.send_response(cod)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        u = urlparse(self.path)
        try:
            if u.path in ("/", "/index.html"):
                with open(PAGINA, "rb") as f:
                    return self._manda(200, f.read(), "text/html; charset=utf-8")
            if u.path == "/api/estado":
                return self._manda(200, estado())
            if u.path == "/api/capa":
                b = capa((parse_qs(u.query).get("a") or [""])[0])
                return self._manda(200, b, "image/jpeg") if b else self._manda(404, {"erro": "sem capa"})
            if u.path == "/api/oi":
                return self._manda(200, {"tandera": "painel"})
            self._manda(404, {"erro": "não achei"})
        except Exception as e:
            self._manda(500, {"erro": str(e)})

    def do_POST(self):
        if urlparse(self.path).path != "/api/rodar":
            return self._manda(404, {"erro": "não achei"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            corpo = json.loads(self.rfile.read(n) or b"{}") if n else {}
            self._manda(200, rodar(corpo))
        except ValueError as e:
            self._manda(400, {"erro": str(e)})
        except Exception as e:
            self._manda(500, {"erro": str(e)})


def _ja_ligado(porta):
    try:
        return json.load(urlopen("http://127.0.0.1:%d/api/oi" % porta, timeout=2)).get("tandera") == "painel"
    except Exception:
        return False


def main(argv):
    porta, abrir = PORTA, "--sem-abrir" not in argv
    if "--porta" in argv:
        porta = int(argv[argv.index("--porta") + 1])
    url = "http://127.0.0.1:%d/" % porta
    if _ja_ligado(porta):
        print("o painel já está ligado:", url)
        if abrir:
            webbrowser.open(url)
        return
    srv = ThreadingHTTPServer(("127.0.0.1", porta), _Pedido)          # só nesta máquina
    threading.Thread(target=_vigia, daemon=True, name="painel-vigia").start()
    print("painel do checklist:", url, "(Ctrl+C desliga)")
    if abrir:
        threading.Timer(0.6, webbrowser.open, (url,)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
