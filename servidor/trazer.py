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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ssh", default=""); ap.add_argument("--wsl", default=""); ap.add_argument("--storage", default="/workspace/tandera")
    ap.add_argument("--de", default=""); ap.add_argument("--para", default=base.ANALISES); ap.add_argument("--so", default="")
    ap.add_argument("--sem-audio", action="store_true")
    a = ap.parse_args()
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
