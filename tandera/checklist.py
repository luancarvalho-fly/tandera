# -*- coding: utf-8 -*-
"""O CHECKLIST DE ANÁLISE do Tandera (03/11/2026). Ele (03/11 ~09h): «vale a pena a gente criar um checklist de análise do Tandera, que a
gente já tem, pra gente não refazer, e só fazer coisas se alguma peça do motor se atualizou, ou alguma coisa a mais que ainda não foi
feita... pra eu conseguir ter esse controle, desse registro de coisas que foram analisadas, que não foram analisadas, que podem ser
analisadas no tempo ocioso».
  - A LISTA: checklist\\arquivos.json = cada arquivo dele que pode ser analisado (grupo, pista, prioridade); nasceu do inventário de 02/11
    (1.139 arquivos medidos) e cresce com `tandera.cmd checklist --somar <pasta> --grupo G --pista P`. Duplicado (mesma assinatura),
    arquivo vazio e material de outra pessoa ficam fora, com o motivo.
  - O ESTADO de cada peça da pista, lido das análises guardadas (analises\\<nome>_<assinatura>\\analise.json):
      ok = feita na versão atual · velha = a peça do motor atualizou · falta = nunca rodou · falhou = rodou e deu erro
    Só «velha» e «falta» (e «falhou») viram trabalho: o que está ok NUNCA roda de novo (o incremental do motor garante o mesmo).
  - A FILA DO TEMPO OCIOSO: `tandera.cmd checklist --fila` = só o que falta, na ordem das prioridades, com a estimativa de máquina;
    `tandera.cmd fila --checklist --ate 08:30` roda e, quando acabar, puxa o próximo do checklist até a hora (03/11: a fila acabou às 05h
    e o PC ficou parado até ele acordar).
  - Grupo com `pedir_ok` (o curso: aula inteira só com o OK dele) fica de fora da fila até ele liberar (`--com` grupo).
Escreve checklist\\CHECKLIST.md (o resumo por grupo + o que falta) e checklist\\checklist.json.
  tandera.cmd checklist                       atualiza e mostra o resumo
  tandera.cmd checklist --fila [--horas 8] [--com grupo,grupo]   monta trabalho\\fila-checklist.json
  tandera.cmd checklist --somar <pasta> --grupo G --pista P [--prioridade N]"""
import json, os, re, time

from . import base
from .armazem import assinatura
from .manifesto import ORDEM, PECAS
from .pistas import FOTOS, PISTAS, VIDEOS, pecas_da

PASTA = os.path.join(base.TANDERA, "checklist")
LISTA = os.path.join(PASTA, "arquivos.json")
CACHE = os.path.join(PASTA, "assinaturas.json")          # (caminho, tamanho, data) → assinatura: o HD não é relido a cada vez


def _ler(p, padrao):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return padrao


def lista():
    return _ler(LISTA, {"grupos": {}, "arquivos": []})


def _assinatura(caminho, cache):
    st = os.stat(caminho); k = f"{caminho}|{st.st_size}|{int(st.st_mtime)}"
    if k not in cache: cache[k] = assinatura(caminho)
    return cache[k], st


def _indice_analises():
    """assinatura → pasta da análise com mais peças"""
    ind = {}
    if not os.path.isdir(base.ANALISES): return ind
    for d in os.listdir(base.ANALISES):
        a = os.path.join(base.ANALISES, d, "analise.json")
        m = re.search(r"_([0-9a-f]{12})$", d)
        if not m or not os.path.exists(a): continue
        n = len(_ler(a, {}).get("pecas", {}))
        if m.group(1) not in ind or n > ind[m.group(1)][1]: ind[m.group(1)] = (os.path.join(base.ANALISES, d), n)
    return {k: v[0] for k, v in ind.items()}


