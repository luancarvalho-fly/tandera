# -*- coding: utf-8 -*-
"""FAXINA DO som48k (06/11/2026, ele: «isso aí você pode apagar»): a cópia do áudio do vídeo que o preparo guarda em
analises\\<pasta>\\pecas\\preparo\\som48k.wav. Não é relatório e o Flynder não usa; o motor refaz IGUAL quando uma peça precisar
(preparo.caminho, testado 06/11 no C0044: bit a bit igual). Vai pra QUARENTENA no E: (nada apagado de vez); o resto do preparo
(cópia leve, quadros, miniaturas, fala16k) FICA — o Flynder toca e mostra direto deles.
Fica de fora: análise cujo vídeo não está no PC (sem o vídeo não daria pra refazer).

  python servidor\\faxina_som48k.py            (mostra o que faria)
  python servidor\\faxina_som48k.py --fazer"""
import glob, json, os, shutil, sys, time

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUAR = r"E:\_QUARENTENA\tandera-som48k-" + time.strftime("%Y-%m-%d")


def main():
    fazer = "--fazer" in sys.argv
    vai, fica, tam = [], [], 0
    for f in glob.glob(os.path.join(R, "analises", "*", "pecas", "preparo", "som48k.wav")):
        pasta = os.path.dirname(os.path.dirname(os.path.dirname(f)))
        try: video = json.load(open(os.path.join(pasta, "analise.json"), encoding="utf-8")).get("video") or ""
        except Exception: video = ""
        if video and os.path.exists(video): vai.append(f); tam += os.path.getsize(f)
        else: fica.append((os.path.basename(pasta), video))
    print(f"{len(vai)} som48k vão pra quarentena ({tam / 1e9:.2f} GB) · {len(fica)} ficam (vídeo fora do PC)"
          + ("" if fazer else " · (só contando: --fazer pra fazer)"))
    if not fazer: return
    os.makedirs(QUAR, exist_ok=True)
    for f in vai:
        nome = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(f))))
        shutil.move(f, os.path.join(QUAR, nome + "__som48k.wav"))
    json.dump({"quando": time.strftime("%Y-%m-%d %H:%M:%S"), "n": len(vai), "gb": round(tam / 1e9, 2), "ficaram": fica,
               "como_volta": "nada a fazer: o Tandera refaz o som48k do vídeo sozinho (preparo.caminho)"},
              open(os.path.join(QUAR, "LEIA.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"feito · quarentena: {QUAR}")


if __name__ == "__main__":
    main()
