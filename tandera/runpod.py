# -*- coding: utf-8 -*-
"""ONDE RODAR: o PC ou o RunPod (06/11, Luan: «eu quero ter a opção de ou fazer pelo RunPod ou pelo computador»). Este arquivo só
ORQUESTRA — liga/desliga placa e disco pela API do RunPod e chama o caminho do servidor que já existe desde 01/11 (um motor só):
  servidor\\montar_lote.item  → o lote (assinatura do PC, a pasta da análise, as peças de cada vídeo)
  servidor\\enviar.py         → código + pesos + lote + a análise que o PC JÁ TEM (o servidor roda só o que falta) + os vídeos que precisam
  servidor\\preparar_tandera.sh → a máquina (ambientes com as versões do PC, modelos guardados no disco de rede pra próxima máquina)
  servidor\\rodar_lote.py     → a fila DIVIDIDA entre as placas (no disco de rede), peça por peça em blocos
  servidor\\trazer.py         → soma no PC pela versão de cada peça (nada do PC é sobrescrito à toa); --sem-audio = só o relatório

  tandera runpod --grupo 2-cliente-bruto --bateria reconhecimento            o que falta da bateria no grupo (pelo checklist)
  tandera runpod --lista dias.txt --pista bruto --bateria profunda --placas 3   arquivos escolhidos (um caminho por linha)
  tandera runpod ... --so-contar        mostra o lote (vídeos, peças, o que sobe, custo estimado) e NÃO liga nada
  tandera runpod --teste <vídeo curto> --pista bruto   a prova: o servidor faz TODAS as peças do zero e compara com o PC
  tandera runpod --desligar             desliga as placas e apaga o disco do estado (se algo ficou ligado)

Sempre: a placa e o disco são apagados no fim, até com erro (--manter deixa). Chave: ~/.runpod/chave-api.txt (nunca impressa).
SSH: ~/.ssh/runpod_luan. Andamento: trabalho\\runpod\\<lote>\\ (estado.json, os logs, o checklist antes/depois)."""
import argparse, json, os, shutil, subprocess, sys, time, urllib.error, urllib.request

from . import base
from .manifesto import PECAS, com_dependencias

API = "https://rest.runpod.io/v1"
CHAVE = os.path.expanduser(os.path.join("~", ".runpod", "chave-api.txt"))
SSH_CHAVE = os.path.expanduser(os.path.join("~", ".ssh", "runpod_luan"))
TRABALHO = os.path.join(base.TANDERA, "trabalho", "runpod")
ESTADO = os.path.join(TRABALHO, "estado.json")
CHECKLIST = os.path.join(base.TANDERA, "checklist", "checklist.json")
SERV = os.path.join(base.TANDERA, "servidor")
W = "/workspace/tandera"                           # o disco de rede, montado em /workspace em toda placa
# DISCO FIXO (07/11): quem tem um disco de rede só com os motores (codigo/ pesos/ do_pc/ wheels/ hf/ do Tandera) põe o endereço dele em
# ~/.runpod/tandera_disco_fixo.json → {"id": "<id do disco>", "centro": "<data center>", "livre_gb": <o que sobra além dos motores>}.
# Lote que cabe no que sobra roda NELE: não sobe os pesos, não apaga o disco; no fim só limpa entrada/ analises/ fila/ do lote.
# Sem o arquivo (ou lote maior, ou sem placa no centro dele) → o jeito de sempre: um disco por lote, apagado no fim.
# O arquivo é de cada máquina: fica FORA do repositório (é o disco da conta de quem roda).
def _fixo():
    try:
        d = json.load(open(os.path.expanduser(os.path.join("~", ".runpod", "tandera_disco_fixo.json")), encoding="utf-8"))
        return {"id": d["id"], "centro": d["centro"]}, float(d.get("livre_gb", 30))
    except Exception:
        return None, 0.0


FIXO, FIXO_LIVRE_GB = _fixo()
# placas de 24 GB+ (Gemma 12B ~10 GB · Sapiens2 ~5,5 · Ovis ~6; uma peça por vez), da mais em conta pra mais cara; a 1ª com vaga leva
GPUS = ["NVIDIA RTX PRO 4500 Blackwell", "NVIDIA RTX PRO 4000 Blackwell", "NVIDIA A40",   # (a «Server Edition» não está na lista da API v1: 400)
        "NVIDIA RTX A6000", "NVIDIA RTX A5000", "NVIDIA GeForce RTX 3090", "NVIDIA GeForce RTX 4090", "NVIDIA L40S"]
