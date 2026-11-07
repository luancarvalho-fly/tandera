# -*- coding: utf-8 -*-
"""ENVIA do PC pro storage do servidor (01/11, panelas de som): o código do Tandera, os pesos que só existem no PC, e os vídeos/stems
de um lote. Vai por UM tar pela conexão (ssh, ou o WSL na prova): o tar leva a DATA de cada arquivo e o servidor a devolve na
extração — a assinatura do Tandera (tamanho + data + 1 MB do começo e do fim) sai igual lá e cá, e a análise volta com o nome certo.
(O rodar_lote.py ainda confere: se a data se perdeu, acerta pela data do lote; se o conteúdo mudou, não analisa.)
Arquivo que já está lá com o mesmo tamanho e a mesma data é pulado (o envio pode cair e recomeçar).

  python servidor\\enviar.py --ssh "root@IP -p PORTA -i <caminho da SUA chave ssh>" --codigo --pesos --lote <lote.json>
  python servidor\\enviar.py --wsl Ubuntu-24.04 --destino /root/storage/tandera --codigo --pesos --lote <lote.json>     (a prova)
--destino = a pasta do Tandera no storage (padrão /workspace/tandera)."""
import argparse, json, os, shlex, subprocess, sys, tarfile, time, unicodedata

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
    # ServerAlive: sessão longa sem saída (o tar dos pesos) não cai calada no meio do caminho (06/11)
    return ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new", "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=6",
            *shlex.split(a.ssh, posix=(os.name != "nt")), comando]


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
    # 06/11 (o motor INTEIRO no servidor, Luan: «os modelos não é a gente que upa do motor do Tandera?»): os pesos das peças de imagem
    # que só existem no PC — rostos (SCRFD, AdaFace, EmotiEff: TANDERA\modelos), corpo (Sapiens2 + DETR), câmera (CoTracker3), boca
    # (OpenFace 3.0) com os códigos deles (REGUA\repos) e o MediaPipe Pose heavy (a ferramenta pisada)
    REGUA = os.environ.get("TANDERA_REGUA") or os.path.join(T, "terceiros", "REGUA")   # pacote da Fly
    pastas = [(os.path.join(T, "modelos"), "do_pc/tandera_modelos")] + \
             [(os.path.join(REGUA, "modelos", m), "do_pc/regua/modelos/" + m) for m in ("sapiens2", "cotracker3", "openface3")] + \
             [(os.path.join(REGUA, "repos", r), "do_pc/regua/repos/" + r) for r in ("sapiens2", "co-tracker")]
    for src, dst in pastas:
        for raiz, dirs, fs in os.walk(src):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
            out += [(os.path.join(raiz, f), dst + "/" + os.path.relpath(os.path.join(raiz, f), src).replace("\\", "/")) for f in fs]
    out.append((os.environ.get("TANDERA_POSE") or os.path.join(T, "modelos", "pose_landmarker_heavy.task"), "do_pc/pose_landmarker_heavy.task"))
    return out


# 06/11 (baterias): a análise que o PC JÁ TEM sobe junto, pro servidor rodar só o que falta (o rodar_lote continua dela). Sobem os .json
# (o índice + cada peça) e os arquivos do preparo que as peças leem; os wav grandes (som48k, stems) e os vetores ficam (não são entrada)
DA_ANALISE = ("preparo/q1/", "preparo/leve480", "preparo/fala16k", "preparo/mini/")


def da_analise(pasta_pc, pasta):
    out = []
    for raiz, dirs, fs in os.walk(pasta_pc):
        for f in fs:
            full = os.path.join(raiz, f); rel = os.path.relpath(full, pasta_pc).replace("\\", "/")
            if rel == "analise.json" or (rel.startswith("pecas/") and rel.count("/") == 1 and f.endswith(".json")) or                any(rel.startswith("pecas/" + d) for d in DA_ANALISE):
                out.append((full, f"analises/{pasta}/{rel}"))
    return out


