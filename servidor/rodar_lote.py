# -*- coding: utf-8 -*-
"""A FILA DO LOTE no servidor (01/11, panelas de som; LOTE POR PEÇA em 01/11 à noite). Lê o lote (montar_lote.py no PC) e roda o TANDERA:
  - várias máquinas dividem a MESMA fila no storage ($W/fila/<lote>/: cada vídeo pego vira um arquivinho com o nome da máquina —
    o mesmo jeito do --fila do Flynder); quem acaba a sua parte pega o que sobrou;
  - pesados primeiro (4K longo; --primeiro leves numa 2ª máquina, como o Flynder fazia);
  - cada vídeo: copia do storage pro disco da máquina, ACERTA A DATA pela do lote e confere a assinatura do PC (a análise tem que voltar
    com o nome que o PC procura), soma os stems do Plexus (servidor/stems.py), roda as peças da RECEITA do grupo (o lote leva) e guarda
    a pasta da análise no storage ($W/analises/<pasta>);
  - PADRÃO = em BLOCOS (--bloco 12): a máquina pega um bloco da fila; o processador recebe e faz o PREPARO do próximo bloco enquanto a
    placa passa o atual PEÇA POR PEÇA (tandera/lote.py num processo próprio por bloco: cada modelo carrega UMA vez pro bloco inteiro,
    solta, e vai pra próxima peça; o sinal roda ao lado no processador). Mesmo resultado, guardado do mesmo jeito (assinatura, incremental);
  - --bloco 0 = o jeito de antes: `tandera analisar` num processo por vídeo (cada peça carrega o modelo em cada vídeo);
  - fila vazia = DESLIGA a máquina (runpodctl stop pod), se --desligar.
Uso (depois de source /root/ativar_tandera.sh):
  python /root/TANDERA/servidor/rodar_lote.py --lote $TANDERA_STORAGE/lotes/<nome>.json --desligar [--primeiro leves] [--pecas a,b] [--so ID,ID]
                                             [--bloco N] [--preparo-juntos N]
  python /root/TANDERA/servidor/rodar_lote.py --lote ... --estado          (o andamento da fila, de qualquer máquina)
  --soltar: devolve pra fila o que ficou preso numa máquina que morreu (sem .feito) · --refazer-falhos: tenta de novo os que falharam
  (continua da análise guardada no storage: só roda o que falta) · --refazer a,b: roda essas peças de novo mesmo guardadas."""
import argparse, json, os, shutil, socket, subprocess, sys, time

AQUI = os.path.dirname(os.path.abspath(__file__)); T = os.path.dirname(AQUI)
sys.path.insert(0, T); sys.path.insert(0, AQUI)
from tandera.armazem import assinatura  # noqa: E402
import stems as S  # noqa: E402

W = os.environ.get("TANDERA_STORAGE", "/workspace/tandera")
ANALISES = os.environ.get("TANDERA_ANALISES", "/root/analises")
TRABALHO = os.environ.get("TANDERA_TRABALHO", "/root/trabalho")
# 07/11: sem esta variável no ambiente o preparo NÃO tira os quadros pequenos dos cortes/sinal da mesma leitura do 4K (preparo._raw) e
# os cortes abriam o 4K original de novo pelo processador (~4–5 min por vídeo, placa a 2–15 %)
os.environ["TANDERA_TRABALHO"] = TRABALHO
PY = os.environ.get("TANDERA_PY", sys.executable)
MAQ = os.environ.get("RUNPOD_POD_ID") or socket.gethostname()
try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except AttributeError:
    pass


def log(*a):
    msg = time.strftime("[%H:%M:%S] ") + " ".join(str(x) for x in a)
    print(msg, flush=True)
    try:
        os.makedirs(os.path.join(W, "logs"), exist_ok=True)
        open(os.path.join(W, "logs", f"{MAQ}.log"), "a", encoding="utf-8").write(msg + "\n")
    except OSError:
        pass


