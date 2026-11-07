# -*- coding: utf-8 -*-
"""TRAZ as análises do servidor pro PC (01/11, panelas de som) e SOMA no que o PC já tem — sem estragar nada.
O PC acha a análise pela ASSINATURA do vídeo (tandera\\armazem.py): a pasta do servidor tem o mesmo «<nome>_<assinatura>» que o PC dá
(o lote leva a assinatura do PC e o servidor confere), então ela cai no lugar certo e o `tandera.analisar` do PC lê como «guardada».
Regras da soma (pasta que já existe no PC):
  - peça que o PC NÃO tem → vem do servidor (o .json, a pasta grande da peça e a linha no índice);
  - peça que os dois têm na MESMA versão, e a do PC feita com as entradas que o PC tem → fica a do PC (nada é sobrescrito);
  - a do PC não vale mais (versão velha, ou feita com uma entrada que mudou) → vem a do servidor SE ela for a versão que o PC espera
    (o manifesto; na separação entregue, a assinatura dos stems do PC) e feita com as entradas que o PC fica tendo. A do PC vai pra
    _antes_trazer\\<quando>\\ dentro da pasta (nada se perde). Senão fica a do PC (e avisa). As peças são vistas na ORDEM do motor;
  - as rodadas do servidor entram no histórico; o RESUMO.md é refeito.
Pasta nova no PC → vem inteira; o «video» do índice vira o caminho do PC (o servidor.json diz qual era).

  python servidor\\trazer.py --ssh "root@IP -p PORTA -i CHAVE" [--storage /workspace/tandera] [--sem-audio]
  python servidor\\trazer.py --de <pasta com as análises>       (já baixadas por outro caminho: runpodctl receive, \\\\wsl.localhost\\…)
--para <pasta> (padrão: as análises do PC, apps\\TANDERA\\analises) · --sem-audio: não traz os wav grandes (separação e som do preparo;
ficam só no servidor: peça do PC que precisar deles depois refaz a separação) · --so pasta1,pasta2."""
import argparse, json, os, shlex, shutil, subprocess, sys, time

AQUI = os.path.dirname(os.path.abspath(__file__)); T = os.path.dirname(AQUI)
sys.path.insert(0, T)
from tandera import base  # noqa: E402
from tandera.manifesto import ORDEM, PECAS  # noqa: E402
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass
AUDIO_GRANDE = ("pecas/separacao/", "pecas/preparo/som48k.wav", "pecas/preparo/fala16k.wav")


def grande(rel):
    rel = rel.replace("\\", "/")
    return rel.endswith(".wav") and any(rel.startswith(a) or a in rel for a in AUDIO_GRANDE)


def copia_arvore(src, dst, sem_audio=False):
    n = 0
    for raiz, _, fs in os.walk(src):
        for f in fs:
            s = os.path.join(raiz, f); rel = os.path.relpath(s, src)
            if sem_audio and grande(rel): continue
            d = os.path.join(dst, rel)
            if os.path.exists(d): continue
            os.makedirs(os.path.dirname(d), exist_ok=True); shutil.copy2(s, d); n += 1
    return n


def ler(p):
    return json.load(open(p, encoding="utf-8"))


def em_dia(p, g, d):
    """a peça g foi feita com as versões das entradas que o índice d tem? (é o mesmo teste do armazem.precisa)"""
    return all((g.get("feito_com") or {}).get(dep) == (d["pecas"].get(dep) or {}).get("versao") for dep in PECAS[p]["depende"])


def versao_esperada(p, srv):
    """a versão que o PC vai pedir: a do manifesto; a separação ENTREGUE (stems) = a assinatura dos stems do PC (se existem aqui, um
    arquivo por papel) — None = não dá pra saber"""
    if p != "separacao" or not srv.get("stems_pc"): return (PECAS.get(p) or {}).get("versao")
    st = srv["stems_pc"]
    if any(len(v) != 1 or not os.path.exists(v[0]) for v in st.values()): return None
    from tandera.pecas import separacao
    return separacao.versao_entregue(separacao.completar({k: v[0] for k, v in st.items()}))


