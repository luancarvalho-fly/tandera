# -*- coding: utf-8 -*-
"""Compara uma análise do Tandera (a pasta com analise.json + pecas/) com a de referência, peça por peça, com as tolerâncias que o Luan
usou pra dizer «igual» entre o PC e o Linux (01/11, panelas e lote): corte no MESMO quadro; palavra com o mesmo texto e o tempo a ≤ 40 ms;
batida e ataque a ≤ 10 ms; rótulo com a mesma 1ª etiqueta. Só biblioteca padrão (roda em qualquer Python).

  python comparar.py <análise nova> <análise de referência>
  ex.: python comparar.py ~/tandera/analises/exemplo-sintetico_XXXX  sintetico/resultado-pc-processador
Sai uma linha por peça (IGUAL / PERTO / DIFERENTE, com os números) e o código 1 se alguma ficou DIFERENTE."""
import json, os, sys


def ler(pasta, peca):
    p = os.path.join(pasta, "pecas", peca + ".json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def perto(a, b, tol):
    """quantos de a têm um par em b a ≤ tol (cada um de b usado uma vez)"""
    b = sorted(b); usados, n = set(), 0
    for x in sorted(a):
        melhor = min((j for j in range(len(b)) if j not in usados), key=lambda j: abs(b[j] - x), default=None)
        if melhor is not None and abs(b[melhor] - x) <= tol:
            usados.add(melhor); n += 1
    return n


def main(nova, ref):
    ruim, linhas = False, []

    def diz(peca, estado, txt):
        nonlocal ruim
        ruim |= estado == "DIFERENTE"
        linhas.append(f"{peca:<10} {estado:<9} {txt}")
    c1, c2 = ler(nova, "cortes"), ler(ref, "cortes")
    if c1 and c2:
        n = perto(c1["cortes"], c2["cortes"], 0)
        diz("cortes", "IGUAL" if n == len(c1["cortes"]) == len(c2["cortes"]) else "DIFERENTE",
            f"{n} no mesmo quadro · nova {c1['cortes']} · ref {c2['cortes']}")
    f1, f2 = ler(nova, "fala"), ler(ref, "fala")
    if f1 and f2:
        p1, p2 = f1.get("palavras", []), f2.get("palavras", [])
        txt1 = " ".join(w["p"].lower().strip(".,!?") for w in p1); txt2 = " ".join(w["p"].lower().strip(".,!?") for w in p2)
        pares = [(a, b) for a, b in zip(p1, p2) if a["p"].lower().strip(".,!?") == b["p"].lower().strip(".,!?")]
        d = sorted(max(abs(a["ini"] - b["ini"]), abs(a["fim"] - b["fim"])) * 1000 for a, b in pares)
        bons = sum(1 for x in d if x <= 40)
        estado = "IGUAL" if txt1 == txt2 and bons == len(p2) else ("PERTO" if len(pares) >= 0.9 * len(p2) else "DIFERENTE")
        diz("fala", estado, f"{len(p1)} × {len(p2)} palavras · texto {'igual' if txt1 == txt2 else 'diferente'} · {bons} a ≤ 40 ms"
            + (f" · pior {d[-1]:.0f} ms" if d else "") + f" · modelo nova: {f1.get('modelo')}")
    for peca, chave, tol in (("batida", "batidas", 0.010), ("sinal", "ataques", 0.010)):
        a, b = ler(nova, peca), ler(ref, peca)
        if a and b:
            xa = [x if isinstance(x, (int, float)) else x["t"] for x in a.get(chave, [])]
            xb = [x if isinstance(x, (int, float)) else x["t"] for x in b.get(chave, [])]
            n = perto(xa, xb, tol)
            diz(peca, "IGUAL" if n == len(xa) == len(xb) else ("PERTO" if n >= 0.9 * max(len(xb), 1) else "DIFERENTE"),
                f"{len(xa)} × {len(xb)} {chave} · {n} a ≤ {tol * 1000:.0f} ms")
    r1, r2 = ler(nova, "rotulos"), ler(ref, "rotulos")
    if r1 and r2:
        j1, j2 = r1.get("janelas", []), r2.get("janelas", [])
        top = lambda j: j["rotulos"][0][0] if j.get("rotulos") else None   # noqa: E731
        n = sum(1 for a, b in zip(j1, j2) if top(a) == top(b))
        diz("rotulos", "IGUAL" if n == len(j1) == len(j2) else ("PERTO" if n >= 0.9 * max(len(j2), 1) else "DIFERENTE"),
            f"{n} de {len(j2)} janelas com a mesma 1ª etiqueta")
    m1, m2 = ler(nova, "musica"), ler(ref, "musica")
    if m1 and m2:
        diz("musica", "IGUAL" if (m1.get("bpm"), len(m1.get("partes", []))) == (m2.get("bpm"), len(m2.get("partes", []))) else "DIFERENTE",
            f"BPM {m1.get('bpm')} × {m2.get('bpm')} · partes {len(m1.get('partes', []))} × {len(m2.get('partes', []))}")
    print("\n".join(linhas) or "nenhuma peça em comum")
    sys.exit(1 if ruim else 0)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1], sys.argv[2])
