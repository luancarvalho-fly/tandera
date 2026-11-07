#!/bin/bash
# PANELAS DE SOM (01/11/2026): prepara uma máquina Linux (RunPod, RTX PRO 4500; ou o WSL na prova) pra rodar o TANDERA — as peças de som
# (preparo, cortes, separação, fala, batida, música, rótulos, sinal) + texto, ovis e olho. O MESMO jeito do Flynder
# (fly-brutos-teste\servidor_teste\preparar_storage.sh):
#   - PROGRAMAS (ambientes Python, ffmpeg, Ollama) são instalados no disco da máquina a cada máquina nova;
#   - MODELOS são baixados UMA vez pro storage (/workspace) e, em cada máquina, COPIADOS pro disco local (ler modelo do storage em
#     pedaços é lento, e o storage Global não guarda os atalhos do cache do Hugging Face: por isso cada pasta de modelos vai pro storage
#     como UM .tar, que preserva os atalhos e se lê de uma vez);
#   - a chave do Hugging Face, SE você guardou a sua no storage (/workspace/hf/token, ou TANDERA_CHAVE_HF); sem ela baixa mais devagar.
# Ambientes SEPARADOS porque as bibliotecas brigam (versões EXATAS do PC, servidor/requisitos/*.txt, tiradas por travas_do_pc.py):
#   /root/venv_tandera (o Tandera)  ·  /root/venv_sep (BS-Roformer)  ·  /root/venv_cine (BandIt, msst, Python 3.13)  ·  /root/venv_ocr (PaddleOCR)
# Uso:  bash /workspace/tandera/codigo/servidor/preparar_tandera.sh        (depois: source /root/ativar_tandera.sh)
# 07/11: um preparo por vez na máquina (o adiantado à mão e o do runpod.py esperam um ao outro; o segundo passa rápido: «já pronto»)
exec 9>/root/preparar.lock; flock 9
# Rodar de novo é seguro: o que já está pronto é pulado.
set -u
W=${TANDERA_STORAGE:-/workspace/tandera}           # o storage (no WSL da prova: uma pasta comum)
CODIGO=$W/codigo
REQ=$CODIGO/servidor/requisitos
P=/root/tandera_pesos; HFL=/root/hf_local; TH=/root/torch_home; PDX=/root/paddlex; OM=/root/ollama_modelos
export UV_CACHE_DIR=/root/uv-cache UV_LINK_MODE=hardlink UV_HTTP_TIMEOUT=300
export HF_HUB_DISABLE_XET=1 HF_HUB_CACHE=$HFL TORCH_HOME=$TH PADDLE_PDX_CACHE_HOME=$PDX OLLAMA_MODELS=$OM
CHAVE_HF=${TANDERA_CHAVE_HF:-/workspace/hf/token}
[ -s "$CHAVE_HF" ] && export HF_TOKEN="$(cat "$CHAVE_HF")" && echo "chave do Hugging Face: do storage"
LOG=/root/preparar_tandera.log
exec > >(tee -a $LOG) 2>&1
T0=$(date +%s)
marca() { echo "== $1 ($(( $(date +%s) - T0 )) s) $(date +%H:%M:%S)"; }
marca "início · storage $W"
mkdir -p $W/pesos $W/wheels $P $HFL $TH $PDX $OM

# ------------------------------------------------------------------ 1. programas do sistema (disco da máquina)
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq > /dev/null 2>&1
apt-get install -y -qq curl ca-certificates xz-utils zstd pciutils rsync fonts-liberation libgl1 libglib2.0-0 libsndfile1 > /dev/null 2>&1 \
  && echo "pacotes do sistema ok"
# ffmpeg 9.0 (o mesmo do PC: o preparo e os cortes leem o vídeo por ele). Estático da BtbN; sem rede pra ele, o do Ubuntu.
FF=/root/ffmpeg9/bin
if [ ! -x $FF/ffmpeg ]; then
  mkdir -p /root/ffmpeg9 && curl -sL --retry 3 "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n9.0-latest-linux64-gpl-9.0.tar.xz" \
    | tar -xJ -C /root/ffmpeg9 --strip-components=1 || { echo "AVISO: ffmpeg 9.0 não veio; usando o do sistema"; apt-get install -y -qq ffmpeg > /dev/null 2>&1; }