def _velocidade():
    """segundos de máquina por segundo de vídeo de cada peça (mediana das análises do perfil pc com duração) — pra estimar a fila"""
    med = {}
    for d in os.listdir(base.ANALISES) if os.path.isdir(base.ANALISES) else []:
        A = _ler(os.path.join(base.ANALISES, d, "analise.json"), {})
        dur = float((_ler(os.path.join(base.ANALISES, d, "pecas", "preparo.json"), {}).get("duracao")) or 0)
        if dur < 20: continue
        for p, g in A.get("pecas", {}).items():
            s = (g.get("medida") or {}).get("s")
            if g.get("perfil") == "pc" and s: med.setdefault(p, []).append(s / dur)
    out = {}
    for p, v in med.items():
        v.sort(); out[p] = round(v[len(v) // 2], 3)
    return out


def estado_pecas(pasta, pecas):
    """peça → ok / velha / falta / falhou (+ o motivo)"""
    A = _ler(os.path.join(pasta, "analise.json"), {}) if pasta else {}
    G = A.get("pecas", {})
    ult = {}
    for r in A.get("rodadas", []):
        for p, m in (r.get("falhou") or {}).items(): ult[p] = m
        for p in r.get("rodou") or {}: ult.pop(p, None)
    out = {}
    for p in pecas:
        g = G.get(p)
        if not g:
            out[p] = ("falhou", ult[p][:120]) if p in ult else ("falta", "")
        elif str(g.get("versao", "")).startswith("entregue-") or g.get("versao") == PECAS[p]["versao"]:
            out[p] = ("ok", g.get("perfil", ""))
            if p == "diario":         # 04/11 (Kakashi 14:31): «Diário Gema e Diário Gemini, tá ligado?» — os dois valem; a tela diz qual
                dj = _ler(os.path.join(pasta, "pecas", "diario.json"), {})
                gemma = dj.get("fonte") == "gemma" or str(dj.get("modelo") or "").startswith("gemma")
                out[p] = ("ok", "Gemma" if gemma else "Gemini")
        else:
            out[p] = ("velha", f"{g.get('versao')} → {PECAS[p]['versao']}")
    return out


def atualizar(log=base.log):
    L = lista(); cache = _ler(CACHE, {}); ind = _indice_analises(); vel = _velocidade()
    linhas, vistos = [], {}
    for a in L["arquivos"]:
        r = dict(a)
        if a.get("fora"):
            r["situacao"] = "fora"; linhas.append(r); continue
        if not os.path.exists(a["caminho"]):
            r["situacao"] = "sumiu"; linhas.append(r); continue
        try:
            sig, st = _assinatura(a["caminho"], cache)
        except OSError as e:
            r["situacao"] = f"não abre: {e}"; linhas.append(r); continue
        if st.st_size == 0:
            r["situacao"] = "vazio (0 byte)"; linhas.append(r); continue
        if sig in vistos:
            r["situacao"] = f"duplicado de {os.path.basename(vistos[sig])}"; linhas.append(r); continue
        vistos[sig] = a["caminho"]
        g = L["grupos"].get(a["grupo"], {})
        pista = a.get("pista") or g.get("pista") or "editado"
        pecas = pecas_da(pista, a["caminho"])
        pasta = ind.get(sig)
        e = estado_pecas(pasta, pecas)
        dur = float(a.get("duracao_s") or 0)
        trabalho = [p for p, (s, _) in e.items() if s != "ok"]
        r.update(assinatura=sig, pista=pista, analise=pasta, pecas={p: s for p, (s, _) in e.items()},
                 motivos={p: m for p, (s, m) in e.items() if m and s != "ok"},
                 fontes={p: m for p, (s, m) in e.items() if s == "ok" and p == "diario"},
                 situacao="completo" if not trabalho else ("nunca analisado" if not pasta else "falta peça"),
                 falta=trabalho, maquina_s=round(sum(vel.get(p, 0.3) for p in trabalho if PECAS[p]["onde"] != "nuvem") * dur, 1))
        linhas.append(r)
    base.salvar_json(CACHE, cache)
    C = {"atualizado": time.strftime("%Y-%m-%d %H:%M:%S"), "velocidade_s_por_s": vel, "grupos": L["grupos"], "arquivos": linhas}
    base.salvar_json(os.path.join(PASTA, "checklist.json"), C)
    _escrever_md(C)
    return C


def _h(s): return f"{s / 3600:.1f} h"


def _escrever_md(C):
    grupos = C["grupos"]
    ordem = sorted(grupos, key=lambda g: grupos[g].get("prioridade", 99))
    L = ["# Checklist de análise do Tandera", "",
         f"Atualizado: {C['atualizado']} · `tandera.cmd checklist` atualiza · `tandera.cmd fila --checklist --ate 08:30` roda o que falta",
         "", "**ok** = feito na versão atual (nunca roda de novo) · **velha** = a peça do motor atualizou · **falta** = nunca rodou · **falhou** = deu erro", "",
         "| # | grupo | pista | arquivos | vídeo | completos | falta peça | nunca analisados | máquina que falta | obs |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for n, g in enumerate(ordem, 1):
        its = [a for a in C["arquivos"] if a["grupo"] == g and a.get("situacao") in ("completo", "falta peça", "nunca analisado")]
        fora = [a for a in C["arquivos"] if a["grupo"] == g and a.get("situacao") not in ("completo", "falta peça", "nunca analisado")]
        dur = sum(float(a.get("duracao_s") or 0) for a in its)
        c = {s: sum(1 for a in its if a["situacao"] == s) for s in ("completo", "falta peça", "nunca analisado")}
        obs = ("**só com o OK dele** · " if grupos[g].get("pedir_ok") else "") + (f"{len(fora)} fora (duplicado/vazio/outra pessoa)" if fora else "")
        L.append(f"| {grupos[g].get('prioridade', '')} | {g} | {grupos[g].get('pista', '')} | {len(its)} | {_h(dur)} | {c['completo']} | {c['falta peça']} | "
                 f"{c['nunca analisado']} | {_h(sum(a.get('maquina_s', 0) for a in its))} | {obs} |")
    L += ["", "## O que falta, por peça (quantos arquivos)", "", "| grupo | " + " | ".join(ORDEM) + " |", "|---|" + "---|" * len(ORDEM)]
    for g in ordem:
        its = [a for a in C["arquivos"] if a["grupo"] == g and a.get("pecas")]
        cel = []
        for p in ORDEM:
            st = [a["pecas"].get(p) for a in its if p in a["pecas"]]
            if not st: cel.append(""); continue
            ok = st.count("ok"); resto = len(st) - ok
            cel.append(f"{ok}/{len(st)}" + (f" ({st.count('velha')} velha)" if st.count("velha") else "") + (f" ({st.count('falhou')} erro)" if st.count("falhou") else ""))
        L.append(f"| {g} | " + " | ".join(cel) + " |")
    L += ["", "## Arquivo por arquivo", ""]
    for g in ordem:
        L += [f"### {g}", "", "| arquivo | duração | situação | falta | obs |", "|---|---|---|---|---|"]
        for a in [a for a in C["arquivos"] if a["grupo"] == g]:
            obs = "; ".join(f"{p}: {m}" for p, m in (a.get("motivos") or {}).items())[:160] or (a.get("nota") or "")
            L.append(f"| {os.path.basename(a['caminho'])} | {base.mmss(float(a.get('duracao_s') or 0), 0)} | {a.get('situacao')} | "
                     f"{', '.join(a.get('falta') or [])} | {obs} |")
        L.append("")
    open(os.path.join(PASTA, "CHECKLIST.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


def pendentes(C=None, com=(), excluir=(), horas=None):
    """os arquivos com trabalho, na ordem das prioridades (dentro do grupo: o que já tem análise primeiro, depois o mais curto)"""
    C = C or atualizar()
    g = C["grupos"]
    its = [a for a in C["arquivos"] if a.get("falta") and a["caminho"] not in excluir
           and (not g.get(a["grupo"], {}).get("pedir_ok") or a["grupo"] in com)]
    its.sort(key=lambda a: (g.get(a["grupo"], {}).get("prioridade", 99), a.get("situacao") != "falta peça", float(a.get("duracao_s") or 0)))
    if horas:
        out, t = [], 0.0
        for a in its:
            if t > horas * 3600: break
            out.append(a); t += a.get("maquina_s", 0)
        its = out
    return [{"arquivo": a["caminho"], "pista": a["pista"], "grupo": a["grupo"], "dur": a.get("duracao_s"), "idioma": g.get(a["grupo"], {}).get("idioma"),
             "nota": "falta: " + ", ".join(a["falta"])} for a in its]


def somar(pasta, grupo, pista, prioridade=None):
    L = lista()
    if pista not in PISTAS: raise SystemExit(f"pista desconhecida: {pista}")
    L["grupos"].setdefault(grupo, {"pista": pista, "prioridade": prioridade or 50})
    ja = {a["caminho"] for a in L["arquivos"]}
    n = 0
    for raiz, _, fs in os.walk(pasta):
        for f in sorted(fs):
            c = os.path.join(raiz, f)
            if f.lower().endswith(VIDEOS + FOTOS) and not f.startswith("._") and c not in ja:
                try: d = float(base.ffprobe(c, "-show_entries", "format=duration", "-of", "csv=p=0") or 0)
                except Exception: d = 0
                L["arquivos"].append({"grupo": grupo, "caminho": c, "duracao_s": round(d, 1)}); n += 1
    base.salvar_json(LISTA, L)
    return n


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="tandera checklist")
    ap.add_argument("--fila", action="store_true"); ap.add_argument("--horas", type=float); ap.add_argument("--com", default="")
    ap.add_argument("--somar"); ap.add_argument("--grupo"); ap.add_argument("--pista"); ap.add_argument("--prioridade", type=int)
    x = ap.parse_args(argv)
    if x.somar:
        print(f"{somar(x.somar, x.grupo, x.pista, x.prioridade)} arquivos novos no grupo {x.grupo}")
    C = atualizar()
    print(open(os.path.join(PASTA, "CHECKLIST.md"), encoding="utf-8").read().split("## O que falta, por peça")[0])
    if x.fila:
        its = pendentes(C, com=[g for g in x.com.split(",") if g], horas=x.horas)
        arq = os.path.join(base.TANDERA, "trabalho", "fila-checklist.json")
        base.salvar_json(arq, {"nome": "checklist-" + time.strftime("%Y%m%d-%H%M"), "itens": its})
        print(f"fila: {len(its)} arquivos → {arq}")