def assinatura_da_pasta(nome):
    return nome.rsplit("_", 1)[-1]


def achar_no_pc(para, nome):
    """a pasta do PC pra este vídeo: a de mesmo nome, ou outra com a MESMA assinatura (o vídeo copiado com outro nome)"""
    if os.path.isdir(os.path.join(para, nome)): return os.path.join(para, nome)
    a = assinatura_da_pasta(nome)
    ja = [d for d in os.listdir(para) if d.endswith("_" + a) and os.path.exists(os.path.join(para, d, "analise.json"))] if os.path.isdir(para) else []
    return os.path.join(para, max(ja, key=lambda d: len(ler(os.path.join(para, d, "analise.json")).get("pecas", {})))) if ja else None


def juntar(S, para, sem_audio=False):
    """uma pasta de análise do servidor (S) → as análises do PC. Devolve (o que fez, avisos)"""
    nome = os.path.basename(S.rstrip("/\\"))
    dS = ler(os.path.join(S, "analise.json"))
    srv = ler(os.path.join(S, "servidor.json")) if os.path.exists(os.path.join(S, "servidor.json")) else {}
    video_pc = srv.get("video_pc")
    D = achar_no_pc(para, nome)
    avisos = []
    if D is None:
        D = os.path.join(para, nome)
        copia_arvore(S, D, sem_audio)
        dS["video_servidor"] = dS.get("video"); dS["video"] = video_pc or dS.get("video")
        dS.setdefault("trazida", []).append({"quando": time.strftime("%Y-%m-%d %H:%M:%S"), "pecas": sorted(dS["pecas"]), "sem_audio": sem_audio})
        base.salvar_json(os.path.join(D, "analise.json"), dS)
        feito = f"nova no PC ({len(dS['pecas'])} peças)"
    else:
        dD = ler(os.path.join(D, "analise.json"))
        vieram, ficou = [], []
        quando = time.strftime("%Y%m%d-%H%M%S")
        for p in [q for q in ORDEM if q in dS["pecas"]]:          # na ORDEM: a entrada de cada peça já está decidida quando ela chega
            g = dS["pecas"][p]
            jS = os.path.join(S, "pecas", p + ".json")
            if not os.path.exists(jS): continue
            gD = dD["pecas"].get(p); tem = gD and os.path.exists(os.path.join(D, "pecas", p + ".json"))
            atual = versao_esperada(p, srv)
            if tem:
                igual = gD.get("versao") == g.get("versao")
                # a do PC fica se ela vale (mesma versão e feita com as entradas que o PC tem); a do servidor só entra se for a versão que
                # o PC espera, feita com as entradas que o PC vai ter — senão o PC refaria do mesmo jeito
                if igual and em_dia(p, gD, dD):
                    ficou.append(p); continue
                serve = em_dia(p, g, dD) and (igual or (atual is not None and g.get("versao") == atual and gD.get("versao") != atual))
                if not serve:
                    avisos.append(f"{p}: o PC tem {gD.get('versao')}, o servidor {g.get('versao')} — fica a do PC"); ficou.append(p); continue
                guarda = os.path.join(D, "_antes_trazer", quando, "pecas")
                os.makedirs(guarda, exist_ok=True)
                shutil.move(os.path.join(D, "pecas", p + ".json"), os.path.join(guarda, p + ".json"))
                if os.path.isdir(os.path.join(D, "pecas", p)): shutil.move(os.path.join(D, "pecas", p), os.path.join(guarda, p))
            elif os.path.isdir(os.path.join(D, "pecas", p)):          # sobra de uma peça que nunca terminou no PC: guarda e traz limpa
                guarda = os.path.join(D, "_antes_trazer", quando, "pecas"); os.makedirs(guarda, exist_ok=True)
                shutil.move(os.path.join(D, "pecas", p), os.path.join(guarda, p))
            if os.path.isdir(os.path.join(S, "pecas", p)): copia_arvore(os.path.join(S, "pecas", p), os.path.join(D, "pecas", p), sem_audio)
            shutil.copy2(jS, os.path.join(D, "pecas", p + ".json"))
            dD["pecas"][p] = g; vieram.append(p)
        ja = {(r.get("quando"), r.get("perfil")) for r in dD.get("rodadas", [])}
        dD.setdefault("rodadas", []).extend(r for r in dS.get("rodadas", []) if (r.get("quando"), r.get("perfil")) not in ja)
        dD.setdefault("trazida", []).append({"quando": time.strftime("%Y-%m-%d %H:%M:%S"), "de": nome, "vieram": vieram, "ficou_do_pc": ficou,
                                            "sem_audio": sem_audio})
        for f in ("servidor.json", "tandera-servidor.log"):
            if os.path.exists(os.path.join(S, f)): shutil.copy2(os.path.join(S, f), os.path.join(D, f))
        base.salvar_json(os.path.join(D, "analise.json"), dD)
        feito = f"somada no PC: vieram {', '.join(vieram) or 'nenhuma'} · ficaram as do PC: {', '.join(ficou) or 'nenhuma'}"
    try:
        from tandera import motor
        from tandera.armazem import Analise
        motor.escrever_resumo(Analise(video_pc or ler(os.path.join(D, "analise.json"))["video"], D))
    except Exception as e:
        avisos.append(f"RESUMO.md não refeito: {type(e).__name__}: {e}")
    return D, feito, avisos


