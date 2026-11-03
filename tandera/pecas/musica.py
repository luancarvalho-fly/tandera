# -*- coding: utf-8 -*-
"""MÚSICA: as seções e a curva da música no stem de música — partes (encaixadas no tempo forte, em compassos), subidas, drops, viradas,
respiros, energia e brilho. Medida, sem modelo de emoção (decisão dele). O medidor é o da régua (_medidor_musica.py)."""
from . import _medidor_musica as M


def aquecer(ctx):
    from . import batida
    batida._beat_this(ctx.placa)                     # o mesmo Beat This! da peça «batida» (no lote, se ela acabou de rodar, já está na placa)


def rodar(A, ctx):
    from . import separacao
    from .. import base
    mus = separacao.stem(A, "musica")
    if not mus:
        return {"sem_som": True}
    beats = None
    if base.SEGURAR:                                 # só no lote: fora dele o medidor carrega o modelo como sempre
        from . import batida
        beats = batida._beat_this(ctx.placa)
    r = M.medir(mus, dispositivo="cuda" if ctx.placa else "cpu", beats=beats)
    base.liberar_torch()
    return {k: v for k, v in r.items() if k not in ("arquivo",)}
