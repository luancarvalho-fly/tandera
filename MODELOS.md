# Os modelos do Tandera único: fonte, tamanho, licença, se vem no zip, se roda no Mac (02/11/2026)

**Peso de modelo NÃO vem no zip** (ele tem que ser leve): cada um se baixa da fonte oficial. A exceção é o que não tem fonte oficial:
só o `autoshot.onnx` (34,0 MB, conversão do Luan; ver a linha dele). Tamanho = o que está no disco do PC do Luan em 02/11 (medido).

Como ler a coluna «Mac»: **[CÓDIGO]** = conferido no código deste pacote · **[SABIDO]** = documentação pública do projeto, não testado
num Mac · **[TESTAR]** = hipótese, provar no Mac antes de contar com ela. Nada aqui rodou num Mac.

| peça | modelo | fonte oficial | tamanho | licença | no zip? | placa no PC do Luan | roda no Mac? |
|---|---|---|---|---|---|---|---|
| preparo | ffmpeg (sistema) | ffmpeg.org (o servidor usa o estático 9.0 da BtbN) | — | LGPL/GPL | não | — | sim: ffmpeg existe pro Mac [SABIDO] |
| cortes | **AutoShot** `autoshot.onnx` | código e artigo: github.com/wentaozhu/AutoShot. Não existe ONNX oficial: é a conversão do Luan (CUTX, 01/10) do `ckpt_0_200_0.pth` (57,2 MB) do espelho huggingface.co/backseollgi/AutoShot (o original fica no Baidu) | 34,0 MB | código MIT; o espelho do peso não declara licença (decisão do Luan: aceito como no CUTX) | **SIM** (sha256 no `SHA256SUMS.txt`) | ~0,6 GB | onnxruntime de processador sim [SABIDO]; CoreML (`CoreMLExecutionProvider`) [TESTAR] |
| cortes | **TransNetV2** (dentro do pip `transnetv2-pytorch` 1.0.5) | pypi.org/project/transnetv2-pytorch | 32,7 MB | MIT | não (vem com o pip) | (junto) | torch no processador sim; MPS [TESTAR] |
| separacao | **BS-Roformer** `model_bs_roformer_ep_317_sdr_12.9755.ckpt` (+ .yaml) | github.com/TRvlvr/model_repo (o repositório de modelos do UVR); quem baixa é o `audio-separator` 0.44.5 | 639 MB | não declarada pelo repositório | não | ~3,3 GB | o audio-separator roda no Mac (processador/MPS) [SABIDO]; velocidade [TESTAR] — ou no RunPod |
| separacao | **BandIt Plus** `model_bandit_plus_dnr_sdr_11.47.chpt` | github.com/ZFTurbo/Music-Source-Separation-Training, release v.1.0.3 (o código do msst vem em `terceiros/`, commit 2ba884c) | 148,9 MB | msst MIT · BandIt original (kwatcharasupat/bandit) Apache-2.0 | não (o código sim) | (junto) | torch; o `--force_cpu` existe [CÓDIGO]; MPS [TESTAR] |
| fala | **Whisper large-v3-turbo** (faster-whisper / CTranslate2) | huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo | 1,62 GB | MIT (o Whisper da OpenAI) | não | ~2,5 GB | só processador (int8): o CTranslate2 não usa a placa do Mac [SABIDO]; o Tandera já tem o caminho `dispositivo="cpu"` [CÓDIGO] |
| fala | **MMS_FA** (alinhamento por palavra, torchaudio) | dl.fbaipublicfiles.com/mms/torchaudio/ctc_alignment_mling_uroman/model.pt (Meta; baixa sozinho pelo torch.hub) | 1,26 GB | **CC BY-NC 4.0 (não comercial)** | não | (junto) | torch no processador sim; MPS [TESTAR] |
| entonacao | **Praat** (praat-parselmouth) | pypi.org/project/praat-parselmouth | — | GPL-3.0 | não | — | sim (tem pacote pro Mac) [SABIDO] |
| batida, musica | **Beat This!** `final0` | github.com/CPJKU/beat_this (o peso fica na nuvem da JKU; baixa sozinho pelo torch.hub — em 27/10 o servidor da JKU deu erro 500 três vezes) | 81,1 MB | MIT (código e pesos, diz o README) | não | ~0,8 GB | torch no processador sim; MPS [TESTAR] |
| musica | librosa | pypi | — | ISC | não | — | sim [SABIDO] |
| rotulos | **CED-Base** `mispeech/ced-base` (+ a lista de etiquetas de `topel/ConvNeXt-Tiny-AT`, que o código dele busca) | huggingface.co/mispeech/ced-base | 430 MB | Apache-2.0 (conferido no cartão) | não | ~0,6 GB | transformers no processador/MPS [TESTAR] |
| camera | **CoTracker3** `scaled_offline.pth` + o código `co-tracker` | peso: huggingface.co/facebook/cotracker3 · código: github.com/facebookresearch/co-tracker (commit 82e02e8, o do PC do Luan) — o código NÃO vem: `git clone` nesse commit em `$TANDERA_REGUA/repos/co-tracker` | 102 MB | **CC BY-NC 4.0 (não comercial)** (conferido no cartão) | não | ~2,0 GB | o `autocast` é só "cuda" [CÓDIGO]; no Mac processador/MPS [TESTAR] |
| corpo | **Sapiens2-1B** pose + detector DETR-R101 | huggingface.co/facebook/sapiens2-pose-1b + facebook/detr-resnet-101-dc5 · código github.com/facebookresearch/sapiens2 (commit 7e5bae8) | 6,57 GB | Sapiens2: licença própria da Meta · DETR Apache-2.0 | não | ~5,5 GB | pesado: deixar fora no Mac (PC/RunPod) |
| pisada | **MediaPipe Pose Landmarker heavy** | storage.googleapis.com/mediapipe-models (pose_landmarker_heavy.task) | 31 MB | Apache-2.0 | não | processador | sim (mediapipe tem pacote pro Mac) [SABIDO] |
| rostos | **SCRFD 10G** `det_10g.onnx` (do pacote buffalo_l do insightface) | github.com/deepinsight/insightface (modelos pré-treinados) | 16,9 MB | os modelos do insightface: só pesquisa / não comercial | não | ~1,5 GB | onnxruntime processador sim [SABIDO] |
| rostos | **AdaFace IR-101 WebFace12M** `adaface_ir101_webface12m.ckpt` (+ `net.py`, que VEM em `modelos/adaface/`) | github.com/mk-minchul/AdaFace | 1,53 GB | código MIT; o peso foi treinado no WebFace (termos de pesquisa) | só o `net.py` | (junto) | torch processador/MPS [TESTAR] |
| rostos | **EmotiEffLib** `enet_b0_8_best_vgaf.onnx` | github.com/av-savchenko/EmotiEffLib | 16,0 MB | Apache-2.0 (código) | não | (junto) | onnxruntime processador sim [SABIDO] |
| boca | **OpenFace 3.0** (Alignment_RetinaFace, Landmark_98...) | github.com/CMU-MultiComp-Lab/OpenFace-3.0 | 462 MB | conferir no repositório | não | ~1,0 GB | no PC do Luan roda pelo WSL (Linux) [CÓDIGO]: fora na 1ª versão do Mac |
| texto | **PaddleOCR 3.7** (PP-OCRv5, `lang=pt`) + paddlepaddle 3.3 | github.com/PaddlePaddle/PaddleOCR (baixa sozinho no 1º uso) | ~0,15 GB | Apache-2.0 | não | ~1,5 GB | paddlepaddle de processador pro Mac [TESTAR] (o `_ocr_placa.py` já aceita `cpu`) [CÓDIGO] |
| imagem | **SigLIP 2** `google/siglip2-so400m-patch14-384` | huggingface.co/google/siglip2-so400m-patch14-384 | 4,58 GB (cache) | Apache-2.0 | não | ~2,0 GB | transformers processador/MPS [TESTAR] |
| som | **CLAP** `laion/larger_clap_general` | huggingface.co/laion/larger_clap_general | 1,56 GB | Apache-2.0 (conferido no cartão) | não | ~1,2 GB | transformers processador/MPS [TESTAR] |
| ovis | **Ovis-Omni-Embedding-3B** `ATH-MaaS/Ovis-Omni-Embedding-3B` (base Qwen2.5-Omni-3B) | huggingface.co/ATH-MaaS/Ovis-Omni-Embedding-3B (só `model/*`) | ~11 GB (cache) | Apache-2.0 (conferido no cartão) | não | 5,9 GB (8 bits) | o 8 bits usa bitsandbytes (só CUDA) [CÓDIGO]; no Mac só bf16 (MPS) [TESTAR] — candidato a ir pro RunPod |
| diario | **Gemini Flash** (nuvem) | API do Google (`generativelanguage.googleapis.com`) | — | termos do Google; **chave de quem usa** (`GEMINI_API_KEY` ou `~/.gemini/chave-api.txt`), nunca no pacote | — | — | sim (é rede) [CÓDIGO] |
| busca | **Qwen3-Embedding-8B** (4 bits na placa) + BM25 | huggingface.co/Qwen/Qwen3-Embedding-8B | 15,15 GB (cache) | Apache-2.0 (conferido no cartão) | não | ~6,0 GB | 4 bits = bitsandbytes (só CUDA) [CÓDIGO]; bf16 = 16 GB: RunPod |
| olho | **Gemma 4 12B** no Ollama (`gemma4:12b`) | ollama.com/library/gemma4 | ~7,5–8 GB | Apache-2.0 (conferido em 27/10) | não | ~8 GB | o Ollama do Mac usa a placa da Apple (Metal) [SABIDO]; velocidade [TESTAR] |
| efeitos | encaixe na onda contra uma BIBLIOTECA de efeitos indexada (`lista.txt` + `bib8k.npy`) | a biblioteca é de quem usa (a do Luan não vem) | — | — | não | ~3,0 GB | sem biblioteca, não roda |

**Não comercial (CC BY-NC 4.0 e afins): CoTracker3 (câmera), MMS (fala no ms) e os de rosto (SCRFD do insightface, o peso do AdaFace).**
Uso interno da Fly, que o Luan liberou pro time (21/10: «A Fly não é comercial, é tudo intra-time, é teste»). Se um dia o uso for
comercial, esses saem.

**Ollama no Mac:** o Ollama roda os modelos na placa da Apple; o Tandera fala com ele pela porta 11434 (`TANDERA_OLLAMA`). O `base.Placa`
tira o Ollama da memória antes de cada peça (`keep_alive: 0`): no Mac (memória unificada) isso continua valendo [CÓDIGO].