RCLONE = os.environ.get("TANDERA_RCLONE") or "rclone"   # pacote da Fly: o rclone do PATH
RCONF = os.path.expanduser(os.path.join("~", ".rclone", "rclone.conf"))
DRIVE_RES = os.environ.get("TANDERA_DRIVE_RESULTADOS") or "drive:TANDERA-RESULTADOS"


def pela_nuvem(a, cmd, R, pegar, lista):
    """06/11 (ele: «o resultado das análises, qual que é mais rápido, ir pro Drive ou ir pro meu PC? Porque a placa vai ficar ligada
    nesse tempo»): a placa empacota o que vem (um .tar) e manda pro Drive dele (~150 MB/s; direto pro PC era ~9 MB/s, com as placas
    ligadas). Roda SOLTO na placa (nohup) e aqui só confiro com conexões curtas. Depois o PC baixa do Drive SOZINHO, num processo à
    parte (--do-drive), e o runpod já pode desligar tudo. Devolve False se a placa não tem rclone (aí vai pelo caminho antigo)."""
    if "SIM" not in subprocess.run(cmd + ["command -v rclone >/dev/null && [ -s /root/.config/rclone/rclone.conf ] && echo SIM"],
                                   capture_output=True, text=True, encoding="utf-8", errors="replace").stdout:
        return False
    nome = time.strftime("%Y%m%d-%H%M%S")
    exc = ("--exclude='*/pecas/separacao/*.wav' --exclude='*/pecas/preparo/som48k.wav' --exclude='*/pecas/preparo/fala16k.wav'"
           if a.sem_audio else "")
    # 07/11: com 845 pastas a lista na linha de comando passava do limite do Windows (32 mil caracteres) e o pacote nem começava
    # (estado «?» pra sempre) → a lista vai ANTES, como arquivo, pela entrada do ssh
    subprocess.run(cmd + [f"mkdir -p /workspace/_trazer && cat > /workspace/_trazer/{nome}.lista"], input=("\n".join(pegar) + "\n").encode("utf-8"),
                   check=True, timeout=300)          # em bytes: como texto o Windows punha \r em cada nome e o tar não achava nenhum
    script = (f"cd {R} && echo EMPACOTANDO > /root/trazer.estado && "
              f"tar --ignore-failed-read {exc} -cf /workspace/_trazer/{nome}.tar -T /workspace/_trazer/{nome}.lista && echo SUBINDO > /root/trazer.estado && "
              f"rclone copyto --drive-chunk-size 256M /workspace/_trazer/{nome}.tar {DRIVE_RES}/{nome}.tar && echo PRONTO > /root/trazer.estado "
              f"|| echo FALHOU > /root/trazer.estado")
    subprocess.run(cmd + [f"rm -f /root/trazer.estado; nohup bash -c {shlex.quote(script)} > /root/trazer.log 2>&1 < /dev/null &"], timeout=120)
    t0, ult = time.time(), ""
    while True:
        time.sleep(15)
        try:
            est = subprocess.run(cmd + ["cat /root/trazer.estado 2>/dev/null || echo ?"], capture_output=True, text=True, encoding="utf-8",
                                 errors="replace", timeout=90).stdout.strip()
        except subprocess.TimeoutExpired:
            continue
        if est != ult: print(f"resultados: {est} ({int(time.time() - t0)} s)", flush=True); ult = est
        if est == "PRONTO": break
        if est == "FALHOU":
            log = subprocess.run(cmd + ["tail -5 /root/trazer.log"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
            raise SystemExit(f"os resultados não subiram pro Drive: {log}")
    # o PC baixa e soma depois, sozinho (a placa já pode desligar)
    pend = os.path.join(a.para, f"_pendente_{nome}.json")
    base.salvar_json(pend, {"nome": nome, "pegar": pegar, "lista": {p: lista[p] for p in pegar}, "sem_audio": a.sem_audio})
    subprocess.Popen([sys.executable, os.path.abspath(__file__), "--do-drive", pend, "--para", a.para],
                     creationflags=0x00000008 | 0x00000200 | 0x08000000,   # solto do processo do runpod, sem janela
                     stdout=open(pend[:-5] + ".log", "w", encoding="utf-8"), stderr=subprocess.STDOUT, close_fds=True)
    print(f"resultados no Drive ({DRIVE_RES}/{nome}.tar); o PC baixa e soma sozinho (log: {pend[:-5]}.log)", flush=True)
    return True


def do_drive(pend, para):
    """a 2ª metade: Drive → PC, desempacota, soma nas análises do PC, marca como trazidas, atualiza o checklist"""
    P = ler(pend); nome = P["nome"]
    origem = os.path.join(para, f"_chegando_{nome}"); os.makedirs(origem, exist_ok=True)
    tarq = os.path.join(origem, "_r.tar")
    t0 = time.time()
    subprocess.run([RCLONE, "--config", RCONF, "copyto", f"{DRIVE_RES}/{nome}.tar", tarq, "--multi-thread-streams", "8"], check=True,
                   creationflags=0x08000000)
    print(f"baixado do Drive em {time.time() - t0:.0f} s ({os.path.getsize(tarq) / 1e9:.1f} GB)", flush=True)
    tar = r"C:\Windows\System32\tar.exe" if os.path.exists(r"C:\Windows\System32\tar.exe") else "tar"
    subprocess.run([tar, "-xf", tarq, "-C", origem], check=True, creationflags=0x08000000)
    os.remove(tarq)
    pastas = sorted(d for d in os.listdir(origem) if os.path.exists(os.path.join(origem, d, "analise.json")))
    for d in pastas:
        D, feito, avisos = juntar(os.path.join(origem, d), para, P.get("sem_audio"))
        print(f"{d}: {feito} → {D}", flush=True)
        for x in avisos: print("   aviso:", x)
    marca = os.path.join(para, "_trazidas.json")
    ja = ler(marca) if os.path.exists(marca) else {}
    ja.update({p: P["lista"][p] for p in pastas if p in P["lista"]}); base.salvar_json(marca, ja)
    shutil.rmtree(origem, ignore_errors=True)
    os.replace(pend, pend.replace("_pendente_", "_feito_"))
    subprocess.run([os.path.join(T, "tandera.cmd"), "checklist"], capture_output=True, creationflags=0x08000000)
    print(f"FIM: {len(pastas)} análises somadas no PC em {time.time() - t0:.0f} s", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ssh", default=""); ap.add_argument("--wsl", default=""); ap.add_argument("--storage", default="/workspace/tandera")
    ap.add_argument("--de", default=""); ap.add_argument("--para", default=base.ANALISES); ap.add_argument("--so", default="")
    ap.add_argument("--sem-audio", action="store_true"); ap.add_argument("--direto", action="store_true", help="sem o Drive (o caminho antigo)")
    ap.add_argument("--do-drive", default="", help="(interno) baixa do Drive o pacote pendente e soma no PC")
    a = ap.parse_args()
    if a.do_drive:
        return do_drive(a.do_drive, a.para)
    so = {s.strip() for s in a.so.split(",") if s.strip()}
    os.makedirs(a.para, exist_ok=True)
    if a.de:
        origem = a.de
    else:
        if not (a.ssh or a.wsl): raise SystemExit("de onde: --ssh \"root@IP -p PORTA -i CHAVE\", --wsl Ubuntu-24.04 ou --de <pasta>")
        cmd = (["wsl", "-d", a.wsl, "-e", "bash", "-c"] if a.wsl else
               ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new", *shlex.split(a.ssh, posix=(os.name != "nt"))])
        R = a.storage.rstrip("/") + "/analises"
        # só o que mudou desde a última vez (a data do analise.json de cada pasta)
        r = subprocess.run(cmd + [f"cd {R} 2>/dev/null && for d in */; do stat --printf '%n\\t%Y\\n' \"$d/analise.json\" 2>/dev/null; done"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        lista = {l.split("\t")[0].split("/")[0]: int(l.split("\t")[1]) for l in r.stdout.splitlines() if "\t" in l}
        marca = os.path.join(a.para, "_trazidas.json")
        ja = ler(marca) if os.path.exists(marca) else {}
        pegar = sorted(p for p, m in lista.items() if (not so or p in so) and ja.get(p) != m)
        print(f"{len(lista)} análises no servidor · {len(pegar)} novas ou mudadas", flush=True)
        if not pegar: return
        if a.ssh and not a.direto and pela_nuvem(a, cmd, R, pegar, lista): return
        origem = os.path.join(a.para, "_chegando"); os.makedirs(origem, exist_ok=True)
        exc = ("--exclude='*/pecas/separacao/*.wav' --exclude='*/pecas/preparo/som48k.wav' --exclude='*/pecas/preparo/fala16k.wav'"
               if a.sem_audio else "")
        pr =subprocess.Popen(cmd + [f"tar -C {R} {exc} -cf - " + " ".join(shlex.quote(p) for p in pegar)], stdout=subprocess.PIPE)
        tar = r"C:\Windows\System32\tar.exe" if os.path.exists(r"C:\Windows\System32\tar.exe") else "tar"   # o do Git Bash lê «C:» como máquina
        subprocess.run([tar, "-xf", "-", "-C", origem], stdin=pr.stdout, check=True)
        pr.stdout.close()
        if pr.wait() > 1: raise SystemExit("a cópia do servidor falhou")
        so = set(pegar)
    pastas = sorted(d for d in os.listdir(origem) if os.path.exists(os.path.join(origem, d, "analise.json")) and (not so or d in so))
    for d in pastas:
        D, feito, avisos = juntar(os.path.join(origem, d), a.para, a.sem_audio)
        print(f"{d}: {feito} → {D}")
        for x in avisos: print("   aviso:", x)
    if not a.de:
        ja.update({p: lista[p] for p in pastas if p in lista}); base.salvar_json(marca, ja)
        shutil.rmtree(origem, ignore_errors=True)


if __name__ == "__main__":
    main()
