# -*- coding: utf-8 -*-
"""SINAL (peça): ataques do som sem a voz, picos de movimento (corte da peça «cortes»), voz soando, vãos e eventos candidatos com as
etiquetas do CED — o que a ficha sonora (/sonoplastia etapa 1) lê. As contas estão em tandera\\sinal.py."""
from .. import sinal as S


def rodar(A, ctx):
    from . import separacao
    c, p = A["cortes"], A["preparo"]
    dur = p["duracao"]
    resto, voz = separacao.stem(A, "resto"), separacao.stem(A, "voz")
    ats, env = S.ataques(resto) if resto else ([], [])
    from . import preparo
    g = preparo.raw(A, "m170", 96, 170) if p["tem_imagem"] else None          # SERVIDOR: da mesma leitura do preparo (PC: None, lê o vídeo)
    mov = S.movimento(A.video, c["cortes_s"], g, p.get("fps") or 30) if p["tem_imagem"] else {"picos": [], "curva": [], "cortes": [], "fps": 0, "dur": dur}
    ativa = S.fala_ativa(voz, dur) if voz else []
    falas = [{"ini": s["ini"], "fim": s["fim"], "txt": s["txt"]} for s in (A.get("fala") or {}).get("segmentos", [])]
    return {"dur": dur, "fps": c.get("fps"), "ataques": ats, "envelope": env, "movimento_picos": mov["picos"], "curva_movimento": mov["curva"],
            "fala_ativa": ativa, "vaos": S.vaos(ativa or falas, dur), "eventos": S.candidatos(ats, mov, A.get("rotulos"))}
