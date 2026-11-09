# -*- coding: utf-8 -*-
"""O LOTE do Tandera (01/11/2026; ele: «um motor só... você sabe quando desligar e ligar um pistão»): vários vídeos, PEÇA POR PEÇA.
O motor.rodar() é um vídeo por vez, e em cada vídeo cada peça carrega o seu modelo de novo (no WSL, 01/11, isso era a maior parte do
tempo de máquina). Aqui cada peça de placa carrega o modelo UMA vez, passa o bloco inteiro, solta, e só então vai pra próxima peça; a
peça de processador que vem depois das de placa (o sinal) roda ao lado enquanto a placa segue.
O resultado de cada vídeo é o MESMO do motor.rodar() e é guardado do mesmo jeito: Analise.guardar, a versão do manifesto, o mesmo
incremental (peça guardada não roda; se nenhum vídeo do bloco precisa da peça, o modelo nem carrega), a mesma regra de perfil e de
entrada que falta, uma rodada por vídeo no analise.json (com «lote»: quantos vídeos e quanto custou carregar cada modelo).
Duas metades (o servidor\\rodar_lote.py chama as duas):
  preparar(item)          o PREPARO de um vídeo (processador): o rodar_lote faz o do próximo bloco enquanto a placa trabalha no atual
  rodar_bloco(itens)      o resto, peça por peça:   python -m tandera.lote <bloco.json> <resultado.json>
item = {"video", "pasta", "pecas", "stems" (voz/resto/musica…: arquivo), "idioma", "refazer", "id"}.
O PC não usa isto: tandera.analisar(video) continua no motor.rodar() (um vídeo), e base.SEGURAR fica False."""
import importlib, json, os, sys, threading, time, traceback, types
from concurrent.futures import ThreadPoolExecutor

from . import base
from .armazem import Analise
from .manifesto import ORDEM, PECAS, VERSAO_MOTOR, com_dependencias, padrao
from .motor import _tem_placa, escrever_resumo

# peças vizinhas que usam o MESMO modelo: o lote não solta entre uma e outra
JUNTAS = {("batida", "musica")}


def _abrir(it, perfil, placa, log):
    """o mesmo começo do motor.rodar(): a análise, os stems entregues (a versão «entregue-…» da separação) e o plano"""
    A = Analise(it["video"], it.get("pasta"))
    stems = it.get("stems") or None
    if stems:
        from .pecas import separacao
        stems = separacao.completar(stems)
        A.esperada["separacao"] = (separacao.versao_entregue(stems), "entregue pronta (" + ", ".join(sorted(stems)) + "): " +
                                   " · ".join(os.path.basename(v) for _, v in sorted(stems.items())))
    pedidas = list(it.get("pecas") or padrao())
    for p in pedidas:
        if p not in PECAS or PECAS[p].get("ferramenta"): raise SystemExit(f"peça desconhecida (ou ferramenta, sem análise): {p}")
    ctx = types.SimpleNamespace(placa=placa, perfil=perfil, idioma=it.get("idioma"), log=log, stems=stems)
    nome = it.get("id") or os.path.basename(A.video)
    return {"it": it, "A": A, "ctx": ctx, "nome": nome, "perfil": perfil, "plano": com_dependencias(pedidas), "pedidas": pedidas,
            "refazer": set(it.get("refazer") or ()), "refeitas": set(), "feitas": set(), "trava": threading.Lock(),
            "rodada": {"quando": time.strftime("%Y-%m-%d %H:%M:%S"), "perfil": perfil, "motor": VERSAO_MOTOR, "pedidas": pedidas,
                       "rodou": {}, "guardada": [], "falhou": {}, "pulou": {}}}


