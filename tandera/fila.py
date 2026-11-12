# -*- coding: utf-8 -*-
"""A FILA DO PC (B6, 02/11/2026 à noite): vários arquivos, cada um na sua PISTA (tandera\\pistas.py), rodados sozinhos enquanto o Luan
dorme. Ele (02/11 ~23h50): «eu vou dormir agora e deixar o PC trabalhando de madrugada, gerando relatórios de vídeos que faltavam a gente
analisar... a ordem das coisas que for analisar, você pode ficar por você mesmo».
  - em BLOCOS pelo tandera\\lote.py (o mesmo do RunPod): cada modelo carrega UMA vez pro bloco, peça por peça; mesmo resultado e mesmo
    jeito de guardar do `tandera analisar` (assinatura, versão, incremental: o que já está guardado não roda);
  - pista «tutorial» = as janelas de exemplo (janelas.exemplos), um vídeo por vez;
  - UMA coisa na placa por vez (este processo é o único trabalho); o Medidor é avisado em cada bloco (base.Placa);
  - PARA sozinha: na hora do --ate (não começa bloco novo depois dela), com o Premiere aberto (o PC é dele) ou com a placa em uso por
    outro trabalho; o que já foi feito fica guardado e rodar de novo continua de onde parou;
  - nenhuma janela: rodando sem console (pythonw), todo programa que ela chama abre com CREATE_NO_WINDOW;
  - o andamento: trabalho\\filas\\<nome>\\ESTADO.md (legível) + estado.json + log.txt.
  tandera.cmd fila <fila.json> [--ate 08:30] [--bloco 4]
  tandera.cmd fila --pista bruto <arquivos ou pastas...> [--nome X] [--ate 08:30]
  tandera.cmd fila --checklist --ate 08:30          o que FALTA no checklist, na ordem das prioridades, até a hora (03/11)
fila.json = {"nome": "...", "itens": [{"arquivo": "...", "pista": "editado", "idioma": "pt", "grupo": "meu-grupo", "nota": "..."}]}"""
import json, os, queue, subprocess, sys, threading, time, traceback

from . import base
from .pistas import FOTOS, PISTAS, VIDEOS, pecas_da, stems_da


def _sem_janela():
    """sem console (pythonw): todo filho abre sem janela (regra dele, 31/10: «Para de ficar abrindo essa tela»)"""
    base.sem_janela()      # 04/11: o remendo mudou pra base.py, que todo processo do Tandera importa (os filhos da fila também)


def _arquivos(caminhos):
    out = []
    for c in caminhos:
        if os.path.isdir(c):
            for raiz, _, fs in os.walk(c):
                out += [os.path.join(raiz, f) for f in sorted(fs) if f.lower().endswith(VIDEOS + FOTOS) and not f.startswith("._")]
        elif os.path.exists(c):
            out.append(c)
    return [os.path.abspath(x) for x in out]


