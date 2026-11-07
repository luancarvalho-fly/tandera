# -*- coding: utf-8 -*-
"""OS DIÁRIOS DO GEMINI, TODO DIA (06/11, Luan: «um aviso todo dia pra gente não esquecer de fazer o diário do Gemini... se eu não
direcionar durante o dia você automaticamente já dispara ele pra uma escolha sua, que aí no longo prazo a gente vai ter todos os
diários via Gemini»).

  tandera diarios-gemini [--ate 23:30] [--max N] [--so-contar]

O que faz (sem placa: só a nuvem do Gemini, o PC só manda a cópia 480p; pode rodar com o Premiere aberto):
  1. gasta a cota grátis do dia (20 pedidos por modelo Flash por dia; 1 vídeo = 1 pedido; o Tandera reveza os Flash) até ela acabar
     (SemCota) ou até a hora do --ate;
  2. A ORDEM: primeiro o que ELE escolheu (trabalho\\diarios-gemini\\ESCOLHA.txt: um grupo do checklist, um nome de arquivo ou uma pasta
     por linha; o que já tem diário do Gemini sai sozinho); depois os vídeos SEM diário, na prioridade do checklist; depois os diários
     que saíram pelo GEMMA (troca pelo do Gemini, que ouve o som);
  3. quando troca um diário do Gemma pelo do Gemini, a BUSCA daquele vídeo fica marcada como «falta» (ela foi feita em cima do diário
     velho) e a próxima fila/RunPod refaz;
  4. grupos que pedem o OK dele (o curso) ficam de fora;
  5. o relatório do dia: trabalho\\diarios-gemini\\<data>.md (o que fez, quanto falta e em quantos dias acaba no ritmo de hoje)."""
import argparse, json, os, time

from . import base
from .armazem import Analise

PASTA = os.path.join(base.TANDERA, "trabalho", "diarios-gemini")
ESCOLHA = os.path.join(PASTA, "ESCOLHA.txt")
CHECKLIST = os.path.join(base.TANDERA, "checklist", "checklist.json")


def _escolha():
    if not os.path.exists(ESCOLHA): return []
    return [l.strip() for l in open(ESCOLHA, encoding="utf-8-sig") if l.strip() and not l.strip().startswith("#")]


def fila():
    """[(item do checklist, motivo)] na ordem: escolha dele → sem diário → diário do Gemma"""
    C = json.load(open(CHECKLIST, encoding="utf-8"))
    G = C["grupos"]
    prio = lambda a: (G.get(a.get("grupo"), {}).get("prioridade", 99), a.get("duracao_s") or 0)   # noqa: E731
    ok = [a for a in C["arquivos"] if a.get("analise") and os.path.exists(os.path.join(a["analise"], "analise.json"))
          and not G.get(a.get("grupo"), {}).get("pedir_ok") and a.get("situacao") != "fora"]
    falta = lambda a: "diario" in (a.get("falta") or []) or "preparo" in (a.get("falta") or [])        # noqa: E731
    gemma = lambda a: (a.get("fontes") or {}).get("diario") == "Gemma"                                # noqa: E731
    pedidos = _escolha()
    def linha(a):
        """a 1ª linha do ESCOLHA que pega este arquivo (a ORDEM das linhas é a prioridade dele: câmera antes do iPhone, 06/11); None = nenhuma"""
        c = (a.get("caminho") or "").lower()
        return next((n for n, p in enumerate(pedidos) if p.lower() == a.get("grupo", "").lower() or p.lower() in c), None)
    out, vistos = [], set()
    esc = [(linha(a), a) for a in ok if pedidos and (falta(a) or gemma(a))]
    for _, a in sorted(((n, a) for n, a in esc if n is not None), key=lambda x: (x[0], *prio(x[1]))):
        out.append((a, "escolha dele")); vistos.add(a["analise"])
    for a in sorted(ok, key=prio):
        if a["analise"] not in vistos and falta(a) and "preparo" not in (a.get("falta") or []):
            out.append((a, "sem diário")); vistos.add(a["analise"])
    for a in sorted(ok, key=prio):
        if a["analise"] not in vistos and gemma(a): out.append((a, "trocar o do Gemma")); vistos.add(a["analise"])
    return out