def _decide(v, p):
    """a MESMA regra do motor.rodar(): guardada / fora do perfil / falta a entrada / roda"""
    A, r = v["A"], v["rodada"]
    faz, porque = A.precisa(p, v["refeitas"])
    if p in v["refazer"]: faz, porque = True, "pedida de novo (--refazer)"
    if not faz: return "guardada", porque
    if v["perfil"] not in PECAS[p]["perfis"]: return "pulou", f"não faz parte do perfil {v['perfil']}"
    falta = [d for d in PECAS[p]["depende"] if not A.tem(d) or d in r["falhou"]]
    if falta: return "pulou", f"falta a entrada: {', '.join(falta)}"
    return "roda", porque


def _anota(v, p):
    """decide a peça neste vídeo e anota guardada/pulou; devolve o porquê se ela tem que rodar (None se não)"""
    if p not in v["plano"] or p in v["feitas"]: return None
    v["feitas"].add(p)
    acao, porque = _decide(v, p)
    if acao == "guardada": v["rodada"]["guardada"].append(p)
    elif acao == "pulou": v["rodada"]["pulou"][p] = porque
    else: return porque
    return None


def _guardar(v, p, res, med, porque, log):
    with v["trava"]:                                   # o sinal (ao lado) e a peça de placa gravam o mesmo analise.json
        v["A"].guardar(p, res, med, v["perfil"])
        v["refeitas"].add(p); v["rodada"]["rodou"][p] = dict(med, porque=porque)
    log(f"  ✓ {v['nome']}: {p} em {med['s']:.1f} s" + (f" · placa pico {med['placa_pico_gb']} GB · uso médio {med['uso_medio_pct']}%"
                                                       if "placa_pico_gb" in med and PECAS[p]["onde"] == "placa" else ""))


def _falhou(v, p, e, log):
    with v["trava"]:
        v["rodada"]["falhou"][p] = f"{type(e).__name__}: {str(e)[:400]}"
        open(os.path.join(v["A"].pasta, "erros.log"), "a", encoding="utf-8").write(
            f"\n--- {time.ctime()} {p} (lote)\n" + "".join(traceback.format_exception(type(e), e, e.__traceback__)))
    log(f"  ✗ {v['nome']}: {p} falhou: {type(e).__name__}: {str(e)[:300]}")


def _uma(v, p, porque, log):
    """uma peça num vídeo (o modelo, se a peça é de placa, já está segurado)"""
    log(f"▶ {v['nome']}: {p} — {v['A'].alvo(p)[1][:90]} ({porque})")
    try:
        mod = importlib.import_module(f".pecas.{p}", __package__)
        with base.Medida() as m:
            res = mod.rodar(v["A"], v["ctx"])
        _guardar(v, p, res, m.resumo(), porque, log)
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as e:
        _falhou(v, p, e, log)
    finally:
        base.liberar_torch()


def _separar_juntos(lista, log, trabalho):
    """a separação PELO MODELO de vários vídeos com o BS-Roformer e o BandIt carregados uma vez; o tempo do bloco é rateado pela duração"""
    from .pecas import separacao
    for v, porque in lista:
        log(f"▶ {v['nome']}: separacao — {v['A'].alvo('separacao')[1][:90]} ({porque}) · junto com mais {len(lista) - 1}")
    As = [v["A"] for v, _ in lista]
    try:
        with base.Medida() as m:
            res = separacao.rodar_varios(As, lista[0][0]["ctx"], trabalho)
        med = m.resumo()
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as e:
        for v, _ in lista: _falhou(v, "separacao", e, log)
        return
    finally:
        base.liberar_torch()
    durs = [float(A["preparo"].get("duracao") or 0) for A in As]; tot = sum(durs)
    for (v, porque), r, d in zip(lista, res, durs):
        if isinstance(r, Exception):
            _falhou(v, "separacao", r, log); continue
        parte = med["s"] * (d / tot if tot else 1 / len(lista))
        _guardar(v, "separacao", r, dict(med, s=round(parte, 1), lote={"videos": len(lista), "s_bloco": med["s"],
                                                                         "como": "um BS-Roformer e um BandIt pro bloco; tempo rateado pela duração"}),
                 porque, log)