class Estado:
    def __init__(self, nome, itens):
        self.d = os.path.join(base.TANDERA, "trabalho", "filas", nome); os.makedirs(self.d, exist_ok=True)
        self.arq = os.path.join(self.d, "estado.json")
        velho = json.load(open(self.arq, encoding="utf-8")) if os.path.exists(self.arq) else {}
        ant = {i["arquivo"]: i for i in velho.get("itens", [])}
        self.s = {"nome": nome, "comecou": time.strftime("%Y-%m-%d %H:%M:%S"), "parou": None, "porque": None,
                  "itens": [dict(it, **{k: ant.get(it["arquivo"], {}).get(k) for k in ("estado", "s", "pasta", "falhou", "quando")})
                            for it in itens]}
        self.log_arq = open(os.path.join(self.d, "log.txt"), "a", encoding="utf-8", buffering=1)

    def log(self, *a):
        msg = time.strftime("[%H:%M:%S] ") + " ".join(str(x) for x in a)
        self.log_arq.write(msg + "\n")
        try: print(msg, flush=True)
        except Exception: pass

    def marca(self, arquivo, **k):
        for i in self.s["itens"]:
            if i["arquivo"] == arquivo: i.update(k, quando=time.strftime("%H:%M:%S"))
        self.gravar()

    def gravar(self):
        base.salvar_json(self.arq, self.s)
        L = [f"# Fila do Tandera — {self.s['nome']}", "", f"- começou: {self.s['comecou']}",
             f"- parou: {self.s['parou'] or '— (rodando)'}" + (f" · {self.s['porque']}" if self.s.get("porque") else ""), ""]
        its = self.s["itens"]
        cont = {}
        for i in its: cont[i.get("estado") or "na fila"] = cont.get(i.get("estado") or "na fila", 0) + 1
        L += ["**" + " · ".join(f"{k}: {v}" for k, v in sorted(cont.items())) + "**", "",
              "| # | grupo | pista | arquivo | duração | estado | tempo | quando | obs |", "|---|---|---|---|---|---|---|---|---|"]
        for n, i in enumerate(its, 1):
            obs = "; ".join(f"{k}: {str(v)[:60]}" for k, v in (i.get("falhou") or {}).items()) or (i.get("nota") or "")
            L.append(f"| {n} | {i.get('grupo') or ''} | {i['pista']} | {os.path.basename(i['arquivo'])} | {base.mmss(i.get('dur') or 0, 0)} | "
                     f"{i.get('estado') or 'na fila'} | {round(i['s']) if i.get('s') else ''} s | {i.get('quando') or ''} | {obs} |")
        open(os.path.join(self.d, "ESTADO.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


def _parar(ate):
    """motivo pra não começar o próximo bloco (None = segue)"""
    if ate and time.strftime("%H:%M") >= ate and time.strftime("%H:%M") < "18:00":
        return f"deu a hora ({ate}): o PC volta livre pro Luan"
    if base.premiere_aberto():
        return "o Premiere abriu: a placa é dele"
    trava = os.environ.get("TANDERA_TRAVA_PLACA") or os.path.join(base.TANDERA, "GPU_EM_USO.txt")   # pacote da Fly: era a trava fixa do PC do Luan
    if os.name == "nt" and os.path.exists(trava) and "tandera" not in open(trava, encoding="utf-8", errors="replace").read().lower():
        return "a placa está em uso por outro trabalho: " + open(trava, encoding="utf-8", errors="replace").read().strip()[:120]
    return None


# 03/11: o diário (Gemini, nuvem) levava de 5 a 15 min por vídeo e o bloco ESPERAVA ele com a placa parada (bloco de 4 vídeos em 1 h na
# madrugada de 03/11). Agora a placa nunca espera a nuvem: o diário corre numa linha à parte (LinhaNuvem), um vídeo depois do outro, e a
# busca (que lê o diário e usa a placa) entra num bloquinho próprio quando há diários prontos. Cota do Gemini acabou = a linha para
# (o que faltou volta no checklist da próxima noite).
NUVEM = ("diario",)
DEPOIS_DA_NUVEM = ("busca",)


ESPERA_COTA = 30 * 60          # segundos entre uma tentativa e outra quando o Gemini está sem cota


class LinhaNuvem(threading.Thread):
    def __init__(self, log):
        super().__init__(daemon=True)
        self.q, self.log, self.prontos, self.trava = queue.Queue(), log, [], threading.Lock()
        self.gemma = []                # (vídeo, quer_busca) sem cota no Gemini: o diário sai pelo Gemma no bloquinho da placa
        self.parar, self.sem_cota, self.pendentes = False, False, 0

    def por(self, video, quer_busca):
        with self.trava: self.pendentes += 1
        self.q.put((video, quer_busca))

    def run(self):
        from . import motor
        from .armazem import Analise
        while True:
            x = self.q.get()
            if x is None: return
            video, quer_busca = x
            try:
                # (03/11 ~23h a linha esperava a cota voltar e tentava o mesmo vídeo a cada ESPERA_COTA.) 04/11 (ele, Kakashi 14:13: «se você já analisou isso aqui com o Gema, tem que entrar o diário do Gema aqui»): sem cota, o
                # vídeo NÃO espera mais a cota voltar — vai pro bloquinho da placa e o Gemma faz o diário (pecas/diario.py, gemma())
                motor.rodar(video, ["diario"], placa=False, log=self.log)
                A = Analise(video)
                erro = ((A.d.get("rodadas") or [{}])[-1].get("falhou") or {}).get("diario", "")
                if erro:                   # sem cota, sem chave ou o Gemini não respondeu (C0038, 04/11): o Gemma faz
                    if not self.sem_cota:
                        self.log(f"☁ o Gemini não fez o diário ({erro[:80]}): os diários seguem pelo Gemma, na placa, junto da busca")
                    self.sem_cota = True
                    with self.trava: self.gemma.append((video, quer_busca))
                    continue
                if self.sem_cota: self.log("☁ o Gemini respondeu de novo: seguindo com os diários dele")
                self.sem_cota = False
                if A.tem("diario") and quer_busca:
                    with self.trava: self.prontos.append(video)
            except Exception as e:
                self.log(f"☁ diário de {os.path.basename(video)} falhou: {type(e).__name__}: {str(e)[:200]}")
            finally:
                with self.trava: self.pendentes -= 1

    def pegar_prontos(self):
        with self.trava:
            p, self.prontos = self.prontos, []
            g, self.gemma = self.gemma, []
        return p, g


def _busca(lote, nuvem, log):
    """o bloquinho da placa: a busca dos vídeos cujo diário ficou pronto + o diário PELO GEMMA dos que ficaram sem cota no Gemini
    (o diário roda antes da busca no mesmo bloco: a busca depende dele)"""
    vs, gs = nuvem.pegar_prontos()
    if not vs and not gs: return
    log(f"bloquinho da placa: busca de {len(vs)} vídeo(s) com o diário pronto"
        + (f" · diário pelo Gemma de {len(gs)} (sem cota no Gemini)" if gs else ""))
    itens = [{"video": v, "pecas": list(DEPOIS_DA_NUVEM), "id": os.path.basename(v)} for v in vs]
    itens += [{"video": v, "pecas": ["diario"] + (list(DEPOIS_DA_NUVEM) if qb else []), "id": os.path.basename(v)} for v, qb in gs]
    try:
        lote.rodar_bloco(itens, placa=True, log=log)
    except SystemExit:
        raise
    except Exception as e:
        log(f"✗ bloquinho da placa falhou: {type(e).__name__}: {str(e)[:300]}")


def rodar(itens, nome, ate=None, bloco=4, completar=False, com=()):
    from . import lote
    E = Estado(nome, itens)
    log = E.log
    base.log = log
    nuvem = LinhaNuvem(log); nuvem.start()
    for i in E.s["itens"]:
        if i.get("dur") is None:
            try: i["dur"] = round(float(base.ffprobe(i["arquivo"], "-show_entries", "format=duration", "-of", "csv=p=0") or 0), 1)
            except Exception: i["dur"] = 0
    E.gravar()
    log(f"FILA {nome}: {len(itens)} arquivos · até {ate or 'acabar'} · bloco {bloco}")
    pend = [i for i in E.s["itens"] if i.get("estado") not in ("feito",)]
    k = 0
    while True:
        if k >= len(pend):
            # 03/11: a fila acabou às 05h e o PC ficou parado até ele acordar → com --checklist, acabou a lista = puxa o próximo que FALTA
            # no checklist (nunca o que já está ok), até a hora
            if not completar or _parar(ate): break
            from .checklist import pendentes
            mais = pendentes(com=com, excluir={i["arquivo"] for i in E.s["itens"]})[:bloco * 2]
            if not mais: break
            log(f"a lista acabou: +{len(mais)} do checklist ({', '.join(sorted({m['grupo'] for m in mais}))})")
            E.s["itens"] += mais; pend += mais; E.gravar()
        porque = _parar(ate)
        if porque:
            nuvem.parar = True
            E.s["parou"], E.s["porque"] = time.strftime("%Y-%m-%d %H:%M:%S"), porque; E.gravar(); log("PAROU:", porque); return E
        try:
            _busca(lote, nuvem, log)
        except SystemExit as e:
            nuvem.parar = True
            E.s["parou"], E.s["porque"] = time.strftime("%Y-%m-%d %H:%M:%S"), str(e)[:200]; E.gravar(); log("PAROU:", e); return E
        pista = pend[k]["pista"]
        if PISTAS[pista].get("exemplos"):
            grupo = [pend[k]]; k += 1
        else:
            grupo = []
            while k < len(pend) and pend[k]["pista"] == pista and len(grupo) < bloco:
                grupo.append(pend[k]); k += 1
        t0 = time.monotonic()
        for i in grupo: E.marca(i["arquivo"], estado="rodando")
        try:
            if PISTAS[pista].get("exemplos"):
                from .janelas import exemplos
                i = grupo[0]
                exemplos(i["arquivo"], True, i.get("idioma") or PISTAS[pista].get("idioma"), False, True, log=log)
                E.marca(i["arquivo"], estado="feito", s=round(time.monotonic() - t0, 1))
                continue
            its = []
            for i in grupo:
                try:
                    todas = pecas_da(pista, i["arquivo"], i.get("bateria") or BATERIA_CLI[0])
                    st, caem = stems_da(pista, i["arquivo"], log, todas)     # 12/11: sem a bateria som = o próprio som (nada de separar)
                    todas = [p for p in todas if p not in caem]
                    pecas = [p for p in todas if p not in NUVEM + DEPOIS_DA_NUVEM]
                    if any(p in todas for p in NUVEM):
                        i["_nuvem"] = any(p in todas for p in DEPOIS_DA_NUVEM)      # o diário vai pra linha da nuvem depois do bloco
                    if not pecas:                                                # só falta diário/busca: nada na placa agora
                        if "_nuvem" in i: nuvem.por(i["arquivo"], i.pop("_nuvem"))
                        if st and pista != "kakashi":                            # 09/11: o stems_da acabou de refazer o som próprio à toa
                            from .armazem import Analise
                            from .pecas.separacao import soltar_sons
                            soltar_sons(Analise(os.path.abspath(i["arquivo"])), log)
                        E.marca(i["arquivo"], estado="feito", nota="diário na linha da nuvem")
                        continue
                    its.append({"video": i["arquivo"], "pecas": pecas, "stems": st, "id": os.path.basename(i["arquivo"]),
                                "idioma": i.get("idioma") or PISTAS[pista].get("idioma"), "refazer": i.get("refazer") or []})
                except Exception as e:
                    E.marca(i["arquivo"], estado="falhou", falhou={"abrir": f"{type(e).__name__}: {str(e)[:300]}"})
                    log(f"✗ {os.path.basename(i['arquivo'])}: não abriu: {e}")
            for it in its:
                try:
                    it["previa"] = lote.preparar(it, placa=True, log=log)
                except Exception as e:
                    it["previa"] = None
                    log(f"✗ {it['id']}: preparo falhou: {type(e).__name__}: {str(e)[:300]}")
            its = [it for it in its if it.get("previa") is not None]
            if not its: continue
            r = lote.rodar_bloco(its, placa=True, log=log)
            dur_tot = sum(i.get("dur") or 0 for i in grupo) or 1
            for it in its:
                v = r["videos"].get(it["id"]) or {}
                d = next((i.get("dur") or 0 for i in grupo if i["arquivo"] == it["video"]), 0)
                E.marca(it["video"], estado="falhou" if v.get("falhou") else "feito", falhou=v.get("falhou") or None, pasta=v.get("pasta"),
                        s=round(r["s"] * d / dur_tot, 1))
                i = next((i for i in grupo if i["arquivo"] == it["video"]), {})
                if "_nuvem" in i and not v.get("falhou", {}).get("preparo"): nuvem.por(it["video"], i.pop("_nuvem"))
            for nm, motivo in (r.get("ruins") or {}).items():
                for i in grupo:
                    if os.path.basename(i["arquivo"]) == nm: E.marca(i["arquivo"], estado="falhou", falhou={"abrir": motivo})
        except SystemExit as e:                       # base.Placa: Premiere abriu / placa ocupada no meio
            for i in grupo:
                if next(x for x in E.s["itens"] if x["arquivo"] == i["arquivo"]).get("estado") == "rodando": E.marca(i["arquivo"], estado=None)
            E.s["parou"], E.s["porque"] = time.strftime("%Y-%m-%d %H:%M:%S"), str(e)[:200]; E.gravar(); log("PAROU:", e); return E
        except Exception as e:
            log(f"✗ bloco ({pista}) falhou: {type(e).__name__}: {str(e)[:300]}\n{traceback.format_exc()[-1500:]}")
            for i in grupo:
                if next(x for x in E.s["itens"] if x["arquivo"] == i["arquivo"]).get("estado") == "rodando":
                    E.marca(i["arquivo"], estado="falhou", falhou={"bloco": f"{type(e).__name__}: {str(e)[:200]}"})
        log(f"bloco {pista} ({len(grupo)}) em {time.monotonic() - t0:.0f} s")
    # a placa acabou: espera a linha da nuvem (até a hora) e faz a busca dos últimos diários
    # (04/11: sem cota não prende mais ninguém — o vídeo vai pro Gemma no bloquinho da placa e a linha segue)
    while nuvem.pendentes and not _parar(ate):
        time.sleep(20)
        try: _busca(lote, nuvem, log)
        except SystemExit: break
    nuvem.parar = True
    try: _busca(lote, nuvem, log)
    except SystemExit: pass
    E.s["parou"], E.s["porque"] = time.strftime("%Y-%m-%d %H:%M:%S"), "acabou a fila"; E.gravar(); log("FILA ACABOU")
    return E


# 03/11 ~19h (ele, na rua: «vai rodando com o tandera o que tiver pra rodar»): UMA fila por vez. A trava GPU_EM_USO deixa passar quem
# é «tandera», então uma fila ligada à mão de noite e a da tarefa das 01h rodavam juntas na mesma placa. A fila que chega com outra viva
# não começa (a viva já puxa o que falta do checklist); a marca de uma fila que morreu sem apagar é ignorada.
FILA_VIVA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trabalho", "filas", "FILA_RODANDO.json")


def _viva(pid):
    if os.name != "nt":
        try: os.kill(pid, 0); return True
        except OSError: return False
    import ctypes
    h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)        # PROCESS_QUERY_LIMITED_INFORMATION
    if not h: return False
    codigo = ctypes.c_ulong()
    ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(codigo))
    ctypes.windll.kernel32.CloseHandle(h)
    return bool(ok) and codigo.value == 259                             # STILL_ACTIVE