class Fila:
    """um arquivinho por vídeo no storage: <id> = pego (conteúdo: a máquina) · <id>.feito · <id>.falhou (o motivo)"""
    def __init__(self, nome):
        self.d = os.path.join(W, "fila", nome); os.makedirs(self.d, exist_ok=True)

    def p(self, iid, ext=""): return os.path.join(self.d, iid + ext)

    def pegar(self, iid):
        if os.path.exists(self.p(iid, ".feito")) or os.path.exists(self.p(iid, ".falhou")): return False
        try:
            fd = os.open(self.p(iid), os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.write(fd, MAQ.encode()); os.close(fd); return True
        except FileExistsError:
            try: return open(self.p(iid)).read().strip() == MAQ          # pego por ESTA máquina numa rodada que caiu: continua
            except OSError: return False

    def marcar(self, iid, ext, texto=""):
        open(self.p(iid, ext), "w", encoding="utf-8").write(texto or MAQ)

    def estado(self, iid):
        if os.path.exists(self.p(iid, ".feito")): return "feito"
        if os.path.exists(self.p(iid, ".falhou")): return "falhou"
        if os.path.exists(self.p(iid)): return "rodando:" + open(self.p(iid)).read().strip()
        return "na fila"


def copia_local(a, dst):
    """storage → disco da máquina; a DATA volta a ser a do PC (a do lote) — é ela que entra na assinatura"""
    src = os.path.join(W, a["rel"])
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if not (os.path.exists(dst) and os.path.getsize(dst) == a["bytes"]):
        shutil.copyfile(src, dst + ".parcial"); os.replace(dst + ".parcial", dst)
    if int(os.stat(dst).st_mtime) != int(a["mtime"]):
        os.utime(dst, (a["mtime"], a["mtime"]))
    return dst


def ollama_no_ar():
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:11434/api/version", timeout=2).read(); return True
    except Exception:
        return False


def garante_ollama():
    if ollama_no_ar(): return
    log("subindo o Ollama (o olho)")
    subprocess.Popen(["ollama", "serve"], stdout=open("/root/ollama.log", "a"), stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(40):
        time.sleep(1)
        if ollama_no_ar(): return
    log("AVISO: o Ollama não subiu — o olho vai falhar")


def receber(it, fila):
    """storage → disco da máquina: o vídeo (data do lote, assinatura conferida), os stems somados, a análise que já estava no storage
    (incremental) e o servidor.json → (vídeo local, stems, pasta da análise, pasta de trabalho)"""
    iid = it["id"]
    tr = os.path.join(TRABALHO, iid); os.makedirs(tr, exist_ok=True)
    if it.get("sem_video"):
        # 06/11 (baterias): as peças pedidas não leem o vídeo (diário/busca: leem a análise que o PC mandou) — o vídeo não subiu
        v = os.path.join(tr, os.path.basename(it["rel"]))
        if not os.path.exists(os.path.join(W, "analises", it["pasta"], "analise.json")):
            raise RuntimeError("sem vídeo e sem a análise do PC no storage: não tem de onde partir")
    else:
        v = copia_local(it, os.path.join(tr, os.path.basename(it["rel"])))
        a = assinatura(v)
        if a != it["assinatura"]:
            raise RuntimeError(f"o vídeo chegou DIFERENTE do PC (assinatura {a} × {it['assinatura']}): não analiso (a análise não seria achada)")
    stems = {}
    if it.get("stems"):
        locais = {p: [copia_local(x, os.path.join(tr, "stems", p, os.path.basename(x["rel"]))) for x in arqs] for p, arqs in it["stems"].items()}
        mt = {os.path.join(tr, "stems", p, os.path.basename(x["rel"])): x["mtime"] for p, arqs in it["stems"].items() for x in arqs}
        stems = S.stems_prontos(locais, os.path.join(tr, "stems", "_juntos"), mt)
        log(f"{iid}: stems prontos ({', '.join(f'{p}={len(locais[p])}' for p in sorted(locais))})")
    # 07/11 (ele, depois do lote de 842: «nenhum desses vídeos precisam de separação de voz, música e efeitos... é literalmente inútil e
    # vai ocupar um espaço do crl»): no BRUTO a «separação» é o PRÓPRIO som do vídeo (pistas.stems_da, a mesma regra das filas do PC
    # desde 06/11) — custo zero, a fala transcreve o som inteiro. O caminho do RunPod não chamava a regra: o lote rodou BS-Roformer +
    # BandIt em tudo (114 GB de wav, disco cheio, falhas). Vídeo sem som: sem stems e sem as peças de som (fala, som).
    # 12/11 (ele: «separação de áudio nesses casos é coisa inútil... diria q só o plexus, e mesmo assim só quando eu for editar»): vale pra
    # QUALQUER pista — sem a «separacao» entre as peças pedidas, o próprio som vale como separação (pistas.stems_da com as peças).
    it["_caem"] = []
    if not stems and it.get("pista") not in (None, "kakashi") and not it.get("sem_video"):
        from tandera.pistas import stems_da
        st, caem = stems_da(it["pista"], v, log, it.get("pecas") or [])
        if st: stems = st
        it["_caem"] = caem
    pasta = os.path.join(ANALISES, it["pasta"])
    guardada = os.path.join(W, "analises", it["pasta"])
    if not os.path.exists(os.path.join(pasta, "analise.json")) and os.path.exists(os.path.join(guardada, "analise.json")):
        # já analisado antes (outra máquina, ou uma rodada que falhou numa peça): começa do que está no storage — o Tandera só roda o que falta
        log(f"{iid}: a análise já está no storage: continua dela (incremental)")
        # 07/11: o storage do RunPod é geesefs — «rsync -a» dá erro 11 (memória, 01/11: «rsync -a não grava»); cópia simples, sem permissões
        os.makedirs(pasta, exist_ok=True); subprocess.run(["cp", "-r", guardada + "/.", pasta + "/"], check=True)
    os.makedirs(pasta, exist_ok=True)
    json.dump({"video_pc": it["video_pc"], "id": iid, "lote": fila.d, "maquina": MAQ, "grupo": it["grupo"], "assinatura": it["assinatura"],
               "stems_pc": {p: [x["pc"] for x in arqs] for p, arqs in it.get("stems", {}).items()}},
              open(os.path.join(pasta, "servidor.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return v, stems, pasta, tr


def um_video(it, pecas, fila, refazer=()):
    """o jeito VÍDEO POR VÍDEO (--bloco 0; o de antes de 01/11 à noite): um `tandera analisar` por vídeo, cada peça carrega o seu modelo"""
    t0 = time.monotonic(); iid = it["id"]
    v, stems, pasta, tr = receber(it, fila)
    pecas = [p for p in pecas if p not in it.get("_caem", [])]
    cmd = [PY, "-m", "tandera", "analisar", v, "--pecas", ",".join(pecas), "--pasta", pasta, "--perfil", "servidor"]
    for p, c in stems.items(): cmd += ["--stem", f"{p}={c}"]
    if refazer: cmd += ["--refazer", ",".join(refazer)]
    if it.get("idioma"): cmd += ["--idioma", it["idioma"]]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONPATH=T)
    limite = 1800 + 12 * it["dur"]
    log(f"{iid}: ▶ {os.path.basename(v)} ({it['dur'] / 60:.1f} min, {it['res']}) · {','.join(pecas)}")
    with open(os.path.join(tr, "tandera.log"), "w", encoding="utf-8") as out:
        try:
            r = subprocess.run(cmd, cwd=T, env=env, stdout=out, stderr=subprocess.STDOUT, timeout=limite)
            cod = r.returncode
        except subprocess.TimeoutExpired:
            cod = "tempo esgotado"
    return entregar(it, pasta, os.path.join(tr, "tandera.log"), cod, t0)


def entregar(it, pasta, arq_log, cod, t0, resultado=None):
    """o fim de cada vídeo (nos dois jeitos): o log junto da análise, o que rodou/falhou (vídeo por vídeo: a última rodada do
    analise.json; no bloco: o resultado do bloco), e a pasta guardada no storage"""
    if arq_log and os.path.exists(arq_log) and os.path.isdir(pasta):
        shutil.copy(arq_log, os.path.join(pasta, "tandera-servidor.log"))
    if resultado is not None:
        tempos, falhou = dict(resultado.get("rodou") or {}), dict(resultado.get("falhou") or {})
    else:
        d = json.load(open(os.path.join(pasta, "analise.json"), encoding="utf-8")) if os.path.exists(os.path.join(pasta, "analise.json")) else {}
        ult = (d.get("rodadas") or [{}])[-1]
        tempos = {p: x.get("s") for p, x in (ult.get("rodou") or {}).items()}
        falhou = dict(ult.get("falhou") or {})
    if cod != 0: falhou["_processo"] = f"código {cod}"
    # guarda no storage (é de lá que o PC busca; o disco da máquina some quando ela desliga)
    dst = os.path.join(W, "analises", it["pasta"])
    os.makedirs(dst, exist_ok=True)
    subprocess.run(["cp", "-r", pasta + "/.", dst + "/"], check=True)   # 07/11: sem rsync -a (geesefs)
    return {"s": round(time.monotonic() - t0, 1), "pecas_s": tempos, "falhou": falhou, "pasta": it["pasta"], "maquina": MAQ}


def preparar_bloco(bloco, fila, pecas_de, refazer, juntos=3):
    """o PROCESSADOR de um bloco (roda enquanto a placa trabalha no bloco anterior): cada vídeo recebido do storage e com o preparo feito
    (abre o vídeo uma vez: quadros, cópia 480p, som) — `juntos` vídeos ao mesmo tempo → [(it, item do lote ou None, erro ou None, t0)]"""
    from concurrent.futures import ThreadPoolExecutor
    from tandera import lote as LT

    def um(it):
        t0 = time.monotonic()
        try:
            v, stems, pasta, _ = receber(it, fila)
            item = {"id": it["id"], "video": v, "pasta": pasta, "pecas": [p for p in pecas_de(it) if p not in it.get("_caem", [])],
                    "stems": stems or None, "idioma": it.get("idioma"),
                    "refazer": refazer}
            item["previa"] = LT.preparar(item, "servidor", True, log=log)
            log(f"{it['id']}: preparo pronto em {time.monotonic() - t0:.0f} s ({it['dur'] / 60:.1f} min de vídeo, {it['res']})")
            return it, item, None, t0
        except BaseException as e:                     # (SystemExit dos stems também: só este vídeo)
            return it, None, e, t0
    with ThreadPoolExecutor(max(1, juntos)) as pool:
        return list(pool.map(um, bloco))


def placa_do_bloco(prontos, n):
    """a PLACA de um bloco: `python -m tandera.lote` num processo próprio (um bloco que derruba a placa não leva a fila junto) — cada
    peça carrega o modelo uma vez e passa o bloco inteiro → (resultado do bloco, código, log)"""
    d = os.path.join(TRABALHO, "_blocos"); os.makedirs(d, exist_ok=True)
    bj, rj, lg = (os.path.join(d, f"bloco-{n:03d}{x}") for x in (".json", ".resultado.json", ".log"))
    itens = [item for _, item, e, _ in prontos if item]
    json.dump({"itens": itens, "placa": True, "perfil": "servidor", "trabalho": TRABALHO}, open(bj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if os.path.exists(rj): os.remove(rj)
    limite = 1800 + 12 * sum(it["dur"] for it, item, _, _ in prontos if item)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONPATH=T)
    log(f"bloco {n}: ▶ placa · {len(itens)} vídeos · {sum(it['dur'] for it, item, _, _ in prontos if item) / 60:.1f} min de vídeo")
    with open(lg, "w", encoding="utf-8") as out:
        try:
            cod = subprocess.run([PY, "-m", "tandera.lote", bj, rj], cwd=T, env=env, stdout=out, stderr=subprocess.STDOUT, timeout=limite).returncode
        except subprocess.TimeoutExpired:
            cod = "tempo esgotado"
    res = json.load(open(rj, encoding="utf-8")) if os.path.exists(rj) else {}
    if res.get("pecas"):
        log(f"bloco {n}: placa pronta em {res['s'] / 60:.1f} min · " + " · ".join(
            f"{p} {x.get('s', 0):.0f}s" + (f" (carregar {x['carregar_s']:.0f}s)" if x.get("carregar_s") else "") for p, x in res["pecas"].items()))
    return res, cod, lg


def em_blocos(itens, x, fila, L, pecas_cli, refazer):
    """o jeito LOTE (01/11 à noite): pega um BLOCO de vídeos da fila; o processador recebe e prepara o PRÓXIMO bloco enquanto a placa
    passa o atual peça por peça (cada modelo carregado uma vez por bloco). → quantos vídeos terminaram"""
    from concurrent.futures import ThreadPoolExecutor
    resto = iter(itens)

    def proximo():
        b = []
        for it in resto:
            if fila.pegar(it["id"]):
                b.append(it)
                if len(b) >= x.bloco: break
        return b

    pecas_de = lambda it: pecas_cli or it.get("pecas") or L["pecas_padrao"]          # noqa: E731
    feitos, n = 0, 0
    with ThreadPoolExecutor(1) as prep:
        b = proximo()
        fut = prep.submit(preparar_bloco, b, fila, pecas_de, refazer, x.preparo_juntos) if b else None
        while fut:
            prontos = fut.result(); n += 1
            b = proximo()                                # o próximo bloco já vai sendo preparado enquanto a placa trabalha neste
            fut = prep.submit(preparar_bloco, b, fila, pecas_de, refazer, x.preparo_juntos) if b else None
            for it, item, e, _ in prontos:
                if e is not None:
                    fila.marcar(it["id"], ".falhou", f"{type(e).__name__}: {str(e)[:500]}")
                    log(f"{it['id']}: ✗ (preparo) {type(e).__name__}: {str(e)[:300]}")
            if any("olho" in pecas_de(it) for it, item, _, _ in prontos if item): garante_ollama()
            res, cod, lg = placa_do_bloco(prontos, n)
            for it, item, e, t0 in prontos:
                if item is None: continue
                try:
                    rv = (res.get("videos") or {}).get(it["id"])
                    if rv is None: rv = {"falhou": {"_bloco": (res.get("ruins") or {}).get(it["id"]) or f"o bloco não terminou este vídeo (código {cod})"}}
                    rv["rodou"] = {**{p: m.get("s") for p, m in (item["previa"].get("rodou") or {}).items()}, **(rv.get("rodou") or {})}
                    r = entregar(it, item["pasta"], lg, cod, t0, rv)
                    r["bloco"] = n
                    fila.marcar(it["id"], ".falhou" if r["falhou"] else ".feito", json.dumps(r, ensure_ascii=False))
                    log(f"{it['id']}: ✓ bloco {n}" + (f" · FALHOU: {r['falhou']}" if r["falhou"] else "") + " · " +
                        " ".join(f"{p} {s:.0f}s" for p, s in r["pecas_s"].items() if s is not None))
                    feitos += 1
                    if not x.manter_local:
                        shutil.rmtree(os.path.join(TRABALHO, it["id"]), ignore_errors=True)
                        shutil.rmtree(os.path.join(ANALISES, it["pasta"]), ignore_errors=True)
                except Exception as e:
                    fila.marcar(it["id"], ".falhou", f"{type(e).__name__}: {str(e)[:500]}")
                    log(f"{it['id']}: ✗ {type(e).__name__}: {str(e)[:300]}")
    return feitos


def estado(L, fila):
    cont = {}
    print(f"lote «{L['nome']}» · {len(L['itens'])} vídeos")
    for it in L["itens"]:
        e = fila.estado(it["id"]); cont[e.split(":")[0]] = cont.get(e.split(":")[0], 0) + 1
        extra = ""
        if e == "feito":
            try: extra = f"{json.load(open(fila.p(it['id'], '.feito'), encoding='utf-8'))['s'] / 60:.1f} min"
            except Exception: pass
        if e == "falhou": extra = open(fila.p(it["id"], ".falhou"), encoding="utf-8").read()[:160]
        print(f"  {it['id']:<7} {e:<28} {it['dur'] / 60:5.1f} min  {os.path.basename(it['rel'])[:50]}  {extra}")
    print("  " + " · ".join(f"{k}: {v}" for k, v in sorted(cont.items())))


def desligar():
    pid = os.environ.get("RUNPOD_POD_ID")
    if not pid:
        try: pid = next(l.split("=", 1)[1] for l in open("/proc/1/environ").read().split("\0") if l.startswith("RUNPOD_POD_ID="))
        except Exception: pid = None
    if pid and shutil.which("runpodctl"):
        log(f"fila acabou: desligando a máquina {pid}")
        subprocess.run(["runpodctl", "stop", "pod", pid])
    else:
        log("fila acabou (sem runpodctl/RUNPOD_POD_ID aqui: não é uma máquina do RunPod — nada a desligar)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lote", required=True); ap.add_argument("--pecas", default=""); ap.add_argument("--so", default="")
    ap.add_argument("--primeiro", choices=["pesados", "leves"], default="pesados"); ap.add_argument("--desligar", action="store_true")
    ap.add_argument("--estado", action="store_true"); ap.add_argument("--soltar", action="store_true"); ap.add_argument("--refazer-falhos", action="store_true")
    ap.add_argument("--refazer", default="", help="peças pra rodar de novo mesmo guardadas (a,b)")
    ap.add_argument("--manter-local", action="store_true", help="não apaga o vídeo e a análise do disco da máquina depois de guardar")
    ap.add_argument("--bloco", type=int, default=12, help="vídeos por bloco (cada modelo carrega uma vez por bloco); 0 = vídeo por vídeo (o jeito antigo)")
    ap.add_argument("--preparo-juntos", type=int, default=3, help="vídeos sendo preparados ao mesmo tempo (processador)")
    x = ap.parse_args()
    L = json.load(open(x.lote, encoding="utf-8"))
    fila = Fila(L["nome"])
    if x.estado: estado(L, fila); return
    # 07/11: a fila pode ser aberta cedo à mão (enquanto o PC ainda manda as análises) e depois o runpod.py abre de novo na mesma
    # máquina: duas filas com o MESMO nome de máquina pegariam o mesmo vídeo. A segunda vê a primeira viva e sai sem fazer nada
    # (o runpod.py segue vendo «rodar_lote.py» vivo e acompanha normal)
    meu = os.getpid()
    for l in subprocess.run(["pgrep", "-af", "rodar_lote.py"], capture_output=True, text=True).stdout.splitlines():
        pid, _, linha = l.partition(" ")
        if pid.isdigit() and int(pid) != meu and "--lote" in linha and os.path.basename(x.lote) in linha and "--estado" not in linha \
                and not linha.startswith(("bash", "sh ")):
            print(f"já tem uma fila deste lote rodando nesta máquina (pid {pid}): esta sai", flush=True); return
    if x.soltar or x.refazer_falhos:
        for it in L["itens"]:
            e = fila.estado(it["id"])
            if (x.soltar and e.startswith("rodando")) or (x.refazer_falhos and e == "falhou"):
                for ext in ("", ".falhou"):
                    try: os.remove(fila.p(it["id"], ext))
                    except OSError: pass
                log(f"{it['id']}: de volta pra fila ({e})")
        return
    so = {s.strip() for s in x.so.split(",") if s.strip()}
    itens = [it for it in L["itens"] if not so or it["id"] in so]
    itens.sort(key=lambda it: it["peso"], reverse=(x.primeiro == "pesados"))
    pecas_cli = [p.strip() for p in x.pecas.split(",") if p.strip()]
    refazer = [p.strip() for p in x.refazer.split(",") if p.strip()]
    log(f"máquina {MAQ} · lote «{L['nome']}» · {len(itens)} vídeos · {x.primeiro} primeiro · " +
        (f"BLOCOS de {x.bloco} (peça por peça)" if x.bloco > 0 else "vídeo por vídeo") + f" · análises em {ANALISES} → {W}/analises")
    feitos = 0; T0 = time.monotonic()
    if x.bloco > 0:
        feitos = em_blocos(itens, x, fila, L, pecas_cli, refazer)
        itens = []
    for it in itens:
        if not fila.pegar(it["id"]): continue
        pecas = pecas_cli or it.get("pecas") or L["pecas_padrao"]
        if "olho" in pecas: garante_ollama()
        try:
            r = um_video(it, pecas, fila, refazer)
            fila.marcar(it["id"], ".falhou" if r["falhou"] else ".feito", json.dumps(r, ensure_ascii=False))
            log(f"{it['id']}: ✓ em {r['s'] / 60:.1f} min" + (f" · FALHOU: {r['falhou']}" if r["falhou"] else "") +
                " · " + " ".join(f"{p} {s:.0f}s" for p, s in r["pecas_s"].items() if s is not None))
            feitos += 1
            if not x.manter_local:
                shutil.rmtree(os.path.join(TRABALHO, it["id"]), ignore_errors=True)
                shutil.rmtree(os.path.join(ANALISES, it["pasta"]), ignore_errors=True)
        except Exception as e:
            fila.marcar(it["id"], ".falhou", f"{type(e).__name__}: {str(e)[:500]}")
            log(f"{it['id']}: ✗ {type(e).__name__}: {str(e)[:300]}")
    log(f"esta máquina terminou {feitos} vídeos em {(time.monotonic() - T0) / 60:.1f} min; nada mais na fila pra ela")
    if x.desligar: desligar()


if __name__ == "__main__":
    main()