def preparar(it, perfil=None, placa=True, log=base.log):
    """a metade do PROCESSADOR que abre o vídeo (o preparo: o que não depende de nada) → o que rodou, pra o rodar_bloco somar na rodada"""
    perfil = perfil or base.perfil_da_maquina()
    v = _abrir(it, perfil, placa, log)
    for p in v["plano"]:
        if PECAS[p]["depende"] or PECAS[p]["onde"] != "cpu": continue
        porque = _anota(v, p)
        if porque: _uma(v, p, porque, log)
    r = v["rodada"]
    return {"quando": r["quando"], "rodou": r["rodou"], "guardada": r["guardada"], "falhou": r["falhou"], "pulou": r["pulou"],
            "refeitas": sorted(v["refeitas"]), "feitas": sorted(v["feitas"])}


def rodar_bloco(itens, placa=True, perfil=None, log=base.log, trabalho=None, cpu_ao_lado=2):
    """o bloco, PEÇA POR PEÇA (cada modelo uma vez). itens[i]["previa"] = o que o preparar() já fez nesse vídeo.
    → {"videos": {id: {pasta, rodou, falhou, pulou, guardada}}, "pecas": {peca: {carregar_s, s, videos}}, "s": total}"""
    base.SEGURAR = True
    perfil = perfil or base.perfil_da_maquina()
    tem_placa = bool(placa) and _tem_placa()
    T0 = time.monotonic()
    V, ruins = [], {}
    for it in itens:
        try:
            v = _abrir(it, perfil, tem_placa, log)
        except KeyboardInterrupt:
            raise
        except BaseException as e:                     # (SystemExit inclusive: peça desconhecida, stem que não existe) — só este vídeo
            ruins[it.get("id") or it["video"]] = f"{type(e).__name__}: {str(e)[:400]}"; continue
        pv = it.get("previa") or {}
        r = v["rodada"]
        r["quando"] = pv.get("quando") or r["quando"]
        r["rodou"].update(pv.get("rodou") or {}); r["guardada"] += pv.get("guardada") or []
        r["falhou"].update(pv.get("falhou") or {}); r["pulou"].update(pv.get("pulou") or {})
        v["refeitas"] |= set(pv.get("refeitas") or []); v["feitas"] |= set(pv.get("feitas") or [])
        V.append(v)
    ordem = [p for p in ORDEM if any(p in v["plano"] for v in V)]
    usa_placa = tem_placa and any(PECAS[p]["onde"] == "placa" for p in ordem)
    vram = max([PECAS[p].get("vram_gb", 0) for p in ordem] or [0])
    pecas = {}
    pendentes = {}                                     # peça de processador rodando ao lado → [futuros]
    cpu = ThreadPoolExecutor(cpu_ao_lado)
    log(f"lote: {len(V)} vídeos · peças {', '.join(ordem)}" + (f" · {len(ruins)} não abriram" if ruins else ""))
    try:
        with base.Placa(usa_placa, f"Tandera lote: {len(V)} vídeos ({len(ordem)} peças)", dura_min=max(5, 2 * len(V) * len(ordem)), vram=vram):
            for i, p in enumerate(ordem):
                for d in PECAS[p]["depende"]:              # a peça de processador de que esta depende tem que ter acabado
                    for f in pendentes.pop(d, []): f.result()
                quem = [(v, porque) for v in V for porque in [_anota(v, p)] if porque]
                if not quem: continue
                if PECAS[p]["onde"] != "placa":
                    t0 = time.monotonic()
                    fs = [cpu.submit(_uma, v, p, porque, log) for v, porque in quem]
                    pendentes[p] = fs
                    pecas[p] = {"carregar_s": 0.0, "videos": len(quem), "ao_lado": True, "_t0": t0}
                    continue
                if tem_placa and p != "olho":
                    base.ollama_descarrega()               # um modelo por vez na placa
                mod = importlib.import_module(f".pecas.{p}", __package__)
                t0 = time.monotonic(); carregar = None
                if hasattr(mod, "aquecer") and not (p == "separacao"):
                    try:
                        with base.Medida() as m:
                            mod.aquecer(quem[0][0]["ctx"])
                        carregar = m.resumo()["s"]
                        log(f"⚙ {p}: modelo carregado UMA vez em {carregar:.1f} s pra {len(quem)} vídeo(s)")
                    except (KeyboardInterrupt, SystemExit):
                        raise
                    except BaseException as e:            # não carregou junto: cada vídeo tenta carregar sozinho (e falha sozinho)
                        log(f"⚙ {p}: não carregou de uma vez ({type(e).__name__}: {str(e)[:200]}); cada vídeo tenta sozinho")
                if p == "separacao":
                    entregue = [(v, q) for v, q in quem if v["ctx"].stems]
                    modelo = [(v, q) for v, q in quem if not v["ctx"].stems]
                    for v, q in entregue: _uma(v, p, q, log)
                    if modelo: _separar_juntos(modelo, log, trabalho)
                else:
                    for v, q in quem: _uma(v, p, q, log)
                prox = ordem[i + 1] if i + 1 < len(ordem) else None
                if (p, prox) not in JUNTAS:
                    base.soltar_segurados()
                    if hasattr(mod, "soltar"):
                        try: mod.soltar()
                        except Exception: pass
                pecas[p] = {"carregar_s": carregar, "s": round(time.monotonic() - t0, 1), "videos": len(quem)}
            for p, fs in pendentes.items():
                for f in fs: f.result()
            pendentes = {}
    finally:
        cpu.shutdown(wait=True)
        base.soltar_segurados()
        base.SEGURAR = False
        for p, x in pecas.items():                         # a peça ao lado: o tempo de processador dela (soma dos vídeos), não a espera
            if x.pop("_t0", None) is not None:
                x["s"] = round(sum((v["rodada"]["rodou"].get(p) or {}).get("s") or 0 for v in V), 1)
    out = {"videos": {}, "pecas": pecas, "ruins": ruins, "s": round(time.monotonic() - T0, 1)}
    carregou = {p: x["carregar_s"] for p, x in pecas.items() if x.get("carregar_s")}
    for v in V:
        r = v["rodada"]
        r["s"] = round(sum((x.get("s") or 0) for x in r["rodou"].values()), 1)
        r["lote"] = {"videos": len(V), "carregar_s": carregou,
                     "obs": "rodada do LOTE (tandera\\lote.py): peça por peça, o modelo carregado uma vez pro bloco; «s» de cada peça = só este vídeo"}
        with v["trava"]:
            v["A"].d["rodadas"].append(r); v["A"].gravar()
        escrever_resumo(v["A"])
        from .pecas.separacao import soltar_sons
        soltar_sons(v["A"], log)                       # 09/11: o som do bruto e o som48k não ficam no C depois da análise (refazem iguais)
        log(f"pronto {v['nome']}: rodou {len(r['rodou'])}, guardadas {len(r['guardada'])}, falhou {len(r['falhou'])}, pulou {len(r['pulou'])} → {v['A'].pasta}")
        out["videos"][v["nome"]] = {"pasta": v["A"].pasta, "rodou": {p: x.get("s") for p, x in r["rodou"].items()}, "falhou": r["falhou"],
                                    "pulou": r["pulou"], "guardada": r["guardada"]}
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except AttributeError:
        pass
    B = json.load(open(sys.argv[1], encoding="utf-8"))
    r = rodar_bloco(B["itens"], placa=B.get("placa", True), perfil=B.get("perfil"), trabalho=B.get("trabalho"))
    base.salvar_json(sys.argv[2], r)


if __name__ == "__main__":
    main()
