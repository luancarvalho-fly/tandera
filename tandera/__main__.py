# -*- coding: utf-8 -*-
"""Linha de comando do Tandera (apps\\TANDERA\\tandera.cmd chama isto no ambiente certo):
  tandera analisar <vídeo> [--pecas a,b] [--refazer a,b] [--perfil pc|servidor] [--sem-placa] [--idioma pt] [--pasta P] [--stem voz=W --stem resto=W]
                   [--versao-de peca=versão]     (finge uma versão nova da peça: teste do incremental)
  tandera versao                                   o manifesto: peça · modelo · versão · onde · perfis
  tandera exemplos <vídeo> [--so-contar] [--sem-placa] [--sem-olho] [--idioma en]
                                                   tutorial «só nos exemplos» (02/11): 1ª passada no vídeo inteiro, o pesado só nas janelas
  tandera fala <áudio ou vídeo> [--idioma pt] [--dispositivo cuda|cpu] [--palavras] [--json]
  tandera buscar <vídeo> "frase"                   busca no diário (BM25 + Qwen3-Embedding-8B)
  tandera onde <vídeo>                             a pasta da análise guardada desse vídeo
  tandera painel [--porta 7822] [--sem-abrir]      o painel do checklist no navegador: cada vídeo × cada peça do motor, ▶ rodar
  tandera runpod --grupo G [--pecas diario,busca] [--so-contar] [--manter] | --desligar
                                                   o que falta do grupo, rodado numa placa do RunPod (06/11: PC OU RunPod)
  tandera diarios-gemini [--ate 23:30] [--max N] [--so-contar]
                                                   a cota grátis do Gemini do dia em diários (sem placa; tarefa das 06h)"""
import argparse, json, os, sys

try:
    sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from . import base, versao
from .manifesto import ORDEM, PECAS, TROCAS, VERSAO_MOTOR


