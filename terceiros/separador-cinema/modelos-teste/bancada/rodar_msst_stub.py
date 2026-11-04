# Roda o msst/inference.py com STUBS das bibliotecas que o codigo do BandIt (Plus)
# importa so pra TREINO (asteroid, spafe, pedalboard, torch_audiomentations...).
# Nao instala nada na venv e nao mexe no repo: os stubs vivem so neste processo.
import sys, types, runpy
from unittest.mock import MagicMock
from pathlib import Path

FALTANDO = ["asteroid", "asteroid.losses", "asteroid.losses.sdr",
            "spafe", "spafe.fbanks", "spafe.fbanks.bark_fbanks", "spafe.utils", "spafe.utils.converters",
            "pedalboard", "torch_audiomentations", "audiomentations"]
for nome in FALTANDO:
    try:
        __import__(nome)
    except Exception:
        sys.modules[nome] = MagicMock(name=nome)

# 04/11 (porte do Mac, Gu): o MPS da Apple nao tem float64 e o BandIt guarda buffers em float64; indo pro MPS, o modelo vira float32
# antes (musica 57 dB x processador). Na NVIDIA e no processador nada muda.
import torch
_to = torch.nn.Module.to
def _to_mps(self, *a, **k):
    if str(a[0] if a else k.get("device")).startswith("mps"):
        self.float()
    return _to(self, *a, **k)
torch.nn.Module.to = _to_mps

msst = Path(__file__).resolve().parents[2] / "msst"
sys.path.insert(0, str(msst))
sys.argv = [str(msst / "inference.py")] + sys.argv[1:]
runpy.run_path(str(msst / "inference.py"), run_name="__main__")
