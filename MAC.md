# TANDERA no Mac — em porte

**Estado (03/11/2026):** o Tandera roda no Windows (placa NVIDIA) e no Linux (o perfil `servidor`, ver `RUNPOD.md`). No Mac o caminho
é: começar TUDO no processador (`--sem-placa`, já funciona), provar com o `exemplo/` (IGUAL/PERTO), e ligar a placa da Apple (MPS)
peça por peça, comparando. As peças pesadas vão pro RunPod. O porte está com o Gu (Fly); quando rodar, entra AQUI, como um 3º perfil
no mesmo código (nunca um Tandera paralelo).

**03/11:** no Mac do Gu já roda a peça **«fala»** (Whisper large-v3-turbo int8 no processador, o código SEM mudança) — é o que o
Kakashi do Mac usa. Cortes, separação, Ovis, olho/Gemma, diário, o perfil `mac` e o MPS: ainda não.

**Como ler:** **[CÓDIGO]** = conferido no código · **[SABIDO]** = documentação pública, NÃO testada num Mac · **[TESTAR]** = hipótese.

## O mapa, peça por peça
| o quê | onde (Windows/CUDA) | o caminho no Mac | dificuldade | 1ª versão? |
|---|---|---|---|---|
| caminhos e perfil | `tandera/base.py`: `if os.name == "nt"` (Windows, tudo por `TANDERA_*` no pacote) / senão = Linux (`/root/...`). **No Mac o código cai no ramo do Linux** (`os.name == "posix"`) e no **perfil "pc"** (`platform.system() == "Darwin"`) [CÓDIGO] | criar o 3º ramo (`sys.platform == "darwin"`) com padrões na pasta que o Gu escolher e o perfil `mac` no `manifesto.py` (quais peças rodam no Mac) | baixa | sim |
| a placa | 12 peças (16 lugares) escolhem `"cuda" if ... else "cpu"`; a separação esconde a placa com `CUDA_VISIBLE_DEVICES` e o BandIt com `--force_cpu`; `torch.cuda.empty_cache()`; `torch.autocast("cuda")` na câmera; `set_per_process_memory_fraction` no corpo; a medida da placa é NVML (só NVIDIA) [CÓDIGO] | um `base.DISPOSITIVO` ("cuda" / "mps" / "cpu"); no Mac começar TUDO no processador (`--sem-placa`, já funciona [CÓDIGO]) e ligar o MPS peça por peça, comparando com o `exemplo/comparar.py` [TESTAR]; sem NVML a medida da placa fica vazia (ok) [CÓDIGO] | média | processador primeiro |
| onnxruntime | `onnxruntime-gpu` + `preload_dlls()` (DLLs do CUDA no Windows); o `ort_sessao` já cai no processador com aviso [CÓDIGO] | `onnxruntime` comum; `CoreMLExecutionProvider` pra AutoShot/SCRFD [TESTAR] | baixa | processador |
| fala (Whisper) | faster-whisper (CTranslate2), fp16 na placa ou int8 no processador [CÓDIGO] | **só processador** (int8): o CTranslate2 não usa a placa da Apple [SABIDO]. Trocar por outro Whisper (ex.: MLX) seria OUTRO motor: só pela regra (medir contra o atual, subir a versão, o Luan decide) | — | sim |
| Ovis 8 bits, busca 4 bits | `bitsandbytes` (só CUDA) [CÓDIGO] | bf16 no MPS (Ovis ~7 GB, Qwen3-8B 16 GB) [TESTAR] — ou RunPod | alta | RunPod |
| texto (PaddleOCR) | `paddlepaddle-gpu` em ambiente separado (`.venv-ocr`); `_ocr_placa.py` já aceita `cpu` [CÓDIGO] | `paddlepaddle` de processador pro Mac [TESTAR] | média | depois |
| separação | `audio-separator` (BS-Roformer) e o msst do BandIt (`--force_cpu` existe) [CÓDIGO] | processador/MPS [TESTAR]; é lenta: candidata ao RunPod; com stems prontos não roda | média | stems ou RunPod |
| boca (OpenFace) | só pelo WSL do Windows (`wsl -d Ubuntu-24.04`) [CÓDIGO] | — | — | fora |
| corpo, efeitos, busca, rostos | pesados ou dependem de coisa de fora (biblioteca de efeitos, repositórios) | — | — | fora |
| olho (Gemma 4) | Ollama em `localhost:11434` [CÓDIGO] | o Ollama do Mac usa a placa da Apple [SABIDO]; `ollama pull gemma4:12b` (~8 GB, com o "pode") | baixa | depois |
| Premiere aberto | `premiere_aberto()` usa o `tasklist` do Windows; **no Mac sempre diz "fechado"** [CÓDIGO] | `pgrep -f "Adobe Premiere Pro"` [TESTAR] (no Mac a memória é dividida: pesar antes de usar a placa com o Premiere aberto) | baixa | sim |
| Medidor, `GPU_EM_USO` | apps do PC dele: vazio no pacote, desligado no Linux [CÓDIGO] | nada | — | — |
| fonte do carimbo do olho | `TANDERA_FONTE` (Windows: Arial Bold; Linux: Liberation) [CÓDIGO] | `/System/Library/Fonts/Supplemental/Arial Bold.ttf` [SABIDO] | baixa | com o olho |
| entrada de comando | `tandera.cmd` (Windows) [CÓDIGO] | `python -m tandera ...` de dentro da pasta (ou um alias) | baixa | sim |
| ambiente | `ambiente/requisitos.txt` + `travar.txt` (torch `+cu128`, `onnxruntime-gpu`, `bitsandbytes`, `nvidia-ml-py`) e as versões exatas em `servidor/requisitos/tandera.txt` [CÓDIGO] | as mesmas versões SEM o que é CUDA (torch comum do Mac, `onnxruntime`); Python 3.12 [TESTAR] | média | sim |
| montar/mandar/trazer o lote (do Mac) | `servidor/montar_lote.py` é Python comum; `enviar.py`/`trazer.py` usam `ssh` e `tar` e, no pacote, já partem o `--ssh` do jeito do Mac (`shlex` posix fora do Windows) sem mudar nada no Windows; o `find -printf`/`stat --printf` que eles usam rodam NO SERVIDOR (Linux) [CÓDIGO] | `ssh` e `tar` vêm no macOS [SABIDO]; testar contra um pod [TESTAR] | baixa | quando for usar o RunPod |
