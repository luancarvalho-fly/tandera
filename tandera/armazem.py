# -*- coding: utf-8 -*-
"""A ANÁLISE GUARDADA de um vídeo: uma pasta por vídeo (nome + assinatura do arquivo) com
  analise.json      o índice: pra cada peça, a VERSÃO que a fez, o modelo, com que versões das peças de entrada ela foi feita,
                    quando, em que perfil (pc/servidor), quanto tempo e quanta placa gastou; e a lista das rodadas
  pecas\\<peca>.json o resultado de cada peça (o que é grande — retratos, quadros, stems — fica em pecas\\<peca>\\)
Incremental (a lei dele, 01/11): «saiu o CLAP 5 e é só isso que mudou... tu vai rodar só o CLAP 5 e vai somar na análise que já
foi feita». Uma peça roda de novo SÓ se: falta; a versão dela no manifesto mudou; ou uma peça de que ela depende foi refeita com
outra versão (a entrada mudou, então a saída antiga não vale). O resto vem guardado."""
import hashlib, json, os, re, time

from . import base
from .manifesto import PECAS


def assinatura(p):
    """tamanho + data + 1 MB do começo e do fim (igual ao cache da Régua): o mesmo arquivo copiado pra outro lugar acha a análise"""
    st = os.stat(p); h = hashlib.sha1(f"{st.st_size}|{int(st.st_mtime)}".encode())
    with open(p, "rb") as f:
        h.update(f.read(1 << 20)); f.seek(max(0, st.st_size - (1 << 20))); h.update(f.read(1 << 20))
    return h.hexdigest()[:12]


def pasta_do_video(video):
    """a análise é achada pela ASSINATURA, não pelo nome: o mesmo vídeo copiado ou ligado com outro nome (ex.: o original.mp4 da
    /sonoplastia) acha a análise que já existe (01/11: a ficha refez tudo porque o nome era outro)"""
    a = assinatura(video)
    if os.path.isdir(base.ANALISES):
        ja = sorted((d for d in os.listdir(base.ANALISES) if d.endswith("_" + a) and os.path.exists(os.path.join(base.ANALISES, d, "analise.json"))),
                    key=lambda d: -len(json.load(open(os.path.join(base.ANALISES, d, "analise.json"), encoding="utf-8")).get("pecas", {})))
        if ja: return os.path.join(base.ANALISES, ja[0])
    return os.path.join(base.ANALISES, nome_da_pasta(os.path.basename(video), a))


def nome_da_pasta(nome_arquivo, assin):
    """o nome da pasta da análise: <nome do arquivo (40 letras)>_<assinatura>. O servidor usa o MESMO nome que o PC daria (01/11, panelas):
    o lote leva o nome calculado no PC, então a pasta volta igual mesmo se o arquivo chegar lá com outro nome"""
    return re.sub(r"[^A-Za-z0-9_-]", "_", os.path.splitext(nome_arquivo)[0])[:40] + "_" + assin


class Analise:
    def __init__(self, video, pasta=None):
        self.video = os.path.abspath(video)
        self.pasta = os.path.abspath(pasta) if pasta else pasta_do_video(self.video)
        self.arq = os.path.join(self.pasta, "analise.json")
        os.makedirs(os.path.join(self.pasta, "pecas"), exist_ok=True)
        if os.path.exists(self.arq):
            self.d = json.load(open(self.arq, encoding="utf-8"))
        else:
            self.d = {"video": self.video, "assinatura": assinatura(self.video), "criada": time.strftime("%Y-%m-%d %H:%M:%S"),
                      "pecas": {}, "rodadas": []}
        self._cache = {}
        self.esperada = {}   # peça → (versão, modelo) no lugar do manifesto: a separação ENTREGUE (voz/música prontas, 01/11)

    def alvo(self, peca):
        """(versão, modelo) que a peça tem que ter: a do manifesto, ou a da entrada que veio pronta"""
        return self.esperada.get(peca) or (PECAS[peca]["versao"], PECAS[peca]["modelo"])

    # ---------------------------------------------------------------- leitura
    def dir(self, peca):
        """pasta dos arquivos grandes da peça"""
        p = os.path.join(self.pasta, "pecas", peca); os.makedirs(p, exist_ok=True); return p

    def tem(self, peca):
        return peca in self.d["pecas"] and os.path.exists(os.path.join(self.pasta, "pecas", peca + ".json"))

    def __getitem__(self, peca):
        """o resultado guardado da peça (dict)"""
        if peca not in self._cache:
            if not self.tem(peca): raise KeyError(f"a peça «{peca}» ainda não foi feita neste vídeo ({self.pasta})")
            self._cache[peca] = json.load(open(os.path.join(self.pasta, "pecas", peca + ".json"), encoding="utf-8"))
        return self._cache[peca]

    def get(self, peca, padrao=None):
        try: return self[peca]
        except KeyError: return padrao

    def versao(self, peca):
        return (self.d["pecas"].get(peca) or {}).get("versao")

    def precisa(self, peca, refeitas=()):
        """(precisa rodar?, por quê)"""
        if not self.tem(peca): return True, "falta"
        g = self.d["pecas"][peca]
        if str(g.get("versao") or "").startswith("entregue-") and peca not in self.esperada:
            # 03/11 (ele: «é só não ter retrabalho»): a separação que veio PRONTA (os stems da mixagem / o próprio som) vale até alguém pedir
            # --refazer; sem isto, rodar o vídeo sem passar os stems de novo refazia a separação no modelo e tudo que depende dela
            return False, "guardada (entregue pronta)"
        if g.get("versao") != self.alvo(peca)[0]:
            return True, f"versão nova ({g.get('versao')} → {self.alvo(peca)[0]})"
        for dep in PECAS[peca]["depende"]:
            if dep in refeitas or (g.get("feito_com") or {}).get(dep) != self.versao(dep):
                return True, f"a entrada «{dep}» mudou"
        return False, "guardada"

    # ---------------------------------------------------------------- escrita
    def guardar(self, peca, resultado, medida, perfil):
        base.salvar_json(os.path.join(self.pasta, "pecas", peca + ".json"), resultado)
        self._cache[peca] = resultado
        self.d["pecas"][peca] = {"versao": self.alvo(peca)[0], "modelo": self.alvo(peca)[1], "onde": PECAS[peca]["onde"],
                                 "feito_com": {d: self.versao(d) for d in PECAS[peca]["depende"]}, "perfil": perfil,
                                 "quando": time.strftime("%Y-%m-%d %H:%M:%S"), "medida": medida}
        self.gravar()

    def gravar(self):
        base.salvar_json(self.arq, self.d)

    def resumo(self):
        """o índice legível: peça · versão · quando · perfil · tempo"""
        return {p: {k: v for k, v in g.items() if k in ("versao", "modelo", "perfil", "quando", "medida")} for p, g in self.d["pecas"].items()}