# A PLACA DELE = RTX PRO 4500 (decidido 01/11 no Flynder e de novo 06/11: «tem que pegar aquela placa boa, a RTX 4500, que tem chip de
# vídeo»: só Blackwell abre o 4:2:2 da Sony no chip, a PRO 4500 SE tem 3 NVDEC; a 5090 do RunPod dá CUDA_ERROR_NO_DEVICE no chip).
# As outras só se não tiver PRO 4500 em lugar nenhum (driver_ok confere o cu128)
# 06/11 ~19h: com o disco de rede só sobravam as Blackwell (PRO 4000 24 GB US$0,57/h e PRO 4500 32 GB US$0,72/h: EU-RO-1, EU-CZ-1,
# EUR-IS-1) — a mesma família da 5070 do PC (torch cu128), então entram na lista; preços do Secure lidos na API nessa hora
# 06/11 (preços na tela dele, Secure com disco de rede): A40/A6000 48 GB US$0,59/h = o melhor por real com o motor inteiro; 3090/A5000 24 GB
# US$0,50; 4090 US$0,89. Lote leve (só diário pelo Gemma + busca) cabe na RTX 4000 Ada 20 GB a US$0,28/h: --gpu "NVIDIA RTX 4000 Ada Generation"
# disco de rede só existe no Secure Cloud e a placa tem que estar no MESMO centro: tenta nesta ordem (EUA/Europa com mais 4090)
CENTROS = ["US-KS-2", "US-TX-3", "US-CA-2", "US-GA-2", "EU-RO-1", "EU-CZ-1", "EUR-IS-1", "CA-MTL-1", "US-IL-1", "EU-SE-1", "EU-NL-1"]
IMAGEM = "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"   # só a base (Ubuntu + sshd); os ambientes do PC vão por cima
# as peças que NÃO leem o vídeo original (leem o que o PC mandou da análise: q1, leve480, fala16k, os .json): o vídeo não precisa subir
SEM_VIDEO = {"diario", "busca", "texto", "rostos", "imagem", "fala"}


def log(*a):
    base.log("[runpod]", *a)


# ------------------------------------------------------------------------------------------------ API do RunPod
def _chave():
    if not os.path.exists(CHAVE):
        raise SystemExit(f"falta a chave do RunPod em {CHAVE} (RunPod → Settings → API Keys → Create; colar no arquivo e salvar)")
    k = open(CHAVE, encoding="utf-8-sig").read().strip()
    if not k: raise SystemExit(f"o arquivo {CHAVE} está vazio")
    return k