def _outra_fila():
    try: m = json.load(open(FILA_VIVA, encoding="utf-8"))
    except (OSError, ValueError): return None
    return m if m.get("pid") != os.getpid() and _viva(int(m.get("pid") or 0)) else None


BATERIA_CLI = [None]      # 06/11: --bateria da linha de comando (vale pra fila inteira; um item pode ter a sua: "bateria")


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="tandera fila")
    ap.add_argument("fila", nargs="?"); ap.add_argument("--pista"); ap.add_argument("arquivos", nargs="*")
    ap.add_argument("--nome"); ap.add_argument("--ate", help="HH:MM: não começa bloco novo depois disso"); ap.add_argument("--bloco", type=int, default=4)
    ap.add_argument("--checklist", action="store_true", help="começa e continua pelo que FALTA no checklist (tandera/checklist.py)")
    ap.add_argument("--com", default="", help="grupos que pedem o OK dele, já liberados (ex.: 4-curso-aulas)")
    ap.add_argument("--bateria", default="", help="só estas baterias (reconhecimento, som, profunda): a fase (06/11)")
    x = ap.parse_args(argv)
    BATERIA_CLI[0] = x.bateria or None
    if sys.stdout is None or not sys.stdout.isatty() and os.environ.get("TANDERA_SEM_JANELA", "1") == "1":
        _sem_janela()
    com = [g for g in x.com.split(",") if g]
    if x.checklist and not x.fila and not x.pista:
        itens, nome = [], x.nome or f"checklist-{time.strftime('%Y%m%d-%H%M')}"
    elif x.pista:
        arqs = _arquivos(([x.fila] if x.fila else []) + x.arquivos)
        itens = [{"arquivo": a, "pista": x.pista} for a in arqs]
        nome = x.nome or f"{x.pista}-{time.strftime('%Y%m%d-%H%M')}"
    else:
        F = json.load(open(x.fila, encoding="utf-8"))
        itens, nome = F["itens"], x.nome or F.get("nome") or os.path.splitext(os.path.basename(x.fila))[0]
    for i in itens:
        if i["pista"] not in PISTAS: raise SystemExit(f"pista desconhecida: {i['pista']}")
        if not os.path.exists(i["arquivo"]): raise SystemExit(f"não existe: {i['arquivo']}")
    outra = _outra_fila()
    if outra:
        base.log(f"já tem uma fila rodando ({outra.get('nome')}, pid {outra.get('pid')}, desde {outra.get('desde')}): esta não começa")
        return
    os.makedirs(os.path.dirname(FILA_VIVA), exist_ok=True)
    json.dump({"pid": os.getpid(), "nome": nome, "desde": time.strftime("%Y-%m-%d %H:%M:%S")}, open(FILA_VIVA, "w", encoding="utf-8"))
    try:
        rodar(itens, nome, x.ate, x.bloco, completar=x.checklist, com=com)
    finally:
        try:
            if json.load(open(FILA_VIVA, encoding="utf-8")).get("pid") == os.getpid(): os.remove(FILA_VIVA)
        except (OSError, ValueError): pass
        # 03/11 (Kakashi 14:15, ele: «o que que acabou se isso aqui não atualizou ainda... atualizar automático, né»): toda fila, ao parar
        # (acabou, deu a hora, Premiere, erro), refaz o checklist — o painel mostra o que ela fez sem ninguém apertar «atualizar»
        try:
            from .checklist import atualizar
            atualizar()
        except Exception as e:
            base.log(f"checklist no fim da fila: {type(e).__name__}: {e}")
