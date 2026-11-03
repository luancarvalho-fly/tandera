# -*- coding: utf-8 -*-
"""O MOTOR: roda as peças pedidas (com as de que elas dependem), na ORDEM, uma por vez na placa, e soma no que já estava guardado.
Peça guardada com a versão atual (e com as entradas iguais) NÃO roda. Cada peça que roda tem o tempo e a placa medidos."""
import importlib, os, time, traceback, types

from . import base
from .armazem import Analise
from .manifesto import ORDEM, PECAS, VERSAO_MOTOR, com_dependencias, padrao


def rodar(video, pecas=None, perfil=None, refazer=(), placa=True, idioma=None, pasta=None, versoes=None, log=base.log, stems=None):
    """video → Analise. pecas = lista (None = as padrão). refazer = peças pra rodar mesmo guardadas. versoes = {peca: versão} pra fingir
    uma versão nova (teste do incremental). stems = {voz, resto|musica[, efeitos, mix]: arquivo} que vieram PRONTOS: valem como a
    separação (nenhum modelo de separação roda) e o que depende deles fica guardado, preso à assinatura desses arquivos."""
    for p, v in (versoes or {}).items():
        PECAS[p]["versao"] = v
    perfil = perfil or base.perfil_da_maquina()
    A = Analise(video, pasta)
    if stems:
        from .pecas import separacao
        stems = separacao.completar(stems)
        A.esperada["separacao"] = (separacao.versao_entregue(stems), "entregue pronta (" + ", ".join(sorted(stems)) + "): " +
                                   " · ".join(os.path.basename(v) for _, v in sorted(stems.items())))
    pedidas = list(pecas or padrao())
    for p in pedidas:
        if p not in PECAS or PECAS[p].get("ferramenta"): raise SystemExit(f"peça desconhecida (ou ferramenta, sem análise): {p}")
    plano = com_dependencias(pedidas)
    ctx = types.SimpleNamespace(placa=placa and _tem_placa(), perfil=perfil, idioma=idioma, log=log, stems=stems)
    rodada = {"quando": time.strftime("%Y-%m-%d %H:%M:%S"), "perfil": perfil, "motor": VERSAO_MOTOR, "pedidas": pedidas, "rodou": {},
              "guardada": [], "falhou": {}, "pulou": {}}
    refeitas = set()
    precisa = {p: A.precisa(p) for p in plano}
    usa_placa = ctx.placa and any(PECAS[p]["onde"] == "placa" and (precisa[p][0] or p in refazer) and not (stems and p == "separacao")
                                  for p in plano)
    ctx.placa_avisada = usa_placa          # 02/11: o preparo do PC só abre o vídeo pela placa (NVDEC) com a placa avisada no Medidor
    vram = max([PECAS[p].get("vram_gb", 0) for p in plano] or [0])
    T0 = time.monotonic()
    with base.Placa(usa_placa, f"Tandera: {os.path.basename(video)} ({len(plano)} peças)", dura_min=max(5, int(len(plano) * 2)), vram=vram):
        for p in plano:
            faz, porque = A.precisa(p, refeitas)
            if p in refazer: faz, porque = True, "pedida de novo (--refazer)"
            if not faz:
                rodada["guardada"].append(p); continue
            if perfil not in PECAS[p]["perfis"]:
                rodada["pulou"][p] = f"não faz parte do perfil {perfil}"; continue
            falta = [d for d in PECAS[p]["depende"] if not A.tem(d) or d in rodada["falhou"]]
            if falta:
                rodada["pulou"][p] = f"falta a entrada: {', '.join(falta)}"; continue
            log(f"▶ {p} — {A.alvo(p)[1]} ({porque})")
            if ctx.placa and PECAS[p]["onde"] == "placa" and p != "olho":
                base.ollama_descarrega()                   # um modelo por vez na placa
            try:
                mod = importlib.import_module(f".pecas.{p}", __package__)
                with base.Medida() as m:
                    res = mod.rodar(A, ctx)
                med = m.resumo()
                A.guardar(p, res, med, perfil)
                refeitas.add(p); rodada["rodou"][p] = dict(med, porque=porque)
                log(f"  ✓ {p} em {med['s']:.1f} s" + (f" · placa pico {med['placa_pico_gb']} GB (+{med['peca_somou_gb']}) · uso médio {med['uso_medio_pct']}%"
                                                       if "placa_pico_gb" in med and PECAS[p]["onde"] == "placa" else ""))
            except (KeyboardInterrupt, SystemExit):
                raise
            except BaseException as e:
                rodada["falhou"][p] = f"{type(e).__name__}: {str(e)[:400]}"
                log(f"  ✗ {p} falhou: {type(e).__name__}: {str(e)[:300]}")
                open(os.path.join(A.pasta, "erros.log"), "a", encoding="utf-8").write(f"\n--- {time.ctime()} {p}\n{traceback.format_exc()}")
            finally:
                base.liberar_torch()
    rodada["s"] = round(time.monotonic() - T0, 1)
    A.d["rodadas"].append(rodada); A.gravar()
    escrever_resumo(A)
    log(f"pronto em {rodada['s']:.0f} s · rodou {len(rodada['rodou'])}, guardadas {len(rodada['guardada'])}, falhou {len(rodada['falhou'])}, "
        f"pulou {len(rodada['pulou'])} → {A.pasta}")
    return A


def _tem_placa():
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False


def escrever_resumo(A):
    L = [f"# Tandera — {os.path.basename(A.video)}", "", f"- vídeo: `{A.video}`", f"- análise guardada: `{A.pasta}`", "",
         "| peça | modelo | versão | perfil | onde | tempo | placa (pico / a peça somou) | quando |", "|---|---|---|---|---|---|---|---|"]
    for p in ORDEM:
        g = A.d["pecas"].get(p)
        if not g: continue
        m = g.get("medida") or {}
        pl = f"{m['placa_pico_gb']} / +{m['peca_somou_gb']} GB · {m['uso_medio_pct']}%" if "placa_pico_gb" in m and g["onde"] == "placa" else "—"
        atual = "" if g["versao"] == PECAS[p]["versao"] or g["versao"].startswith("entregue-") else f" (manifesto: {PECAS[p]['versao']})"
        L.append(f"| {p} | {g['modelo'][:70]} | {g['versao']}{atual} | {g['perfil']} | {g['onde']} | {m.get('s', 0):.1f} s | {pl} | {g['quando']} |")
    L += ["", "## Rodadas", "| quando | perfil | rodou | guardada | falhou | pulou | tempo |", "|---|---|---|---|---|---|---|"]
    for r in A.d["rodadas"]:
        L.append(f"| {r['quando']} | {r['perfil']} | {', '.join(r['rodou']) or '—'} | {', '.join(r['guardada']) or '—'} | "
                 f"{'; '.join(f'{k}: {v[:80]}' for k, v in r['falhou'].items()) or '—'} | {'; '.join(f'{k}: {v}' for k, v in r['pulou'].items()) or '—'} | {r['s']:.0f} s |")
    open(os.path.join(A.pasta, "RESUMO.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