def api(metodo, rota, corpo=None, timeout=60):
    req = urllib.request.Request(API + rota, method=metodo, data=json.dumps(corpo).encode() if corpo is not None else None,
                                 headers={"Authorization": "Bearer " + _chave(), "Content-Type": "application/json",
                                          # 06/11: sem nome de programa o Cloudflare do RunPod recusa (HTTP 403, «error code: 1010»)
                                          "User-Agent": "tandera-runpod/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            txt = r.read().decode("utf-8", "replace")
            return json.loads(txt) if txt.strip() else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"RunPod {metodo} {rota}: HTTP {e.code} — {e.read().decode('utf-8', 'replace')[:400]}")


def _estado(**kw):
    os.makedirs(TRABALHO, exist_ok=True)
    e = json.load(open(ESTADO, encoding="utf-8")) if os.path.exists(ESTADO) else {}
    if kw:
        e.update(kw); base.salvar_json(ESTADO, e)
    return e


def _pod(nome, volume, centro, gpus, disco=250):   # 07/11: 80 GB encheu (modelos 48 + ambientes ~30); as do Flynder usavam 300
    pub = open(SSH_CHAVE + ".pub", encoding="utf-8").read().strip()
    corpo = {"name": nome[:60], "imageName": IMAGEM, "gpuTypeIds": list(gpus), "gpuTypePriority": "custom", "gpuCount": 1,
             "cloudType": "SECURE", "containerDiskInGb": disco, "networkVolumeId": volume, "volumeMountPath": "/workspace",
             "dataCenterIds": [centro], "ports": ["22/tcp"], "env": {"PUBLIC_KEY": pub, "SSH_PUBLIC_KEY": pub},
             "interruptible": False}
    # 06/11 ~19h: com "allowedCudaVersions" o RunPod respondia «no instances available» em TODO centro, até onde havia placa livre
    # (EU-RO-1 com PRO 4500: com o filtro 500, sem o filtro ligou na hora). O driver agora é conferido depois que a placa sobe (driver_ok)
    return api("POST", "/pods", corpo)


def driver_ok(alvo, pid):
    """o torch do motor é cu128: o driver da placa tem que aceitar CUDA 12.8+ (as Blackwell sempre aceitam)"""
    r = ssh(alvo, "nvidia-smi | grep -o 'CUDA Version: [0-9.]*'", checar=False, timeout=60)
    try: v = tuple(int(x) for x in r.stdout.split(":")[-1].strip().split(".")[:2])
    except ValueError: v = (0, 0)
    log(f"placa {pid}: driver CUDA {'.'.join(map(str, v))}")
    if v < (12, 8): raise RuntimeError(f"a placa {pid} tem driver CUDA {v} (o motor precisa 12.8+)")


def _estoque():
    """centro → {placa: estoque} (só centros com disco de rede), pela API GraphQL do RunPod"""
    try:
        req = urllib.request.Request("https://api.runpod.io/graphql", method="POST", data=json.dumps({"query":
              "query { dataCenters { id storageSupport gpuAvailability { gpuTypeId stockStatus } } }"}).encode(),
              headers={"Authorization": "Bearer " + _chave(), "Content-Type": "application/json", "User-Agent": "tandera-runpod/1.0"})
        d = json.loads(urllib.request.urlopen(req, timeout=60).read())
        return {c["id"]: {g["gpuTypeId"]: g.get("stockStatus") for g in (c.get("gpuAvailability") or []) if g.get("stockStatus")}
                for c in d["data"]["dataCenters"] if c.get("storageSupport")}
    except Exception as e:
        log(f"estoque: não li ({str(e)[:120]}); vou centro por centro"); return {}


def ligar_primeira(nome, gb, gpus):
    """o disco de rede + a 1ª placa no mesmo centro. 06/11 (ele: «tem que pegar aquela placa boa, a RTX 4500»): PLACA PRIMEIRO —
    para cada placa da lista, na ordem, os centros que têm estoque dela; só passa pra próxima placa se nenhum centro der a anterior
    (antes era centro primeiro e saiu uma L40S no Texas). Sem vaga, apaga o disco e tenta o próximo. Devolve também a placa escolhida."""
    est = _estoque()
    for gpu in gpus:
        centros = [c for c in est if est[c].get(gpu) not in (None, "None")] if est else CENTROS
        centros.sort(key=lambda c: {"High": 0, "Medium": 1, "Low": 2}.get(est.get(c, {}).get(gpu), 3))
        for c in centros:
            try:
                v = api("POST", "/networkvolumes", {"name": nome[:60], "size": gb, "dataCenterId": c})
            except RuntimeError as e:
                log(f"{c}: sem disco ({str(e)[:120]})"); continue
            _estado(volume=v["id"], centro=c, pods=[])
            try:
                p = _pod(nome + "-1", v["id"], c, [gpu])
                _estado(pods=[p["id"]], gpu=gpu)
                log(f"{c}: disco {gb} GB + placa {p.get('id')} {gpu} ({p.get('costPerHr')} US$/h)")
                return v["id"], c, p, gpu
            except RuntimeError as e:
                log(f"{c}: sem {gpu} ({str(e)[:120]}) — apago o disco e tento outro centro")
                api("DELETE", f"/networkvolumes/{v['id']}"); _estado(volume=None)
        log(f"nenhum centro deu {gpu}; próxima placa da lista")
    raise SystemExit("nenhum centro com disco + placa agora (tentar de novo em alguns minutos)")


def ligar_no_fixo(nome, gpus):
    """a 1ª placa no disco fixo (só dá no centro dele, EU-RO-1). Sem vaga em nenhuma placa da lista = None (o lote vai pro jeito antigo)"""
    for gpu in gpus:
        try:
            p = _pod(nome + "-1", FIXO["id"], FIXO["centro"], [gpu])
        except RuntimeError as e:
            log(f"{FIXO['centro']} (disco fixo): sem {gpu} ({str(e)[:100]})"); continue
        _estado(volume=FIXO["id"], centro=FIXO["centro"], pods=[p["id"]], gpu=gpu, fixo=True)
        log(f"{FIXO['centro']}: disco FIXO + placa {p.get('id')} {gpu} ({p.get('costPerHr')} US$/h)")
        return FIXO["id"], FIXO["centro"], p, gpu
    return None


def ligar_mais(nome, volume, centro, gpus, n):
    ids = []
    for k in range(n):
        try:
            p = _pod(f"{nome}-{k + 2}", volume, centro, gpus); ids.append(p["id"])
            log(f"placa extra {p['id']} ({p.get('costPerHr')} US$/h)")
        except RuntimeError as e:
            log(f"placa extra {k + 2}: sem vaga em {centro} ({str(e)[:120]}) — segue com as que tem"); break
    _estado(pods=_estado().get("pods", []) + ids)
    return ids


def esperar_ssh(pid, minutos=20):
    t0 = time.time()
    while time.time() - t0 < minutos * 60:
        p = api("GET", f"/pods/{pid}")
        ip, porta = p.get("publicIp"), (p.get("portMappings") or {}).get("22")
        if ip and porta and ssh((ip, int(porta)), "echo ok", checar=False, timeout=30).returncode == 0:
            log(f"placa {pid} no ar: {ip}:{porta} ({int(time.time() - t0)} s)")
            return ip, int(porta)
        time.sleep(10)
    raise RuntimeError(f"a placa {pid} não abriu o SSH em {minutos} min")


def desligar_tudo():
    e = _estado()
    for pid in e.get("pods") or []:
        try: api("DELETE", f"/pods/{pid}"); log(f"placa {pid} apagada")
        except RuntimeError as x: log(f"placa {pid}: {str(x)[:120]}")
    if e.get("volume") and (e.get("fixo") or (FIXO and e.get("volume") == FIXO["id"])):
        log(f"disco {e['volume']} é o FIXO: fica (só as placas saem)")
    elif e.get("volume"):
        for _ in range(12):                                # o disco só apaga depois que nenhuma placa o usa
            try:
                api("DELETE", f"/networkvolumes/{e['volume']}"); log(f"disco {e['volume']} apagado"); break
            except RuntimeError as x:
                if "404" in str(x): break
                time.sleep(10)
    _estado(pods=[], volume=None, fixo=False, desligado=time.strftime("%Y-%m-%d %H:%M:%S"))


# ------------------------------------------------------------------------------------------------ SSH
def _exe(n):
    return shutil.which(n) or os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "OpenSSH", n + ".exe")


