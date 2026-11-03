#!/usr/bin/env bash
# Tandera, peça «boca»: roda o OpenFace 3.0 no WSL numa pasta com ./weights (o código procura os pesos relativos à pasta atual)
# uso: bash _boca_openface.sh <lista.json (caminho /mnt/...)> <saida.json (/mnt/...)> <pasta das peças (/mnt/...)> <pesos do OpenFace (/mnt/...)>
# pacote da Fly: a pasta das peças e a dos pesos vêm do boca.py (no PC do Luan eram caminhos fixos dele); o Python do OpenFace no WSL: TANDERA_OPENFACE_PY
PY=${TANDERA_OPENFACE_PY:-/opt/regua/.venv/bin/python}
mkdir -p /tmp/ofw && cd /tmp/ofw && ln -sfn "$4" weights
"$PY" "$3/_boca_openface_wsl.py" "$1" "$2" /tmp/ofw/weights 2>&1 | grep -v -i warn | tail -4
