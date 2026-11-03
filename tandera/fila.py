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
    if os.name != "nt": return
    orig = subprocess.Popen.__init__

    def init(self, *a, **k):
        if not k.get("creationflags"): k["creationflags"] = base.SEM_JANELA
        return orig(self, *a, **k)
    subprocess.Popen.__init__ = init


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


class LinhaNuvem(threading.Thread):
    def __init__(self, log):
        super().__init__(daemon=True)
        self.q, self.log, self.prontos, self.trava = queue.Queue(), log, [], threading.Lock()
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
                if self.parar or self.sem_cota: continue
                motor.rodar(video, ["diario"], placa=False, log=self.log)
                A = Analise(video)
                erro = ((A.d.get("rodadas") or [{}])[-1].get("falhou") or {}).get("diario", "")
                if "sem cota" in erro.lower():
                    self.sem_cota = True
                    self.log("☁ sem cota no Gemini: os diários que faltam ficam pra próxima noite (o checklist guarda)")
                elif A.tem("diario") and quer_busca:
                    with self.trava: self.prontos.append(video)
            except Exception as e:
                self.log(f"☁ diário de {os.path.basename(video)} falhou: {type(e).__name__}: {str(e)[:200]}")
            finally:
                with self.trava: self.pendentes -= 1

    def pegar_prontos(self):
        with self.trava:
            p, self.prontos = self.prontos, []
        return p


def _busca(lote, nuvem, log):
    """o bloquinho da busca: os vídeos cujo diário ficou pronto (modelo da busca carregado uma vez pra todos)"""
    vs = nuvem.pegar_prontos()
    if not vs: return
    log(f"busca: {len(vs)} vídeo(s) com o diário pronto")
    try:
        lote.rodar_bloco([{"video": v, "pecas": list(DEPOIS_DA_NUVEM), "id": os.path.basename(v)} for v in vs], placa=True, log=log)
    except SystemExit:
        raise
    except Exception as e:
        log(f"✗ bloquinho da busca falhou: {type(e).__name__}: {str(e)[:300]}")


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
                    st, caem = stems_da(pista, i["arquivo"], log)
                    todas = [p for p in pecas_da(pista, i["arquivo"]) if p not in caem]
                    pecas = [p for p in todas if p not in NUVEM + DEPOIS_DA_NUVEM]
                    if any(p in todas for p in NUVEM):
                        i["_nuvem"] = any(p in todas for p in DEPOIS_DA_NUVEM)      # o diário vai pra linha da nuvem depois do bloco
                    if not pecas:                                                # só falta diário/busca: nada na placa agora
                        if "_nuvem" in i: nuvem.por(i["arquivo"], i.pop("_nuvem"))
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
    while nuvem.pendentes and not nuvem.sem_cota and not _parar(ate):
        time.sleep(20)
        try: _busca(lote, nuvem, log)
        except SystemExit: break
    nuvem.parar = True
    try: _busca(lote, nuvem, log)
    except SystemExit: pass
    E.s["parou"], E.s["porque"] = time.strftime("%Y-%m-%d %H:%M:%S"), "acabou a fila"; E.gravar(); log("FILA ACABOU")
    return E


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="tandera fila")
    ap.add_argument("fila", nargs="?"); ap.add_argument("--pista"); ap.add_argument("arquivos", nargs="*")
    ap.add_argument("--nome"); ap.add_argument("--ate", help="HH:MM: não começa bloco novo depois disso"); ap.add_argument("--bloco", type=int, default=4)
    ap.add_argument("--checklist", action="store_true", help="começa e continua pelo que FALTA no checklist (tandera/checklist.py)")
    ap.add_argument("--com", default="", help="grupos que pedem o OK dele, já liberados (ex.: 4-curso-aulas)")
    x = ap.parse_args(argv)
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
    rodar(itens, nome, x.ate, x.bloco, completar=x.checklist, com=com)
