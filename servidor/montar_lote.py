# -*- coding: utf-8 -*-
"""MONTA O LOTE no PC (01/11, panelas de som): o LEVANTAMENTO.json (ou um recorte) → <nome>.json com tudo que o servidor precisa pra
devolver a análise com o NOME CERTO: por vídeo, o tamanho, a DATA (mtime), a assinatura que o PC calcula (tandera.armazem) e a pasta
«<nome>_<assinatura>»; os stems do Plexus escolhidos (servidor\\stems.py); e o caminho de cada arquivo no storage.
O servidor confere a assinatura de cada cópia (e acerta a data se o envio a perdeu) antes de analisar.

  python servidor\\montar_lote.py --nome piloto --grupos tutorial --limite 2
  python servidor\\montar_lote.py --nome lote-1                                     (todos os grupos do LEVANTAMENTO.json)
  python servidor\\montar_lote.py --nome prova --video X.mp4 --stem voz=W --stem musica=W [--video Y.mp4]   (vídeos avulsos)
Opções: --grupos a,b · --limite N · --so <trecho do nome> · --pecas a,b (passa por cima da receita) · --todos-exports (Plexus: todas
as versões, não só a principal) · --saida <pasta> (padrão: lotes\\montados desta pasta, ou TANDERA_ESTUDO)
RECEITA por grupo (01/11 à noite): as peças e o idioma de cada vídeo saem do receitas.json do estudo (--receitas; «um motor só... você
sabe quando desligar e ligar um pistão»): o olho (Gemma, a peça mais cara) só no tutorial e no Kakashi. Peça da receita que só existe no
PC (ex.: efeitos) fica fora do lote, com aviso. Vídeo avulso (--video): --receita <nome>. Sem receita pro grupo = as 11 do servidor.
Segura (V011, gabarito do C6) e item sem vídeo (day 1: baixar antes) ficam FORA, com aviso."""
import argparse, json, os, subprocess, sys, time

AQUI = os.path.dirname(os.path.abspath(__file__)); T = os.path.dirname(AQUI)
sys.path.insert(0, T); sys.path.insert(0, AQUI)
from tandera.armazem import assinatura, nome_da_pasta  # noqa: E402
from tandera.manifesto import ORDEM, PECAS  # noqa: E402
import stems as S  # noqa: E402

ESTUDO = os.environ.get("TANDERA_ESTUDO") or os.path.join(T, "lotes")   # pacote da Fly: era a pasta do estudo no PC do Luan
PECAS_SERVIDOR = ["preparo", "cortes", "separacao", "fala", "batida", "musica", "rotulos", "sinal", "texto", "ovis", "olho"]


def receita_do(receitas, grupo, com_stems, nome=None):
    """(nome, {pecas, idioma}) da receita do grupo («2-plexus» vira «2-plexus (com stems)» / «(sem stems)»); None se não há"""
    if not receitas: return None, None
    if nome: return nome, receitas[nome]
    for chave in (f"{grupo} ({'com' if com_stems else 'sem'} stems)", grupo):
        for n, r in receitas.items():
            if chave in r.get("grupos", []): return n, r
    return None, None


def pecas_da_receita(r):
    """as peças da receita que o servidor roda, na ordem do manifesto, e as que ficam pro PC"""
    quer = set(r["pecas"])
    no_servidor = [p for p in ORDEM if p in quer and "servidor" in PECAS[p]["perfis"]]
    return no_servidor, sorted(quer - set(no_servidor))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass


def sonda(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height", "-of", "json", p],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    j = json.loads(r.stdout or "{}")
    v = [s for s in j.get("streams", []) if s.get("codec_type") == "video"]
    return float((j.get("format") or {}).get("duration") or 0), (f"{v[0]['width']}x{v[0]['height']}" if v else None)


def arquivo(pc, rel):
    st = os.stat(pc)
    return {"pc": pc, "rel": rel, "bytes": st.st_size, "mtime": st.st_mtime}


def item(n, grupo, video, dur=None, res=None, stems_pc=None, projeto=None, frente=None, pecas=None, receitas=None, receita=None):
    if dur is None or res is None: dur, res = sonda(video)
    a = assinatura(video); nome = os.path.basename(video)
    iid = f"{grupo.split('-')[0]}-{n:03d}"
    raiz = f"entrada/{iid}"
    it = {"id": iid, "grupo": grupo, "frente": frente, "projeto": projeto, "video_pc": video, **arquivo(video, f"{raiz}/{nome}"),
          "assinatura": a, "pasta": nome_da_pasta(nome, a), "dur": round(dur, 2), "res": res, "pecas": pecas or PECAS_SERVIDOR, "stems": {}}
    w, h = (int(x) for x in res.split("x")) if res else (1920, 1080)
    it["peso"] = round(dur * (w * h / (1920 * 1080)) ** 0.5, 1)          # 4K longo primeiro (o preparo e os cortes leem o vídeo inteiro)
    if stems_pc:
        durs = {nm: sonda(c)[0] for nm, c in stems_pc.items()}
        mt = {c: os.stat(c).st_mtime for c in stems_pc.values()}
        if all(k in ("voz", "musica", "resto", "efeitos", "mix") for k in stems_pc):          # já vieram com o papel (--stem voz=…)
            esc, notas = {k: [c] for k, c in stems_pc.items()}, []
        else:
            esc, notas = S.escolher(stems_pc, dur, durs, mt)
        it["stems"] = {p: [arquivo(c, f"{raiz}/stems/{p}/{os.path.basename(c)}") for c in cs] for p, cs in esc.items()}
        it["notas_stems"] = notas
    nr, r = receita_do(receitas, grupo, bool(it["stems"]), receita)
    if r and not pecas:
        it["pecas"], it["fica_pro_pc"] = pecas_da_receita(r)
        it["receita"] = nr
        if r.get("idioma"): it["idioma"] = r["idioma"]
    return it


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nome", required=True); ap.add_argument("--levantamento", default=os.path.join(ESTUDO, "LEVANTAMENTO.json"))
    ap.add_argument("--grupos", default="", help="a,b (vazio = todos os grupos do levantamento)"); ap.add_argument("--limite", type=int, default=0)
    ap.add_argument("--so", default=""); ap.add_argument("--pecas", default=""); ap.add_argument("--todos-exports", action="store_true")
    ap.add_argument("--video", action="append", default=[]); ap.add_argument("--stem", action="append", default=[])
    ap.add_argument("--grupo-avulso", default="0-avulso"); ap.add_argument("--saida", default=os.path.join(ESTUDO, "montados"))
    ap.add_argument("--receitas", default=os.path.join(AQUI, "receitas.json")); ap.add_argument("--sem-receitas", action="store_true")
    ap.add_argument("--receita", default="", help="vídeos avulsos (--video): a receita deles (tutorial, plexus-stems, trailer…)")
    x = ap.parse_args()
    pecas = [p.strip() for p in x.pecas.split(",") if p.strip()] or None
    receitas = None if x.sem_receitas or not os.path.exists(x.receitas) else json.load(open(x.receitas, encoding="utf-8"))["receitas"]
    itens, fora = [], []
    if x.video:
        st = dict(s.split("=", 1) for s in x.stem)
        for n, v in enumerate(x.video, 1):
            itens.append(item(n, x.grupo_avulso, os.path.abspath(v), stems_pc=({k: os.path.abspath(c) for k, c in st.items()} if st and n == 1 else None),
                              pecas=pecas, receitas=receitas, receita=x.receita or None))
    else:
        grupos = [g.strip() for g in x.grupos.split(",") if g.strip()]
        L = json.load(open(x.levantamento, encoding="utf-8"))
        cont = {}
        for i in L:
            if grupos and i["grupo"] not in grupos: continue
            rot = i.get("projeto") or os.path.basename(i.get("video") or i.get("url") or "")
            if x.so and x.so.lower() not in (rot + (i.get("video") or "")).lower(): continue
            if i.get("segura"): fora.append(f"{rot}: SEGURA (gabarito do C6) — fora"); continue
            if not i.get("video"): fora.append(f"{rot}: sem vídeo no disco ({i.get('nota', '')})"); continue
            if i["grupo"] == "2-plexus" and not i.get("principal") and not x.todos_exports: continue
            if not os.path.exists(i["video"]): fora.append(f"{rot}: o arquivo sumiu ({i['video']})"); continue
            g = i["grupo"]; cont[g] = cont.get(g, 0) + 1
            if x.limite and cont[g] > x.limite: continue
            itens.append(item(cont[g], g, i["video"], i.get("dur") or None, i.get("res"), i.get("stems") or None, i.get("projeto"), i.get("frente"), pecas,
                              receitas))
            print(f"  {itens[-1]['id']}  {rot[:60]}  {itens[-1]['dur'] / 60:.1f} min  {itens[-1]['res']}  stems: "
                  f"{ {p: len(v) for p, v in itens[-1]['stems'].items()} or '—'}  receita: {itens[-1].get('receita') or '—'}", flush=True)
    lote = {"nome": x.nome, "criado": time.strftime("%Y-%m-%d %H:%M:%S"), "pecas_padrao": PECAS_SERVIDOR, "itens": itens, "fora": fora}
    os.makedirs(x.saida, exist_ok=True)
    dst = os.path.join(x.saida, x.nome + ".json")
    json.dump(lote, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    gb = sum(i["bytes"] + sum(a["bytes"] for v in i["stems"].values() for a in v) for i in itens) / 1e9
    h = sum(i["dur"] for i in itens) / 3600
    print(f"\nlote «{x.nome}»: {len(itens)} vídeos · {h:.2f} h · {gb:.1f} GB pra enviar → {dst}")
    for f in fora: print("  fora:", f)
    rec = {}
    for i in itens: rec.setdefault(i.get("receita") or "—", []).append(i)
    for nr, its in rec.items():
        print(f"  receita {nr}: {len(its)} vídeos · {sum(i['dur'] for i in its) / 3600:.2f} h · peças {','.join(its[0]['pecas'])}"
              + (f" · idioma {its[0]['idioma']}" if its[0].get("idioma") else "") + (f" · fica pro PC: {','.join(its[0]['fica_pro_pc'])}" if its[0].get("fica_pro_pc") else ""))
    for i in itens:
        for n in i.get("notas_stems", []): print(f"  {i['id']} stems: {n}")


if __name__ == "__main__":
    main()