_OPTS = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=" + os.devnull, "-o", "ServerAliveInterval=30",
         "-o", "LogLevel=ERROR", "-o", "IdentitiesOnly=yes"]


def ssh(alvo, cmd, checar=True, timeout=None):
    r = subprocess.run([_exe("ssh"), "-i", SSH_CHAVE, "-p", str(alvo[1]), *_OPTS, f"root@{alvo[0]}", cmd], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=timeout, creationflags=base.SEM_JANELA)
    if checar and r.returncode != 0:
        raise RuntimeError(f"ssh falhou ({r.returncode}): {cmd[:120]}\n{r.stderr[-1500:]}\n{r.stdout[-1500:]}")
    return r


def _ssh_arg(alvo):
    """o --ssh do enviar.py/trazer.py (eles chamam o ssh do sistema com isto)"""
    return f"root@{alvo[0]} -p {alvo[1]} -i {SSH_CHAVE} -o UserKnownHostsFile={os.devnull} -o StrictHostKeyChecking=no"


def _py(script, *args, log_arq=None):
    cmd = [os.path.join(base.TANDERA, ".venv", "Scripts" if os.name == "nt" else "bin", "python.exe" if os.name == "nt" else "python"),
           os.path.join(SERV, script), *args]
    with open(log_arq, "a", encoding="utf-8") if log_arq else open(os.devnull, "w") as out:
        r = subprocess.run(cmd, stdout=out, stderr=subprocess.STDOUT, cwd=base.TANDERA, creationflags=base.SEM_JANELA,
                           env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    if r.returncode: raise RuntimeError(f"{script} falhou (código {r.returncode}): veja {log_arq}")


# ------------------------------------------------------------------------------------------------ o lote
def _itens(grupo=None, lista=None, pista=None, bateria=None):
    """[(caminho, pista, grupo, dur, pasta da análise no PC ou None)] — do checklist (grupo) ou de uma lista de arquivos"""
    C = json.load(open(CHECKLIST, encoding="utf-8"))
    por_caminho = {os.path.normcase(a["caminho"]): a for a in C["arquivos"]}
    if grupo:
        # 06/11: «duplicado de X» (a mesma assinatura em outra pasta) também fica: o SDS tem cada bruto em duas pastas e o lote
        # contava 340 vídeos / 453 GB em vez de 184 / ~250 GB
        its = [a for a in C["arquivos"] if a.get("grupo") == grupo and a.get("situacao") != "fora"
               and not str(a.get("situacao") or "").startswith("duplicado")]
    else:
        its = []
        for l in open(lista, encoding="utf-8-sig"):
            c = l.strip().strip('"')
            if not c or c.startswith("#"): continue
            a = por_caminho.get(os.path.normcase(c)) or {"caminho": c, "grupo": "0-avulso", "pista": pista}
            its.append(a)
    out = []
    for a in its:
        p = pista or a.get("pista") or C["grupos"].get(a.get("grupo"), {}).get("pista")
        if not p: raise SystemExit(f"sem pista pra {a['caminho']} (use --pista)")
        out.append((a["caminho"], p, a.get("grupo") or "0-avulso", a.get("duracao_s"), a.get("analise")))
    return out


def montar(nome, itens, bateria, teste=False):
    """o lote no formato do servidor\\montar_lote: só os vídeos que têm peça faltando, com a análise do PC junto"""
    sys.path.insert(0, SERV)
    import montar_lote
    from .armazem import Analise
    from .pistas import pecas_da
    L, n = [], 0
    for cam, pista, grupo, dur, analise in itens:
        quer = [p for p in pecas_da(pista, cam, bateria) if "servidor" in PECAS[p]["perfis"]]
        so_pc = [p for p in pecas_da(pista, cam, bateria) if "servidor" not in PECAS[p]["perfis"]]
        falta, feitas = quer, set()
        if analise and os.path.exists(os.path.join(analise, "analise.json")) and not teste:
            A = Analise(cam, analise)
            falta = [p for p in quer if A.precisa(p)[0]]
            feitas = {p for p in PECAS if not PECAS[p].get("ferramenta") and A.tem(p) and not A.precisa(p)[0]}
        if not falta: continue
        n += 1
        it = montar_lote.item(n, grupo, cam, dur, None, pecas=falta)
        it["pista"] = pista
        if so_pc: it["fica_pro_pc"] = so_pc
        if analise and not teste: it["analise_pc"] = analise
        roda = set(com_dependencias(falta)) - feitas            # o que a placa vai rodar de fato (o feito no PC vem guardado)
        if roda <= SEM_VIDEO and it.get("analise_pc"): it["sem_video"] = True
        L.append(it)
    return {"nome": nome, "criado": time.strftime("%Y-%m-%d %H:%M:%S"), "pecas_padrao": [], "itens": L, "fora": []}


def resumo(lote):
    its = lote["itens"]
    sobe = sum(i["bytes"] for i in its if not i.get("sem_video")) / 1e9
    vel = json.load(open(CHECKLIST, encoding="utf-8")).get("velocidade_s_por_s", {})
    maq = sum(sum(vel.get(p, 0.3) for p in i["pecas"] if PECAS[p]["onde"] != "nuvem") * i["dur"] for i in its) / 3600
    pecas = {}
    for i in its:
        for p in i["pecas"]: pecas[p] = pecas.get(p, 0) + 1
    return dict(videos=len(its), horas_video=round(sum(i["dur"] for i in its) / 3600, 2), sobe_gb=round(sobe, 1),
                sem_video=sum(1 for i in its if i.get("sem_video")), maquina_5070_h=round(maq, 1), pecas=pecas,
                fica_pro_pc=sorted({p for i in its for p in i.get("fica_pro_pc", [])}))


def _estado_fila(alvo, nome):
    r = ssh(alvo, f"source /root/ativar_tandera.sh && python /root/TANDERA/servidor/rodar_lote.py --lote {W}/lotes/{nome}.json --estado",
            checar=False, timeout=120)
    ult = (r.stdout.strip().splitlines() or [""])[-1]
    cont = {}
    for parte in ult.split("·"):
        if ":" in parte:
            k, v = parte.rsplit(":", 1)
            try: cont[k.strip()] = int(v)
            except ValueError: pass
    return cont, r.stdout


def preparar(alvo, pasta, nome_maquina):
    lg = os.path.join(pasta, f"preparar-{nome_maquina}.log")
    # 06/11: sessão ssh longa e calada ficou pendurada no 1º lote → o preparo roda SOLTO (nohup) e aqui só confiro, com conexões curtas
    ssh(alvo, f"rm -f /root/preparar.fim; nohup bash -c 'bash {W}/codigo/servidor/preparar_tandera.sh > /root/preparar.log 2>&1; "
              f"echo FIM > /root/preparar.fim' > /dev/null 2>&1 < /dev/null &", checar=False, timeout=120)
    t0 = time.time()
    while time.time() - t0 < 7200:
        time.sleep(30)
        try:
            if "FIM" in ssh(alvo, "cat /root/preparar.fim 2>/dev/null", checar=False, timeout=90).stdout: break
        except subprocess.TimeoutExpired:
            pass
    r = ssh(alvo, "cat /root/preparar.log", checar=False, timeout=300)
    open(lg, "w", encoding="utf-8").write(r.stdout)
    ruins = [l for l in r.stdout.splitlines() if l.startswith(("FALTA", "FALHOU"))]
    if "PRONTO" not in r.stdout or ruins:
        raise RuntimeError(f"a máquina {nome_maquina} não ficou pronta: {ruins[:6] or 'sem PRONTO'} (log: {lg})")
    log(f"máquina {nome_maquina} pronta")


def rodar(lote, pasta, placas=1, gpus=GPUS, manter=False, para=None, drive=""):
    nome = lote["nome"]
    lj = os.path.join(pasta, nome + ".json"); base.salvar_json(lj, lote)
    R = resumo(lote)
    gb = int(max(150, R["sobe_gb"] * 1.3 + 130))            # modelos guardados (~70 GB) + o que sobe + folga
    _estado(lote=nome, pasta=pasta, comecou=time.strftime("%Y-%m-%d %H:%M:%S"))
    alvos = {}; trazido = False
    # cabe no disco fixo? (vídeos que sobem + ~20 MB de análise por item + folga)
    precisa = R["sobe_gb"] + 0.02 * R["videos"] + 3
    no_fixo = bool(FIXO) and precisa <= FIXO_LIVRE_GB and not os.environ.get("TANDERA_SEM_FIXO")
    log(f"o lote precisa de ~{precisa:.0f} GB no disco: " + ("cabe no disco FIXO" if no_fixo else
        (f"não cabe no fixo (livre {FIXO_LIVRE_GB:.0f} GB) → disco do lote" if FIXO else "sem disco fixo configurado → disco do lote")))
    pesos = [] if no_fixo else ["--pesos"]                  # no fixo os pesos já moram lá
    try:
        if drive:   # 07/11: código + pesos + análises sobem pro Drive num pacote ANTES da placa ligar (a placa não espera o PC)
            log("montando o pacote (código, pesos, análises) e subindo pro Drive, com a placa ainda desligada…")
            _py("enviar.py", "--so-pacote", "--codigo", *pesos, "--lote", lj, log_arq=os.path.join(pasta, "pacote.log"))
        r1 = ligar_no_fixo("tandera-" + nome, gpus) if no_fixo else None
        if no_fixo and not r1:
            log("nenhuma placa livre no centro do disco fixo agora → disco do lote (com os pesos)"); no_fixo = False; pesos = ["--pesos"]
            if drive: _py("enviar.py", "--so-pacote", "--codigo", *pesos, "--lote", lj, log_arq=os.path.join(pasta, "pacote.log"))
        vol, centro, p1, gpu1 = r1 or ligar_primeira("tandera-" + nome, gb, gpus)
        alvos[p1["id"]] = esperar_ssh(p1["id"]); driver_ok(alvos[p1["id"]], p1["id"])
        a1 = alvos[p1["id"]]
        hf = os.path.expanduser(os.path.join("~", ".cache", "huggingface", "token"))
        if os.path.exists(hf):                       # a chave do Hugging Face dele (modelo com termo aceito baixa igual ao PC)
            ssh(a1, f"mkdir -p /workspace/hf"); subprocess.run([_exe("scp"), "-i", SSH_CHAVE, "-P", str(a1[1]), *_OPTS, hf,
                                                                f"root@{a1[0]}:/workspace/hf/token"], capture_output=True, creationflags=base.SEM_JANELA)
        log(f"subindo código + pesos + lote ({R['sobe_gb']} GB de vídeo, {R['sem_video']} vídeos só com a análise)…")
        _py("enviar.py", "--ssh", _ssh_arg(a1), "--destino", W, "--codigo", *pesos, "--lote", lj, *(["--drive", drive] if drive else []),
            log_arq=os.path.join(pasta, "enviar.log"))
        preparar(a1, pasta, "1")
        extras = ligar_mais("tandera-" + nome, vol, centro, [gpu1], max(0, placas - 1)) if placas > 1 else []
        for pid in extras:
            try:
                alvos[pid] = esperar_ssh(pid); driver_ok(alvos[pid], pid); preparar(alvos[pid], pasta, pid[:6])
            except RuntimeError as e:
                log(f"placa extra {pid} fora: {e}"); api("DELETE", f"/pods/{pid}"); alvos.pop(pid, None)
        for pid, a in alvos.items():
            ssh(a, f"source /root/ativar_tandera.sh && cd /root && nohup python /root/TANDERA/servidor/rodar_lote.py "
                   f"--lote {W}/lotes/{nome}.json > /root/rodar_lote.log 2>&1 < /dev/null &", checar=False, timeout=120)
            # 07/11: sem o «< /dev/null» o ssh ficava preso até o lote ACABAR (81 min calado, sem vigiar a fila): agora solta na hora
        log(f"rodando em {len(alvos)} placa(s)…")
        while True:
            time.sleep(90)
            cont, txt = _estado_fila(a1, nome)
            open(os.path.join(pasta, "fila.txt"), "w", encoding="utf-8").write(txt)
            vivas = [pid for pid, a in alvos.items() if "VIVO" in ssh(a, "pgrep -f rodar_lote.py >/dev/null && echo VIVO || echo PAROU",
                                                                            checar=False, timeout=60).stdout]
            _estado(fila=cont, vivas=len(vivas))
            log(" · ".join(f"{k} {v}" for k, v in cont.items()) + f" · placas trabalhando {len(vivas)}")
            if not vivas or (cont and not cont.get("na fila") and not any(k.startswith("rodando") for k in cont)):
                break
        log("trazendo o relatório (sem os áudios grandes)…")
        _py("trazer.py", "--ssh", _ssh_arg(a1), "--storage", W, "--sem-audio", *(["--para", para] if para else []),
            log_arq=os.path.join(pasta, "trazer.log"))
        log("trazido"); trazido = True
    finally:
        if no_fixo and trazido and not manter and alvos:       # o disco fixo guarda só os motores: o que foi do lote sai
            try:
                ssh(next(iter(alvos.values())), f"rm -rf {W}/entrada {W}/analises {W}/fila; df -h /workspace | tail -1", checar=False, timeout=600)
                log("disco fixo limpo (entrada/, analises/, fila/ do lote); motores ficaram")
            except Exception as x:
                log(f"não limpei o disco fixo: {x}")
        elif no_fixo and not trazido:
            log("ATENÇÃO: o lote não foi trazido — entrada/ e analises/ ficaram no disco fixo (trazer.py antes de limpar)")
        if manter: log("--manter: placas e disco ficaram LIGADOS (`tandera runpod --desligar`)")
        else: desligar_tudo()


# ------------------------------------------------------------------------------------------------ a prova (servidor × PC)
def _numeros(x, out, lim=20000):
    if len(out) >= lim: return out
    if isinstance(x, bool) or x is None: return out
    if isinstance(x, (int, float)): out.append(float(x))
    elif isinstance(x, dict):
        for k in sorted(x):
            if k not in ("quando", "s", "segundos", "medida", "maquina", "arquivo", "caminho", "video", "uso_tokens"): _numeros(x[k], out, lim)
    elif isinstance(x, (list, tuple)):
        for v in x: _numeros(v, out, lim)
    return out


def comparar(pc, srv):
    """peça por peça: quantos números batem (tolerância 1% ou 0,05) entre a análise do PC e a do servidor do MESMO vídeo"""
    out = {}
    for f in sorted(os.listdir(os.path.join(srv, "pecas"))):
        if not f.endswith(".json"): continue
        a, b = os.path.join(pc, "pecas", f), os.path.join(srv, "pecas", f)
        p = f[:-5]
        if not os.path.exists(a): out[p] = "só no servidor (o PC nunca fez: conferir à mão)"; continue
        na, nb = _numeros(json.load(open(a, encoding="utf-8")), []), _numeros(json.load(open(b, encoding="utf-8")), [])
        if not na and not nb: out[p] = "sem números (texto)"; continue
        n = min(len(na), len(nb))
        ok = sum(1 for x, y in zip(na[:n], nb[:n]) if abs(x - y) <= max(0.05, 0.01 * max(abs(x), abs(y))))
        out[p] = f"{ok}/{n} números iguais ({100 * ok / max(1, n):.0f}%) · tamanho PC {len(na)} × servidor {len(nb)}"
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tandera runpod")
    ap.add_argument("--grupo"); ap.add_argument("--lista"); ap.add_argument("--pista"); ap.add_argument("--bateria", default="")
    ap.add_argument("--placas", type=int, default=1); ap.add_argument("--gpu", default="")
    # 06/11: vídeos já no Drive dele (trabalho\runpod\subir_drive.py) → a placa baixa de lá; padrão = drive-luan:TANDERA-ENTRADA
    ap.add_argument("--drive", default="drive-luan:TANDERA-ENTRADA"); ap.add_argument("--sem-drive", action="store_true")
    ap.add_argument("--teste", help="um vídeo curto: o servidor faz tudo do zero e compara com o PC")
    ap.add_argument("--manter", action="store_true"); ap.add_argument("--so-contar", action="store_true"); ap.add_argument("--desligar", action="store_true")
    x = ap.parse_args(argv)
    if x.desligar: return desligar_tudo()
    gpus = [g.strip() for g in x.gpu.split(",") if g.strip()] or GPUS
    if x.teste:
        lst = os.path.join(TRABALHO, "_teste.txt"); os.makedirs(TRABALHO, exist_ok=True); open(lst, "w", encoding="utf-8").write(x.teste)
        itens = _itens(lista=lst, pista=x.pista)
    elif x.grupo or x.lista:
        itens = _itens(x.grupo, x.lista, x.pista)
    else:
        ap.error("diga o quê: --grupo G, --lista arquivo.txt ou --teste vídeo")
    nome = ("teste" if x.teste else (x.grupo or os.path.splitext(os.path.basename(x.lista))[0])) + "-" + time.strftime("%Y%m%d-%H%M")
    pasta = os.path.join(TRABALHO, nome); os.makedirs(pasta, exist_ok=True)
    lote = montar(nome, itens, x.bateria or None, teste=bool(x.teste))
    R = resumo(lote); base.salvar_json(os.path.join(pasta, "resumo.json"), R)
    log(f"lote {nome}: {R['videos']} vídeos · {R['horas_video']} h · sobe {R['sobe_gb']} GB de vídeo ({R['sem_video']} sem vídeo) · "
        f"~{R['maquina_5070_h']} h de máquina na 5070 · peças {R['pecas']}" + (f" · SÓ NO PC: {R['fica_pro_pc']}" if R["fica_pro_pc"] else ""))
    if x.so_contar or not lote["itens"]: return
    if x.teste:
        dest = os.path.join(pasta, "volta")
        rodar(lote, pasta, 1, gpus, x.manter, para=dest)
        pc = itens[0][4]
        res = comparar(pc, os.path.join(dest, lote["itens"][0]["pasta"])) if pc else {"aviso": "o PC não tem análise desse vídeo"}
        base.salvar_json(os.path.join(pasta, "comparacao.json"), res)
        for k, v in res.items(): log(f"  {k}: {v}")
        return
    rodar(lote, pasta, x.placas, gpus, x.manter, drive="" if x.sem_drive else x.drive)
    from .checklist import main as ck_main
    ck_main([])
