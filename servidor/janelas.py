# -*- coding: utf-8 -*-
"""JANELAS DE EXEMPLO dos tutoriais no SERVIDOR (lote do som no RunPod, 01/11/2026; o janelas_maquina.py da máquina importa isto).
A receita mora UMA vez só em tandera\\janelas.py (02/11: o PC roda a mesma — `tandera.cmd exemplos <vídeo>`); aqui fica a linha de
comando de sempre. 02/11 (B0): sem «with/without» nos gatilhos.
  python janelas.py <pasta da análise 1ª passada> <vídeo> <saída dos cortes> [--so-contar]"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))          # apps\TANDERA (o pacote tandera)
from tandera.janelas import FOLGA, GATILHOS, JUNTA, MUSICA_MIN, achar, cortar  # noqa: E402,F401


def main():
    pasta, video, saida = sys.argv[1:4]
    jan, dur = achar(pasta)
    cob = sum(j["fim"] - j["ini"] for j in jan)
    print(json.dumps({"janelas": len(jan), "dur": dur, "cobertura_s": round(cob, 1), "cobertura_pct": round(100 * cob / dur, 1) if dur else None,
                      "lista": jan}, ensure_ascii=False, indent=1))
    if "--so-contar" in sys.argv: return
    os.makedirs(saida, exist_ok=True)
    for n, j in enumerate(jan, 1):
        t0 = time.monotonic()
        d = os.path.join(saida, f"j{n:02d}_{int(j['ini']):05d}-{int(j['fim']):05d}.mkv")
        como = cortar(video, j["ini"], j["fim"], d)
        print(f"{os.path.basename(d)}: {j['fim'] - j['ini']:.1f} s pela {como} em {time.monotonic() - t0:.1f} s", flush=True)


if __name__ == "__main__":
    main()