def main():
    # fila e checklist têm opções próprias (--pista, --checklist, --ate…): vão direto, sem passar pelo argparse daqui (o REMAINDER dele
    # não aceita opção logo depois do subcomando)
    if len(sys.argv) > 1 and sys.argv[1] in ("fila", "checklist"):
        from .fila import main as fila_main
        from .checklist import main as ck_main
        (fila_main if sys.argv[1] == "fila" else ck_main)(sys.argv[2:]); return
    if len(sys.argv) > 1 and sys.argv[1] == "diarios-gemini":          # 06/11: a cota grátis do dia em diários (tandera/diarios_gemini.py)
        from .diarios_gemini import main as dg_main
        dg_main(sys.argv[2:]); return
    if len(sys.argv) > 1 and sys.argv[1] == "runpod":                  # 06/11: rodar no RunPod em vez do PC (tandera/runpod.py)
        from .runpod import main as runpod_main
        runpod_main(sys.argv[2:]); return
    if len(sys.argv) > 1 and sys.argv[1] == "painel":                  # 04/11: o painel do checklist (tandera/painel.py)
        from .painel import main as painel_main
        painel_main(sys.argv[2:]); return
    ap = argparse.ArgumentParser(prog="tandera", description="o Tandera: um motor de análise só, sempre o mais novo")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analisar"); a.add_argument("video"); a.add_argument("--pecas", default=""); a.add_argument("--refazer", default="")
    a.add_argument("--perfil", choices=["pc", "servidor"]); a.add_argument("--sem-placa", action="store_true"); a.add_argument("--idioma")
    a.add_argument("--pasta"); a.add_argument("--versao-de", action="append", default=[])
    a.add_argument("--stem", action="append", default=[], help="voz/música PRONTAS: voz=<wav> resto=<wav> (ou musica=, efeitos=, mix=)")
    a.add_argument("--pista", help="as peças da PISTA (tandera\\pistas.py: bruto, editado, plexus-stems, tutorial…); --pecas passa por cima")
    a.add_argument("--bateria", help="só estas baterias (reconhecimento, som, profunda; vírgula): a fase da análise (06/11)")
    sub.add_parser("versao")
    sub.add_parser("pistas")
    fl = sub.add_parser("fila", add_help=False); fl.add_argument("resto", nargs=argparse.REMAINDER)
    ck = sub.add_parser("checklist", add_help=False); ck.add_argument("resto", nargs=argparse.REMAINDER)
    e = sub.add_parser("exemplos"); e.add_argument("video"); e.add_argument("--so-contar", action="store_true")
    e.add_argument("--sem-placa", action="store_true"); e.add_argument("--sem-olho", action="store_true"); e.add_argument("--idioma")
    f = sub.add_parser("fala"); f.add_argument("audio"); f.add_argument("--idioma"); f.add_argument("--dispositivo", default="cuda")
    f.add_argument("--palavras", action="store_true"); f.add_argument("--json", action="store_true")
    f.add_argument("--rapido", action="store_true", help="pelo motor já carregado do ditado (8178) com as regras do Tandera; fora do ar = o do Tandera")
    f.add_argument("--modelo", choices=["turbo", "large"], default="turbo", help="large = o large-v3 da dublagem (DUBX, decisão de 23/08), sempre pelo servidor")
    f.add_argument("--srt", help="grava também a legenda SRT aqui"); f.add_argument("--max-len", type=int, default=70)
    r = sub.add_parser("rotular"); r.add_argument("wav"); r.add_argument("--dispositivo", default="cuda")
    rv = sub.add_parser("rotular-varios"); rv.add_argument("lista_json"); rv.add_argument("--dispositivo", default="cpu")
    bt = sub.add_parser("batidas"); bt.add_argument("wav"); bt.add_argument("--dispositivo", default="cuda")
    b = sub.add_parser("buscar"); b.add_argument("video"); b.add_argument("frase"); b.add_argument("-n", type=int, default=8)
    o = sub.add_parser("onde"); o.add_argument("video")
    x = ap.parse_args()
    lista = lambda s: [p.strip() for p in s.split(",") if p.strip()]          # noqa: E731

    if x.cmd == "versao":
        v = versao()
        print(f"TANDERA · motor {VERSAO_MOTOR} · perfil desta máquina: {v['perfil_desta_maquina']}\n")
        print(f"{'peça':<10} {'versão':<11} {'onde':<6} {'perfis':<15} modelo")
        for p in ORDEM + ["pisada"]:
            g = PECAS[p]
            print(f"{p:<10} {g['versao']:<11} {g['onde']:<6} {'+'.join(g['perfis']):<15} {g['modelo']}" + ("  [só quando pedida]" if not g.get("padrao", True) else "")
                  + ("  [ferramenta]" if g.get("ferramenta") else ""))
        print("\no que substituiu o quê:")
        for p, velho, novo in TROCAS:
            print(f"  {p}: {velho}  →  {novo}")
        return
    if x.cmd == "pistas":
        from .pistas import PISTAS, pecas_da
        for n, p in PISTAS.items():
            print(f"{n:<13} {p['o_que']}\n{'':<13} peças: {', '.join(pecas_da(n))}" + (f"\n{'':<13} foto: {', '.join(p['fotos'])}" if p.get("fotos") else "")
                  + (f"\n{'':<13} pesado só nas janelas de exemplo" if p.get("exemplos") else ""))
        return
    if x.cmd == "checklist":
        from .checklist import main as ck_main
        ck_main(x.resto); return
    if x.cmd == "fila":
        from .fila import main as fila_main
        fila_main(x.resto); return
    if x.cmd == "analisar" and x.pista:
        from .pistas import PISTAS, pecas_da, stems_da
        if x.pista not in PISTAS: raise SystemExit(f"pista desconhecida: {x.pista} (tem: {', '.join(PISTAS)})")
        if PISTAS[x.pista].get("exemplos") and not x.pecas:
            from .janelas import exemplos
            exemplos(x.video, not x.sem_placa, x.idioma or PISTAS[x.pista].get("idioma")); return
        if not x.pecas:
            st, caem = stems_da(x.pista, x.video, base.log)
            x.pecas = ",".join(p for p in pecas_da(x.pista, x.video, x.bateria) if p not in caem)
            if st and not x.stem: x.stem = [f"{k}={v}" for k, v in st.items()]
        x.idioma = x.idioma or PISTAS[x.pista].get("idioma")
    if x.cmd == "exemplos":
        from .janelas import exemplos
        r = exemplos(x.video, not x.sem_placa, x.idioma, x.so_contar, not x.sem_olho)
        print(json.dumps({k: v for k, v in r.items() if k not in ("lista", "janelas")} | {"janelas_lista": [
            {k: j[k] for k in ("ini", "fim", "motivos") if k in j} for j in r.get("janelas") or r.get("lista") or []]}, ensure_ascii=False, indent=1))
        return
    if x.cmd == "onde":
        from .armazem import pasta_do_video
        print(pasta_do_video(x.video)); return
    if x.cmd == "fala":
        from .pecas import fala
        if x.modelo == "large" or x.rapido:
            r = fala.transcrever_rapido(x.audio, x.idioma, x.dispositivo, x.palavras or bool(x.srt), modelo=x.modelo, max_len=x.max_len if x.srt else None)
        else:
            r = fala.transcrever(x.audio, x.idioma, x.dispositivo, x.palavras or bool(x.srt))
        if x.srt:
            open(x.srt, "w", encoding="utf-8").write(fala.para_srt(r["segmentos"], x.max_len))
        if x.json: print(json.dumps(r, ensure_ascii=False))
        else:
            for s in r["segmentos"]: print(f"{s['ini']:7.2f}–{s['fim']:7.2f}  {s['txt']}")
        return
    if x.cmd == "batidas":
        from . import batidas
        print(json.dumps(batidas(x.wav, x.dispositivo), ensure_ascii=False)); return
    if x.cmd == "rotular":
        from . import rotular
        print(json.dumps(rotular(x.wav, x.dispositivo), ensure_ascii=False)); return
    if x.cmd == "rotular-varios":
        from . import rotular_varios
        print(json.dumps(rotular_varios(json.load(open(x.lista_json, encoding="utf-8")), x.dispositivo), ensure_ascii=False)); return
    if x.cmd == "buscar":
        from .armazem import Analise
        from .pecas import busca
        for r in busca.buscar(Analise(x.video), x.frase, x.n):
            de = base.mmss(r["de"]) if r.get("de") is not None else "—"
            print(f"{r['nota']:.4f}  {de:>9}  [{r['tipo']}] {r['texto'][:150]}")
        return
    from . import motor
    versoes = dict(v.split("=", 1) for v in x.versao_de)
    motor.rodar(x.video, lista(x.pecas) or None, x.perfil, lista(x.refazer), not x.sem_placa, x.idioma, x.pasta, versoes,
                stems=dict(v.split("=", 1) for v in x.stem) or None)


if __name__ == "__main__":
    main()
