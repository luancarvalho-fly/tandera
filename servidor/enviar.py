# -*- coding: utf-8 -*-
"""ENVIA do PC pro storage do servidor (01/11, panelas de som): o código do Tandera, os pesos que só existem no PC, e os vídeos/stems
de um lote. Vai por UM tar pela conexão (ssh, ou o WSL na prova): o tar leva a DATA de cada arquivo e o servidor a devolve na
extração — a assinatura do Tandera (tamanho + data + 1 MB do começo e do fim) sai igual lá e cá, e a análise volta com o nome certo.
(O rodar_lote.py ainda confere: se a data se perdeu, acerta pela data do lote; se o conteúdo mudou, não analisa.)
Arquivo que já está lá com o mesmo tamanho e a mesma data é pulado (o envio pode cair e recomeçar).

  python servidor\\enviar.py --ssh "root@IP -p PORTA -i <caminho da SUA chave ssh>" --codigo --pesos --lote <lote.json>
  python servidor\\enviar.py --wsl Ubuntu-24.04 --destino /root/storage/tandera --codigo --pesos --lote <lote.json>     (a prova)
--destino = a pasta do Tandera no storage (padrão /workspace/tandera)."""
import argparse, json, os, shlex, subprocess, sys, tarfile, time

AQUI = os.path.dirname(os.path.abspath(__file__)); T = os.path.dirname(AQUI)
# pacote da Fly: no PC do Luan eram as pastas dele; aqui o código do BandIt vem em terceiros\ e o modelo do Roformer fica onde o
# audio-separator guarda (C:\tmp\... no Windows, /tmp/... no Mac/Linux), ou onde as variáveis disserem
CINE = os.environ.get("TANDERA_CINE") or os.path.join(T, "terceiros", "separador-cinema")
ROFO_PC = os.environ.get("TANDERA_ROFO_MODELOS") or os.path.abspath("/tmp/audio-separator-models")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass


def remoto(a, comando):
    """o comando que roda no servidor (lista de argumentos pro subprocess do Windows)"""
    if a.wsl: return ["wsl", "-d", a.wsl, "-e", "bash", "-c", comando]
    return ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new", *shlex.split(a.ssh, posix=(os.name != "nt")), comando]


def codigo():
    out = []
    for raiz, dirs, fs in os.walk(os.path.join(T, "tandera")):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        out += [(os.path.join(raiz, f), "codigo/" + os.path.relpath(os.path.join(raiz, f), T).replace("\\", "/")) for f in fs
                if f.endswith((".py", ".sh"))]
    for raiz, dirs, fs in os.walk(AQUI):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "lotes")]
        out += [(os.path.join(raiz, f), "codigo/" + os.path.relpath(os.path.join(raiz, f), T).replace("\\", "/")) for f in fs
                if f.endswith((".py", ".sh", ".txt", ".md"))]
    out.append((os.path.join(T, "LEIA-ME.md"), "codigo/LEIA-ME.md"))
    return out


def pesos():
    """o que só existe no PC: o AutoShot do CUTX, o BandIt Plus + o código do msst e o stub do separador-cinema, e o BS-Roformer
    (o mesmo arquivo do PC; o servidor baixaria igual, mas assim é o MESMO)"""
    out = [(os.environ.get("TANDERA_AUTOSHOT") or os.path.join(T, "modelos", "autoshot.onnx"), "do_pc/autoshot.onnx")]
    for f in ("model_bs_roformer_ep_317_sdr_12.9755.ckpt", "model_bs_roformer_ep_317_sdr_12.9755.yaml"):
        if os.path.exists(os.path.join(ROFO_PC, f)):          # pacote da Fly: sem ele aqui, o preparar_tandera.sh baixa da fonte
            out.append((os.path.join(ROFO_PC, f), "do_pc/audio-separator/" + f))
    for raiz, dirs, fs in os.walk(os.path.join(CINE, "msst")):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "docs", "tests", "gui")]
        out += [(os.path.join(raiz, f), "do_pc/separador-cinema/" + os.path.relpath(os.path.join(raiz, f), CINE).replace("\\", "/")) for f in fs]
    for f in ("config_dnr_bandit_bsrnn_multi_mus64.yaml", "model_bandit_plus_dnr_sdr_11.47.chpt"):
        out.append((os.path.join(CINE, "modelos-teste", "bandit_plus", f), "do_pc/separador-cinema/modelos-teste/bandit_plus/" + f))
    out.append((os.path.join(CINE, "modelos-teste", "bancada", "rodar_msst_stub.py"), "do_pc/separador-cinema/modelos-teste/bancada/rodar_msst_stub.py"))
    return out


def do_lote(caminho):
    L = json.load(open(caminho, encoding="utf-8"))
    out = [(caminho, f"lotes/{L['nome']}.json")]
    for i in L["itens"]:
        out.append((i["video_pc"], i["rel"]))
        out += [(a["pc"], a["rel"]) for v in i["stems"].values() for a in v]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ssh", default=""); ap.add_argument("--wsl", default=""); ap.add_argument("--destino", default="/workspace/tandera")
    ap.add_argument("--codigo", action="store_true"); ap.add_argument("--pesos", action="store_true"); ap.add_argument("--lote", default="")
    a = ap.parse_args()
    if not (a.ssh or a.wsl): raise SystemExit("diga pra onde: --ssh \"root@IP -p PORTA -i CHAVE\" ou --wsl Ubuntu-24.04")
    lista = (codigo() if a.codigo else []) + (pesos() if a.pesos else []) + (do_lote(a.lote) if a.lote else [])
    falta = [p for p, _ in lista if not os.path.exists(p)]
    if falta: raise SystemExit("não achei no PC:\n  " + "\n  ".join(falta))
    D = a.destino.rstrip("/")
    # o que já está lá (tamanho e data): pula
    r = subprocess.run(remoto(a, f"mkdir -p {D} && cd {D} && find . -type f -printf '%P\\t%s\\t%T@\\n'"), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    la = {}
    for l in r.stdout.splitlines():
        p = l.split("\t")
        if len(p) == 3: la[p[0]] = (int(p[1]), float(p[2]))
    manda = [(p, rel) for p, rel in lista if not (rel in la and la[rel][0] == os.path.getsize(p) and int(la[rel][1]) == int(os.stat(p).st_mtime))]
    gb = sum(os.path.getsize(p) for p, _ in manda) / 1e9
    print(f"{len(lista)} arquivos · {len(lista) - len(manda)} já estão lá · mandando {len(manda)} ({gb:.2f} GB) → {a.wsl or a.ssh}:{D}", flush=True)
    if not manda: return
    t0 = time.time()
    pr = subprocess.Popen(remoto(a, f"tar -C {D} -xf -"), stdin=subprocess.PIPE)
    with tarfile.open(fileobj=pr.stdin, mode="w|", format=tarfile.PAX_FORMAT) as tar:
        for k, (p, rel) in enumerate(manda, 1):
            tar.add(p, arcname=rel, recursive=False)
            if k % 50 == 0 or os.path.getsize(p) > 200e6: print(f"  {k}/{len(manda)}  {rel}", flush=True)
    pr.stdin.close()
    if pr.wait(): raise SystemExit(f"o tar do outro lado falhou (código {pr.returncode})")
    print(f"pronto em {time.time() - t0:.0f} s ({gb * 1000 / max(1, time.time() - t0):.0f} MB/s)")


if __name__ == "__main__":
    main()
