# -*- coding: utf-8 -*-
"""FAXINA DO SOM DO BRUTO (06/11/2026, ele: «a gente não precisa de voz separada nisso. A gente não precisa disso»).
No bruto a «separação» é o PRÓPRIO som do vídeo (pistas.stems_da): um wav por vídeo em trabalho\\som-proprio\\<pasta>\\mix48k.wav, ligado
(hardlink) como voz/resto/música em analises\\<pasta>\\pecas\\separacao\\entregue-*\\. Nada disso é relatório: o motor refaz IGUAL quando
uma peça precisar (separacao.stem → _refazer_som_proprio, testado 06/11 no C0044: bit a bit igual, mesma assinatura).
Esta faxina: o wav de cada vídeo vai pra QUARENTENA no E: (nada apagado de vez) e os atalhos dentro da análise saem. O .json da
separação fica (a análise continua «feita»). Separação de verdade (modelo ou stems da edição: Plexus, editados) NÃO é tocada.

  python servidor\\faxina_som_bruto.py            (mostra o que faria)
  python servidor\\faxina_som_bruto.py --fazer    (faz)"""
import glob, json, os, shutil, sys, time

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUAR = r"E:\_QUARENTENA\tandera-som-do-bruto-" + time.strftime("%Y-%m-%d")


def eh_som_proprio(ent):
    return bool(ent) and all("som-proprio" in str(v).replace(os.sep, "/").replace("\\", "/") for v in ent.values())


def main():
    fazer = "--fazer" in sys.argv
    pastas, inos, tam = [], set(), 0
    for aj in glob.glob(os.path.join(R, "analises", "*", "pecas", "separacao.json")):
        ent = (json.load(open(aj, encoding="utf-8")) or {}).get("entregue") or {}
        if not eh_som_proprio(ent): continue
        pasta = os.path.dirname(os.path.dirname(aj)); nome = os.path.basename(pasta)
        sp = os.path.join(R, "trabalho", "som-proprio", nome)
        links = glob.glob(os.path.join(pasta, "pecas", "separacao", "entregue-*"))
        arqs = [f for d in links for f in glob.glob(os.path.join(d, "*.wav"))] + glob.glob(os.path.join(sp, "*.wav"))
        for f in arqs:
            st = os.stat(f)
            if (st.st_dev, st.st_ino) not in inos: inos.add((st.st_dev, st.st_ino)); tam += st.st_size
        pastas.append((nome, sp, links))
    print(f"{len(pastas)} análises do bruto com o som próprio · {tam / 1e9:.2f} GB de verdade no disco C" + ("" if fazer else " · (só contando: --fazer pra fazer)"))
    if not fazer: return
    os.makedirs(QUAR, exist_ok=True)
    feito = []
    for nome, sp, links in pastas:
        if os.path.isdir(sp):
            shutil.move(sp, os.path.join(QUAR, nome))          # a cópia do som (o mesmo dado dos atalhos) vai inteira pra quarentena
        for d in links:
            shutil.rmtree(d)                                    # só atalhos (hardlinks) do mesmo som: o dado está na quarentena
        feito.append(nome)
    json.dump({"quando": time.strftime("%Y-%m-%d %H:%M:%S"), "pastas": feito, "gb": round(tam / 1e9, 2),
               "como_volta": "nada a fazer: o Tandera refaz o som do vídeo sozinho quando uma peça precisar (separacao.stem)"},
              open(os.path.join(QUAR, "LEIA.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"feito: {len(feito)} · quarentena: {QUAR}")


if __name__ == "__main__":
    main()