def rodar(ate=None, maximo=None, so_contar=False):
    from .motor import rodar as motor_rodar
    from .pecas import diario
    os.makedirs(PASTA, exist_ok=True)
    F = fila()
    tot = {"escolha dele": 0, "sem diário": 0, "trocar o do Gemma": 0}
    for _, m in F: tot[m] += 1
    base.log(f"diários do Gemini: {len(F)} na fila · " + " · ".join(f"{k} {v}" for k, v in tot.items()))
    if so_contar: return
    feitos, falhas, parou = [], [], "a fila acabou"
    for a, motivo in F:
        if maximo and len(feitos) >= maximo: parou = f"--max {maximo}"; break
        if ate and time.strftime("%H:%M") >= ate: parou = f"hora ({ate})"; break
        A = Analise(a.get("caminho") or a["analise"], a["analise"])
        era_gemma = A.tem("diario") and (A.get("diario") or {}).get("fonte") == "gemma"
        try:
            motor_rodar(a.get("caminho") or a["analise"], ["diario"], placa=False, pasta=a["analise"],
                        refazer=["diario"] if era_gemma else ())
        except diario.SemCota as e:
            parou = f"a cota do dia acabou ({str(e)[:120]})"; break
        except SystemExit as e:
            falhas.append((a["analise"], str(e)[:200])); continue
        except Exception as e:
            falhas.append((a["analise"], f"{type(e).__name__}: {str(e)[:200]}")); continue
        A = Analise(a.get("caminho") or a["analise"], a["analise"])
        d = A.get("diario") or {}
        if A.tem("diario") and d.get("fonte") != "gemma":
            if era_gemma and "busca" in A.d["pecas"]:       # a busca foi feita no diário do Gemma: fica marcada pra refazer
                A.d["pecas"].pop("busca"); A.gravar()
            feitos.append((os.path.basename(a["analise"]), motivo, d.get("modelo") or ""))
            base.log(f"  ✓ {os.path.basename(a['analise'])} ({motivo})")
        else:
            falhas.append((a["analise"], "o diário não saiu do Gemini"))
            # o motor sem placa levanta o erro do Gemini dentro dele; a «falha» com 429 em todos os Flash = cota do dia
            if time.time() < diario._SEM_COTA[0]: parou = "a cota do dia acabou"; break
    resto = len(F) - len(feitos)
    dias = f"{resto / len(feitos):.0f}" if feitos and parou.startswith("a cota") else "?"   # só um dia de cota cheia mede o ritmo
    hoje = time.strftime("%Y-%m-%d")
    L = [f"# Diários do Gemini — {hoje} {time.strftime('%H:%M')}", "",
         f"**feitos hoje: {len(feitos)}** · parou: {parou} · faltam {resto} (no ritmo de hoje: ~{dias} dias)", "",
         "| vídeo | por quê | modelo |", "|---|---|---|"] + [f"| {n} | {m} | {mod} |" for n, m, mod in feitos]
    if falhas: L += ["", "## Falharam", ""] + [f"- {os.path.basename(p)}: {e}" for p, e in falhas[:40]]
    L += ["", f"Escolher o que vai primeiro amanhã: uma linha por grupo/arquivo/pasta em `{ESCOLHA}`."]
    open(os.path.join(PASTA, hoje + ".md"), "a", encoding="utf-8").write("\n".join(L) + "\n\n")
    base.salvar_json(os.path.join(PASTA, "ultimo.json"), {"quando": time.strftime("%Y-%m-%d %H:%M:%S"), "feitos": len(feitos),
                                                          "faltam": resto, "dias": dias, "parou": parou, "falhas": len(falhas)})
    base.log(f"fim: {len(feitos)} feitos · parou: {parou} · faltam {resto}")
    if feitos:                                   # o checklist (e o botão «tandera · N faltam» da tela de projetos) já mostra o de hoje
        try:
            from .checklist import main as ck_main
            ck_main([])
        except Exception as e:
            base.log("aviso: não atualizei o checklist:", e)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tandera diarios-gemini")
    ap.add_argument("--ate", help="HH:MM: não começa vídeo novo depois disso"); ap.add_argument("--max", type=int)
    ap.add_argument("--so-contar", action="store_true")
    x = ap.parse_args(argv)
    base.sem_janela()
    rodar(x.ate, x.max, x.so_contar)