def do_lote(caminho):
    L = json.load(open(caminho, encoding="utf-8"))
    out = [(caminho, f"lotes/{L['nome']}.json")]
    for i in L["itens"]:
        if i.get("analise_pc") and os.path.exists(os.path.join(i["analise_pc"], "analise.json")):
            out += da_analise(i["analise_pc"], i["pasta"])
        if i.get("sem_video"): continue
        out.append((i["video_pc"], i["rel"]))
        out += [(a["pc"], a["rel"]) for v in i["stems"].values() for a in v]
    return out


def pelo_drive(a, D, manda):
    """06/11 (ele: «não é mais fácil a gente fazer pelo drive... de database pra database?»): os VÍDEOS que já estão no Drive dele
    (subidos antes, com a placa desligada, por trabalho\\runpod\\subir_drive.py em <remoto>/<letra>/<caminho do PC>) a placa baixa
    direto do Google (centenas de MB/s), em paralelo; pela conexão do PC vai só o resto (código, pesos, análises). O que não está no
    Drive (tamanho diferente ou ausente) segue pelo tar, como sempre. Devolve o que ainda falta mandar pelo tar."""
    conf = os.path.expanduser(os.path.join("~", ".rclone", "rclone.conf"))
    remoto_drive = a.drive.rstrip("/")
    videos = [(p, rel) for p, rel in manda if rel.startswith("entrada/")]
    if not videos: return manda
    rcl = os.environ.get("TANDERA_RCLONE") or "rclone"   # pacote da Fly: o rclone do PATH
    no_drive = {}
    for letra in sorted({os.path.splitdrive(p)[0][0].upper() for p, _ in videos}):
        r = subprocess.run([rcl, "--config", conf, "lsf", "-R", "--files-only", "--format", "ps", "--separator", "\t",
                            f"{remoto_drive}/{letra}"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        for l in r.stdout.splitlines():
            c, _, t = l.rpartition("\t")
            if c and t.isdigit(): no_drive[(letra, unicodedata.normalize("NFC", c).lower())] = (int(t), c)   # o Drive guarda o nome real; a lista pode vir com outra caixa
    pares, resto = [], [x for x in manda if not x[1].startswith("entrada/")]
    for p, rel in videos:
        d, cam = os.path.splitdrive(p)
        cam = cam.lstrip("\\/").replace("\\", "/")
        achou = no_drive.get((d[0].upper(), unicodedata.normalize("NFC", cam).lower()))
        if achou and achou[0] == os.path.getsize(p): pares.append((f"{remoto_drive}/{d[0].upper()}/{achou[1]}", rel))
        else: resto.append((p, rel))
    print(f"pelo Drive: {len(pares)} vídeos ({sum(os.path.getsize(p) for p, rel in videos if any(rel == r2 for _, r2 in pares)) / 1e9:.1f} GB)"
          f" · pelo PC: {len(resto)} arquivos", flush=True)
    if not pares: return manda
    # a configuração do rclone dele (a chave do Drive dele, client_id próprio) vai pro disco da máquina, nunca pro storage nem pro log
    with open(conf, "rb") as f:
        subprocess.run(remoto(a, "mkdir -p /root/.config/rclone && cat > /root/.config/rclone/rclone.conf && chmod 600 /root/.config/rclone/rclone.conf"),
                       input=f.read(), check=True)
    lst = "\n".join(f"{src}\t{D}/{rel}" for src, rel in pares) + "\n"
    # 06/11 (1º lote): UMA sessão ssh de 20 min sem saída ficou pendurada (o download tinha acabado, o PC nunca soube; matar a sessão
    # fez o lote achar que falhou e apagar 186 GB já baixados). Agora o download roda SOLTO na placa (nohup) e o PC só confere, com
    # conexões curtas a cada 20 s, o arquivo /root/drive.estado (BAIXANDO → PRONTO / FALHOU)
    baixa = r'''#!/bin/bash
command -v rclone >/dev/null || (curl -s https://rclone.org/install.sh | bash >/dev/null 2>&1)
echo BAIXANDO > /root/drive.estado
while IFS=$'\t' read -r s d; do printf '%s\0%s\0' "$s" "$d"; done < /root/drive_lista.tsv |
  xargs -0 -n2 -P 6 sh -c 'mkdir -p "$(dirname "$1")" && rclone copyto --drive-chunk-size 256M "$0" "$1" || echo "$0" >> /root/drive.falhou'
if [ -s /root/drive.falhou ]; then echo FALHOU > /root/drive.estado; else echo PRONTO > /root/drive.estado; fi
'''
    subprocess.run(remoto(a, "cat > /root/drive_lista.tsv"), input=lst.encode("utf-8"), check=True, timeout=300)
    subprocess.run(remoto(a, "cat > /root/drive_baixa.sh && chmod +x /root/drive_baixa.sh && rm -f /root/drive.falhou /root/drive.estado"),
                   input=baixa.encode("utf-8"), check=True, timeout=120)
    subprocess.run(remoto(a, "nohup /root/drive_baixa.sh > /root/drive.log 2>&1 < /dev/null &"), check=True, timeout=120)
    t0, ult = time.time(), ""
    while True:
        time.sleep(20)
        try:
            r = subprocess.run(remoto(a, f"cat /root/drive.estado 2>/dev/null || echo ?; find {D}/entrada -type f 2>/dev/null | wc -l"),
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        except subprocess.TimeoutExpired:
            continue                                   # conexão lenta: tenta na próxima volta
        partes = (r.stdout or "").split()
        est = partes[0] if partes else "?"
        agora = f"Drive → placa: {est} · {partes[1] if len(partes) > 1 else '?'}/{len(pares)} vídeos"
        if agora != ult: print(f"{agora} ({int(time.time() - t0)} s)", flush=True); ult = agora
        if est == "PRONTO": break
        if est == "FALHOU":
            f = subprocess.run(remoto(a, "head -20 /root/drive.falhou"), capture_output=True, text=True, encoding="utf-8", errors="replace")
            raise SystemExit(f"a placa não conseguiu baixar do Drive:\n{f.stdout}")
    print(f"Drive → placa: {len(pares)} vídeos em {time.time() - t0:.0f} s", flush=True)
    return resto


RCL = os.environ.get("TANDERA_RCLONE") or "rclone"   # pacote da Fly: o rclone do PATH
RCONF = os.path.expanduser(os.path.join("~", ".rclone", "rclone.conf"))
ENVIO = "drive-luan:TANDERA-ENVIO"


def nome_pacote(a):
    return (json.load(open(a.lote, encoding="utf-8"))["nome"] if a.lote else "codigo") + ".tar"


def fazer_pacote(a, lista):
    """07/11 (ele: «por que você não mandou do drive pra placa?»): o que NÃO é vídeo (código, pesos, as análises do PC — 13 GB em 46 mil
    arquivos no 1º lote, 33 min de placa parada pelo ssh) vira UM .tar que sobe pro Drive ANTES da placa ligar (--so-pacote, chamado
    pelo runpod.py); com a placa no ar ela baixa e abre (pacote_na_placa)."""
    resto = [(p, rel) for p, rel in lista if not rel.startswith("entrada/")]
    nome = nome_pacote(a)
    tmp = os.path.join(os.environ.get("TEMP", "."), "tandera-" + nome)
    t0 = time.time()
    with tarfile.open(tmp, "w", format=tarfile.PAX_FORMAT) as tar:
        for p, rel in resto: tar.add(p, arcname=rel, recursive=False)
    gb = os.path.getsize(tmp) / 1e9
    print(f"pacote: {len(resto)} arquivos · {gb:.2f} GB em {time.time() - t0:.0f} s → {ENVIO}/{nome}", flush=True)
    subprocess.run([RCL, "--config", RCONF, "copyto", tmp, f"{ENVIO}/{nome}", "--drive-chunk-size", "256M"], check=True, creationflags=0x08000000)
    os.remove(tmp)
    print(f"pacote no Drive em {time.time() - t0:.0f} s", flush=True)


def pacote_na_placa(a, D):
    """a placa baixa o pacote do Drive e abre no storage (solta na placa, conferido com conexões curtas). True se deu."""
    nome = nome_pacote(a)
    r = subprocess.run([RCL, "--config", RCONF, "lsf", f"{ENVIO}/{nome}"], capture_output=True, text=True, creationflags=0x08000000)
    if nome not in r.stdout: return False
    script = (f"rm -f /root/pacote.estado; (rclone copyto --drive-chunk-size 256M --multi-thread-streams 8 {ENVIO}/{nome} /workspace/_pacote.tar "
              f"&& tar -C {D} -xf /workspace/_pacote.tar && rm -f /workspace/_pacote.tar && echo PRONTO > /root/pacote.estado "
              f"|| echo FALHOU > /root/pacote.estado)")
    subprocess.run(remoto(a, f"nohup bash -c {shlex.quote(script)} > /root/pacote.log 2>&1 < /dev/null &"), check=True, timeout=120)
    t0 = time.time()
    while True:
        time.sleep(15)
        try:
            est = subprocess.run(remoto(a, "cat /root/pacote.estado 2>/dev/null || echo BAIXANDO"), capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=90).stdout.strip()
        except subprocess.TimeoutExpired:
            continue
        if est == "PRONTO": print(f"pacote do Drive aberto na placa em {time.time() - t0:.0f} s", flush=True); return True
        if est == "FALHOU": print("o pacote do Drive falhou na placa: vai pelo ssh", flush=True); return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drive", default="", help="remoto do rclone onde os vídeos já estão (ex.: drive-luan:TANDERA-ENTRADA)")
    ap.add_argument("--so-pacote", action="store_true", help="só monta o pacote (código, pesos, análises) e sobe pro Drive — sem placa")
    ap.add_argument("--ssh", default=""); ap.add_argument("--wsl", default=""); ap.add_argument("--destino", default="/workspace/tandera")
    ap.add_argument("--codigo", action="store_true"); ap.add_argument("--pesos", action="store_true"); ap.add_argument("--lote", default="")
    a = ap.parse_args()
    lista = (codigo() if a.codigo else []) + (pesos() if a.pesos else []) + (do_lote(a.lote) if a.lote else [])
    falta = [p for p, _ in lista if not os.path.exists(p)]
    if falta: raise SystemExit("não achei no PC:\n  " + "\n  ".join(falta))
    if a.so_pacote: return fazer_pacote(a, lista)
    if not (a.ssh or a.wsl): raise SystemExit("diga pra onde: --ssh \"root@IP -p PORTA -i CHAVE\" ou --wsl Ubuntu-24.04")
    D = a.destino.rstrip("/")
    # o que já está lá (tamanho e data): pula
    r = subprocess.run(remoto(a, f"mkdir -p {D} && cd {D} && find . -type f -printf '%P\\t%s\\t%T@\\n'"), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    la = {}
    for l in r.stdout.splitlines():
        p = l.split("\t")
        if len(p) == 3: la[p[0]] = (int(p[1]), float(p[2]))
    manda = [(p, rel) for p, rel in lista if not (rel in la and la[rel][0] == os.path.getsize(p) and int(la[rel][1]) == int(os.stat(p).st_mtime))]
    if a.drive:
        manda = pelo_drive(a, D, manda)
        if any(not rel.startswith("entrada/") for _, rel in manda) and pacote_na_placa(a, D):
            manda = [(p, rel) for p, rel in manda if rel.startswith("entrada/")]      # o resto veio no pacote
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