fi
[ -x $FF/ffmpeg ] && export PATH=$FF:$PATH
echo "ffmpeg: $(ffmpeg -version 2>/dev/null | head -1)"
command -v uv > /dev/null || { curl -LsSf https://astral.sh/uv/install.sh | sh > /dev/null 2>&1; }
export PATH=/root/.local/bin:$PATH
echo "uv: $(uv --version)"
marca "programas"

# ------------------------------------------------------------------ 2. os ambientes (versões EXATAS do PC)
PYV() { head -1 "$REQ/$1.txt" | awk '{print $3}'; }     # «# python 3.12.15 · …» → 3.12.15
TORCH_IDX=(--extra-index-url https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match)
amb() {   # amb <nome> <pasta> <teste>
  local nome=$1 dir=$2 teste=$3
  if [ -x $dir/bin/python ] && $dir/bin/python -c "$teste" > /dev/null 2>&1; then echo "ambiente $nome: já pronto"; return 0; fi
  # 06/11 (1ª placa do Luan): o chumpy 0.70 (regua) monta o pacote importando o pip — no isolamento do uv não tem pip e o ambiente
  # inteiro falhava. Os pacotes que precisam disso montam no próprio ambiente, com pip/setuptools/numpy já dentro
  local semiso=()
  if grep -qi '^chumpy==' "$REQ/$nome.txt"; then semiso=(--no-build-isolation-package chumpy); fi
  # 07/11: o regua do PC (WSL) roda com versões que brigam com as dependências declaradas (openface-test pede tqdm 4.66.2 e timm
  # 1.0.15; o PC tem 4.70.1 e 0.9.12 — o pip deixou passar). A lista É o ambiente inteiro do PC (pip freeze): instala exatamente ela,
  # sem o uv tentar resolver (--no-deps)
  if [ "$nome" = "regua" ]; then semiso+=(--no-deps); fi
  uv venv -q --python "$(PYV $nome)" $dir \
    && { [ ${#semiso[@]} -eq 0 ] || uv pip install -q --python $dir/bin/python pip wheel \
           "$(grep -i '^setuptools==' "$REQ/$nome.txt" || echo setuptools)" "$(grep -i '^numpy==' "$REQ/$nome.txt" || echo numpy)"; } \
    && uv pip install -q --python $dir/bin/python -r "$REQ/$nome.txt" "${TORCH_IDX[@]}" "${semiso[@]}" \
    && echo "ambiente $nome ok ($(PYV $nome))" || echo "FALHOU: ambiente $nome"
}
amb tandera /root/venv_tandera "import torch, faster_whisper, beat_this, transnetv2_pytorch, torchaudio, transformers"
# o faster-whisper puxa o «onnxruntime» só de processador, que sobrescreve o da placa (igual ao PC e ao Flynder): tira e põe o da placa
if /root/venv_tandera/bin/python -c "import onnxruntime as o; assert 'CUDAExecutionProvider' in o.get_available_providers()" 2>/dev/null; then :; else
  uv pip uninstall -q --python /root/venv_tandera/bin/python onnxruntime onnxruntime-gpu > /dev/null 2>&1
  uv pip install -q --python /root/venv_tandera/bin/python --reinstall --no-deps onnxruntime-gpu==1.23.2 && echo "onnxruntime da placa ok"
fi
# 07/11: o rodar_lote.py roda no python do SISTEMA e o preparo das fotos (HEIC do iPhone) é feito nele → sem o pillow-heif aqui, 166
# fotos falharam com «cannot identify image file»
python -c "import pillow_heif" 2>/dev/null || { python -m pip install -q pillow-heif==1.8.1 --break-system-packages > /dev/null 2>&1 && echo "pillow-heif do sistema ok"; }
python -c "import pillow_heif" 2>/dev/null || echo "FALTA: pillow-heif no python do sistema (fotos HEIC)"
amb sep /root/venv_sep "import audio_separator, torch"
# 06/11: o OpenFace 3.0 da peça boca (no PC ele mora no WSL, /opt/regua/.venv; aqui roda direto)
amb regua /root/venv_regua "import openface, torch"
amb cine /root/venv_cine "import torch, torchaudio, omegaconf, ml_collections, librosa"
# PaddleOCR: o paddlepaddle-gpu (~2 GB, servidor da Paddle) fica guardado no storage depois da 1ª vez (01/11 no Flynder: o download
# caiu no meio numa máquina). Mesma versão do PC (3.3.1).
if [ -x /root/venv_ocr/bin/python ] && /root/venv_ocr/bin/python -c "import paddleocr, paddle" > /dev/null 2>&1; then echo "ambiente ocr: já pronto"; else
  uv venv -q --python "$(PYV ocr)" /root/venv_ocr
  for t in 1 2 3; do
    ls $W/wheels/paddlepaddle_gpu-3.3.1-*.whl > /dev/null 2>&1 || \
      uvx -q pip download -q --no-deps -d $W/wheels "paddlepaddle-gpu==3.3.1" --python-version 3.12 --only-binary=:all: \
        -i https://www.paddlepaddle.org.cn/packages/stable/cu129/
    uv pip install -q --python /root/venv_ocr/bin/python $W/wheels/paddlepaddle_gpu-3.3.1-*.whl \
      && uv pip install -q --python /root/venv_ocr/bin/python -r "$REQ/ocr.txt" && echo "ambiente ocr ok" && break
    rm -f $W/wheels/paddlepaddle_gpu-*.whl; sleep 10
  done
fi
marca "ambientes"

# ------------------------------------------------------------------ 3. o código (cópia no disco: rodar de dentro do storage travava o ffmpeg no Flynder)
rm -rf /root/TANDERA && cp -r $CODIGO /root/TANDERA && echo "código: $(ls /root/TANDERA)"

# ------------------------------------------------------------------ 4. os modelos: storage (.tar, uma vez) → disco local (cada máquina)
# do_pc = o que só existe no PC (enviar.py --pesos): o AutoShot do CUTX, o BandIt Plus + o código do msst do separador-cinema
traz() {   # traz <nome> <pasta local> : extrai $W/pesos/<nome>.tar se existir; 0 = veio do storage
  [ -s $W/pesos/$1.tar ] || return 1
  tar -C $(dirname $2) -xf $W/pesos/$1.tar && echo "modelos «$1»: do storage pro disco ($(du -sh $2 | cut -f1))"
}
guarda() { tar -C $(dirname $2) -cf $W/pesos/$1.tar.parcial $(basename $2) && mv $W/pesos/$1.tar.parcial $W/pesos/$1.tar && echo "modelos «$1»: guardados no storage"; }
PYT=/root/venv_tandera/bin/python

if ! traz tandera_pesos $P; then
  [ -d $W/do_pc ] && cp -r $W/do_pc/. $P/ && echo "pesos do PC: $(ls $P)"
  [ -s $P/autoshot.onnx ] || echo "FALTA: autoshot.onnx (no PC: python servidor/enviar.py --pesos)"
  [ -s $P/separador-cinema/modelos-teste/bandit_plus/model_bandit_plus_dnr_sdr_11.47.chpt ] || echo "FALTA: BandIt Plus (enviar.py --pesos)"
  # BS-Roformer ep317: o audio-separator baixa (ou veio do PC em do_pc/audio-separator)
  [ -s $P/audio-separator/model_bs_roformer_ep_317_sdr_12.9755.ckpt ] || \
    /root/venv_sep/bin/audio-separator --download_model_only -m model_bs_roformer_ep_317_sdr_12.9755.ckpt --model_file_dir $P/audio-separator > /dev/null 2>&1
  # CED-Base (os rótulos): o mesmo repositório que está em dados\ia-som\ced-base no PC
  $PYT -c "from huggingface_hub import snapshot_download as s; s('mispeech/ced-base', local_dir='$P/ced-base')" > /dev/null 2>&1
  ls $P/audio-separator/*.ckpt $P/ced-base/model.safetensors > /dev/null 2>&1 && guarda tandera_pesos $P || echo "FALTA: Roformer ou CED (não guardei)"
fi
# 06/11: os pesos das peças de imagem que só existem no PC (rostos, corpo, câmera, boca, pose) chegam pelo enviar.py --pesos em do_pc/;
# cp -n = o que já está no disco fica (rodar de novo é seguro), o que é novo entra mesmo quando o tandera_pesos.tar veio do storage
[ -d $W/do_pc ] && cp -rn $W/do_pc/. $P/ && echo "pesos do PC (imagem): $(ls $P | tr '\n' ' ')"
for f in tandera_modelos/scrfd/det_10g.onnx tandera_modelos/adaface/adaface_ir101_webface12m.ckpt tandera_modelos/emotiefflib/enet_b0_8_best_vgaf.onnx \
         regua/modelos/sapiens2/pose/sapiens2_1b_pose.safetensors regua/modelos/cotracker3/scaled_offline.pth regua/modelos/openface3 \
         regua/repos/sapiens2 regua/repos/co-tracker pose_landmarker_heavy.task; do
  [ -e $P/$f ] || echo "FALTA: $f (no PC: python servidor/enviar.py --pesos)"
done
traz hf_local $HFL || true
# o que falta no cache (do storage ou não) baixa agora e o .tar do storage é refeito; tudo lá = nada muda.
# 01/11 (prova no WSL): o código do CED-Base, ao abrir, busca a lista das 527 etiquetas em OUTRO repositório (topel/ConvNeXt-Tiny-AT);
# no PC ela já estava no cache, no servidor (offline durante a análise) os rótulos falhavam
$PYT - <<'EOF' | tee /tmp/hf_novo.txt
from huggingface_hub import snapshot_download as s
for repo, pad in [("mobiuslabsgmbh/faster-whisper-large-v3-turbo", None),      # fala
                  ("ATH-MaaS/Ovis-Omni-Embedding-3B", ["model/*"]),             # ovis
                  ("topel/ConvNeXt-Tiny-AT", ["class_labels_indices.csv"]),     # as etiquetas que o CED-Base lê
                  ("google/siglip2-so400m-patch14-384", None),                  # imagem (06/11)
                  ("laion/larger_clap_general", None),                          # som (06/11)
                  ("Qwen/Qwen3-Embedding-8B", None)]:                           # busca (06/11)
    try:
        s(repo, allow_patterns=pad, local_files_only=True); print("ok (já no disco)", repo, flush=True)
    except Exception:
        try: s(repo, allow_patterns=pad); print("NOVO", repo, flush=True)
        except Exception as e: print("FALHOU", repo, type(e).__name__, str(e)[:200], flush=True)
EOF
grep -q NOVO /tmp/hf_novo.txt && guarda hf_local $HFL
if ! traz torch_home $TH; then
  # MMS_FA (as palavras no ms) e o Beat This! final0 (batida e música) baixam pelo torch.hub na 1ª vez
  $PYT -c "
from torchaudio.pipelines import MMS_FA as b; b.get_model(); print('ok MMS_FA')
from beat_this.inference import File2Beats; File2Beats(checkpoint_path='final0', device='cpu', dbn=False); print('ok beat_this final0')"
  guarda torch_home $TH
fi
if ! traz paddlex $PDX; then
  /root/venv_ocr/bin/python -c "
import os; os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')
from paddleocr import PaddleOCR
PaddleOCR(lang='pt', use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=True, device='cpu', enable_mkldnn=False)
print('ok PP-OCRv5 (pt)')" 2>&1 | tail -1
  guarda paddlex $PDX
fi
marca "modelos"

# ------------------------------------------------------------------ 5. Ollama (o olho: gemma4:12b)
command -v ollama > /dev/null || { curl -fsSL https://ollama.com/install.sh | sh > /dev/null 2>&1 && echo "ollama instalado"; }
# com systemd (o WSL da prova) o instalador sobe um serviço «ollama» que guarda os modelos em /usr/share/ollama: desliga — o Tandera usa
# o servidor dele, com os modelos no disco local ($OM). (No RunPod não há systemd: nada a fazer.) O que ele já baixou vem pro $OM.
if command -v systemctl > /dev/null && systemctl is-active -q ollama 2>/dev/null; then
  systemctl stop ollama; systemctl disable -q ollama 2>/dev/null
  [ -d /usr/share/ollama/.ollama/models/blobs ] && cp -rn /usr/share/ollama/.ollama/models/. $OM/ && echo "ollama: serviço do sistema desligado (modelos dele copiados pro $OM)"
fi
traz ollama $OM || true
if ! curl -s -m 2 localhost:11434/api/version > /dev/null; then
  OLLAMA_MODELS=$OM OLLAMA_KEEP_ALIVE=5m nohup ollama serve > /root/ollama.log 2>&1 &
  for i in $(seq 30); do curl -s -m 2 localhost:11434/api/version > /dev/null && break; sleep 1; done
fi
if ! OLLAMA_MODELS=$OM ollama list 2>/dev/null | grep -q "gemma4:12b"; then
  OLLAMA_MODELS=$OM ollama pull gemma4:12b > /dev/null 2>&1 && echo "gemma4:12b baixado"
fi
[ -s $W/pesos/ollama.tar ] || { ls $OM/blobs/* > /dev/null 2>&1 && guarda ollama $OM; }
echo "ollama: $(ollama --version 2>&1 | tail -1) · $(OLLAMA_MODELS=$OM ollama list 2>/dev/null | grep gemma4 | awk '{print $1, $3, $4}')"
marca "ollama"

# ------------------------------------------------------------------ 6. o ativar (as variáveis que o Tandera lê no Linux)
NUC=$(python3 -c "
try:
    q, p = open('/sys/fs/cgroup/cpu.max').read().split()[:2]; print(max(2, int(int(q) / int(p))) if q != 'max' else __import__('os').cpu_count())
except Exception: print(__import__('os').cpu_count())")
cat > /root/ativar_tandera.sh <<EOF
# gerado por preparar_tandera.sh — source /root/ativar_tandera.sh
export PATH=$FF:/root/.local/bin:\$PATH
export PYTHONPATH=/root/TANDERA TANDERA_PERFIL=servidor TANDERA_STORAGE=$W
export TANDERA_PY=/root/venv_tandera/bin/python TANDERA_PY_OCR=/root/venv_ocr/bin/python TANDERA_PY_CINE=/root/venv_cine/bin/python
export TANDERA_ROFO=/root/venv_sep/bin/audio-separator TANDERA_PESOS=$P TANDERA_ANALISES=\${TANDERA_ANALISES:-/root/analises}
export TANDERA_MODELOS=$P/tandera_modelos TANDERA_PY_REGUA=/root/venv_regua/bin/python
export HF_HUB_CACHE=$HFL HF_HUB_OFFLINE=1 HF_HUB_DISABLE_XET=1 TORCH_HOME=$TH PADDLE_PDX_CACHE_HOME=$PDX OLLAMA_MODELS=$OM
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True FORCE_QWENVL_VIDEO_READER=decord PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
# os núcleos que o aluguel DEIXA usar (01/11 no Flynder: a máquina mostrava 256, o RunPod libera 27; cada biblioteca abria 256 frentes)
export OMP_NUM_THREADS=$(( NUC < 8 ? NUC : 8 )) OPENBLAS_NUM_THREADS=$(( NUC < 8 ? NUC : 8 )) MKL_NUM_THREADS=$(( NUC < 8 ? NUC : 8 ))
EOF
source /root/ativar_tandera.sh

# ------------------------------------------------------------------ 7. conferência: cada panela abre?
cd /root/TANDERA
$TANDERA_PY -c "
import torch, onnxruntime as o, ctranslate2
print('placa:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NENHUMA', '· torch', torch.__version__,
      '· onnxruntime', o.get_available_providers()[0], '· ctranslate2 cuda', ctranslate2.get_cuda_device_count())"
$TANDERA_PY -m tandera versao | head -3
$TANDERA_ROFO --version 2>&1 | tail -1
$TANDERA_PY_CINE -c "import torch; print('cine: torch', torch.__version__, torch.cuda.is_available())"
$TANDERA_PY_OCR -c "import paddle; print('ocr: paddle', paddle.__version__, 'cuda', paddle.device.is_compiled_with_cuda())" 2>&1 | tail -1
$TANDERA_PY -c "import mediapipe, skimage, bitsandbytes; print('imagem: mediapipe', mediapipe.__version__, '· bitsandbytes', bitsandbytes.__version__)" 2>&1 | tail -1
$TANDERA_PY_REGUA -c "import openface, torch; print('boca: openface ok · torch', torch.__version__, torch.cuda.is_available())" 2>&1 | tail -1
du -sh $P $HFL $TH $PDX $OM 2>/dev/null | tr '\n' ' '; echo
marca "PRONTO"
