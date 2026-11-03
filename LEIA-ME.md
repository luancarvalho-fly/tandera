# O TANDERA — o motor de análise de vídeo e som da Fly (um só, sempre o mais novo)

Cópia do Tandera do Luan Carvalho (01/11/2026) pro time, com os caminhos do PC dele trocados por variáveis `TANDERA_*`. A
instalação está no `CLAUDE.md`, o RunPod no `RUNPOD.md`, o Mac no `MAC.md`; aqui é o manual do motor.

**A lei (Luan, 01/11/2026):** «o Tandera é o nosso motor, pra análise de qualquer skill que a gente use. Ele tem que estar 100%
atualizado. É inadmissível você rodar qualquer coisa, hoje, a partir de hoje, no Tandera 1.0, 2.0.» · «o Tandera sempre foi... uma coisa
só, ele só melhorou» · «se [X e Y] foram substituídos pelo W e o Z, você vai rodar com W e com Z».

## REGRA PRA SEMPRE
1. **Toda** skill e app que analisa vídeo/som chama ESTE motor (nunca um número de versão, nunca um motor próprio).
2. **Melhoria de peça entra AQUI:** troca o código em `tandera/pecas/<peça>.py` e sobe a `versao` dela em `tandera/manifesto.py` (e uma
   linha em `TROCAS` se o modelo mudou). Quem chama o Tandera sobe junto, sem mexer em nada.
3. **Análise guardada é incremental:** a próxima análise de um vídeo já analisado roda só a peça cuja versão mudou (e as que dependem
   dela) e SOMA no que estava guardado. A análise é achada pela ASSINATURA do arquivo (tamanho + data + 1 MB do começo e do fim), não
   pelo nome.
4. **O porte pro Mac NÃO é um Tandera paralelo:** o Mac vira um 3º caminho/perfil dentro deste mesmo código (como o `servidor` virou), e
   o que mudar volta pro Luan juntar no motor dele.
5. **Placa:** um trabalho por vez. No PC do Luan ele recusa a placa com o Premiere aberto, tira o Ollama da placa antes de cada peça e
   mede tempo / pico de memória / uso de cada peça (`RESUMO.md` de cada análise).

## Como usar (de dentro desta pasta; o Python é o do ambiente do Tandera)
```
python -m tandera versao                                  o manifesto: peça · modelo · versão · onde · perfis
python -m tandera analisar <vídeo>                        as peças padrão (só roda o que falta ou mudou)
python -m tandera analisar <vídeo> --pecas cortes,fala    só essas (+ as de que dependem)
python -m tandera analisar <vídeo> --refazer som          refaz uma peça mesmo guardada
python -m tandera analisar <vídeo> --sem-placa            tudo no processador
python -m tandera analisar <vídeo> --stem voz=W --stem musica=W   voz/música PRONTAS valem como a separação
python -m tandera fala <áudio> --idioma pt --dispositivo cpu --json
python -m tandera batidas <música.wav> · rotular <som.wav> · buscar <vídeo> "frase" · onde <vídeo>
```
No Windows, `tandera.cmd` faz o mesmo com o `.venv` desta pasta. Em Python, de QUALQUER ambiente (o pesado roda sozinho no ambiente
do Tandera, o de `TANDERA_PY`):
```python
import sys; sys.path.insert(0, "<a pasta do tandera>")
import tandera
A = tandera.analisar(video, pecas=["cortes", "fala"], placa="auto")
A["cortes"]["cortes"], A["fala"]["palavras"], A.pasta, A.versao("fala")
tandera.frases(A)                                             # cada frase no MILISSEGUNDO (palavras do MMS + conferência na onda)
tandera.transcrever(audio, idioma="pt", dispositivo="cpu")   # só a fala (é o que o Kakashi usa)
tandera.batidas(wav) · tandera.rotular(wav) · tandera.sinal.ataques(wav)
```
A análise de cada vídeo fica em `analises/<nome>_<assinatura>/` (ou onde `TANDERA_ANALISES` disser): `analise.json` (o índice: versão
de cada peça, com que entradas foi feita, quando, perfil, tempo e placa), `pecas/<peça>.json` (o resultado), `pecas/<peça>/` (o que é
grande) e `RESUMO.md` (legível).

## As peças (detalhe e versão: `python -m tandera versao`; tabela completa no `MODELOS.md`)
| peça | o quê | modelo |
|---|---|---|
| preparo | abre o vídeo 1 vez: meta, giro à mão, 1ª trilha de som que abre, quadros 1/s, cópia 480p | ffmpeg |
| cortes | corte no quadro exato | AutoShot ∪ TransNetV2 (+ pixel = possível jump cut) |
| separacao | voz / música / efeitos | BS-Roformer → BandIt Plus |
| fala | palavra no ms | Whisper large-v3-turbo + MMS_FA + onda |
| entonacao | altura e final de cada fala | Praat |
| batida | batida no ataque, grade, corte × batida | Beat This! |
| musica | partes, subidas, drops, viradas | medidor da régua (Beat This! + librosa) |
| rotulos | etiquetas do som sem a voz | CED-Base |
| sinal | ataques, picos de movimento, vãos, eventos candidatos | conta pura |
| camera | curva do movimento de câmera por plano | CoTracker3 |
| corpo* | fase da repetição por plano | Sapiens2-1B |
| boca* | boca × fala | OpenFace 3.0 (no PC do Luan, pelo WSL) |
| rostos | caixa, digital, expressão (1/s) | SCRFD + AdaFace + EmotiEffLib b0 |
| texto | texto na tela | PaddleOCR 3.7 (ambiente separado) |
| imagem | retrato de cada quadro 1/s | SigLIP 2 so400m |
| som | retrato do som (5 s / 2,5 s) | CLAP larger_clap_general |
| ovis | retrato vídeo+som de cada 4 s | Ovis-Omni-Embedding-3B |
| diario | o vídeo inteiro descrito (vê + ouve) | Gemini Flash (chave de quem usa) |
| busca | frase → momento no diário | BM25 + Qwen3-Embedding-8B |
| olho | ficha de cada plano | Gemma 4 12B (Ollama) |
| efeitos* | qual arquivo da biblioteca de efeitos tocou | encaixe na onda (precisa de uma biblioteca indexada) |
| pisada (ferramenta) | esqueleto quadro a quadro | MediaPipe Pose heavy |
`*` = só quando pedida (`--pecas`).

## Dois perfis (o Mac vai ser o 3º)
`pc` (o PC do Luan: Windows, RTX 5070 12 GB) e `servidor` (qualquer Linux: o RunPod, ou o WSL na prova). O manifesto diz quais peças
cada perfil roda; a análise grava o perfil que rodou. Peças do servidor: preparo, cortes, separação, fala, batida, música, rótulos,
sinal, texto, ovis, olho.

## Onde o Tandera acha as coisas (`tandera/base.py`)
Tudo por variável; sem ela, o padrão:
| variável | o quê | padrão no Windows (esta pasta) | padrão no Linux (o que o `preparar_tandera.sh` monta) |
|---|---|---|---|
| `TANDERA_PY` | o Python do ambiente principal | `.venv\Scripts\python.exe` | `.venv/bin/python` |
| `TANDERA_PY_OCR` | o Python do PaddleOCR | `.venv-ocr\Scripts\python.exe` | `/root/venv_ocr/bin/python` |
| `TANDERA_ROFO` | o `audio-separator` (BS-Roformer) | `.venv-sep\Scripts\audio-separator.exe` | `/root/venv_sep/bin/audio-separator` |
| `TANDERA_ROFO_MODELOS` | onde mora o modelo do Roformer | o padrão do audio-separator | `$TANDERA_PESOS/audio-separator` |
| `TANDERA_PY_CINE` | o Python do BandIt (msst) | `.venv-cine\Scripts\python.exe` | `/root/venv_cine/bin/python` |
| `TANDERA_CINE` | o código do BandIt + a config + o peso | `terceiros\separador-cinema` | `$TANDERA_PESOS/separador-cinema` |
| `TANDERA_PESOS` | a pasta dos pesos | `pesos\` | `/root/tandera_pesos` |
| `TANDERA_AUTOSHOT` | o `autoshot.onnx` | `modelos\autoshot.onnx` (vem no pacote) | `$TANDERA_PESOS/autoshot.onnx` |
| `TANDERA_CED` | o CED-Base | `pesos\ced-base` | `$TANDERA_PESOS/ced-base` |
| `TANDERA_REGUA` | modelos e repositórios da câmera/corpo/boca | `pesos\regua` | `$TANDERA_PESOS/regua` |
| `TANDERA_POSE` | o MediaPipe Pose heavy | `pesos\pose_landmarker_heavy.task` | `$TANDERA_PESOS/...` |
| `TANDERA_CHAVE_GEMINI` / `GEMINI_API_KEY` | a chave do Gemini (diário) — DE QUEM USA, nunca no pacote | `~\.gemini\chave-api.txt` | `~/.gemini/chave-api.txt` |
| `TANDERA_ANALISES` | onde as análises ficam | `analises\` | `analises/` (o servidor usa `/root/analises`) |
| `TANDERA_OLLAMA` | o Ollama (olho) | `http://localhost:11434/api` | o mesmo |
| `TANDERA_FONTE` | a fonte do carimbo de tempo do olho | Arial Bold | Liberation Sans Bold |
| `TANDERA_PERFIL` | força o perfil | `pc` | `servidor` |
| `TANDERA_OVIS_PRECISAO` / `_LOTE` | precisão e lote do Ovis | `8bit` / 4 no perfil pc | `bf16` / 16 no servidor |
Os pesos da `rostos` (SCRFD, AdaFace, EmotiEffLib) ficam em `modelos\scrfd`, `modelos\adaface` (o `net.py` do AdaFace já vem) e
`modelos\emotiefflib`. Os do Hugging Face (Whisper turbo, Ovis, CLAP, SigLIP 2, Qwen3-Embedding) e do torch.hub (MMS_FA, Beat This!) vão
pro cache padrão de cada um (`HF_HUB_CACHE`, `TORCH_HOME`).

## O Tandera no servidor (`servidor/`: Linux, RunPod — passo a passo no `RUNPOD.md`)
```
seu computador:  python servidor/montar_lote.py --nome X --video A.mp4 [--video B.mp4] [--receita tutorial]
seu computador:  python servidor/enviar.py --ssh "root@IP -p PORTA -i <sua chave>" --codigo --pesos --lote <lotes/montados/X.json>
servidor:        bash /workspace/tandera/codigo/servidor/preparar_tandera.sh && source /root/ativar_tandera.sh
servidor:        $TANDERA_PY /root/TANDERA/servidor/rodar_lote.py --lote /workspace/tandera/lotes/X.json --desligar
seu computador:  python servidor/trazer.py --ssh "root@IP -p PORTA -i <sua chave>" [--sem-audio]
```
**Lote por PEÇA (`tandera/lote.py`):** o `rodar_lote.py` pega um BLOCO da fila (`--bloco 12`, padrão); o processador prepara o PRÓXIMO
bloco enquanto a placa passa o atual peça por peça — cada modelo carrega UMA vez pro bloco. Mesmo resultado e mesmo jeito de guardar
(provado byte a byte, `referencia/03-LOTE-POR-PECA.md`). `--bloco 0` = um `tandera analisar` por vídeo. No computador de cada um
(`tandera.analisar`, um vídeo) nada muda: `base.SEGURAR` só liga no lote. As peças de cada vídeo saem da RECEITA do grupo
(`servidor/receitas.json`, lida pelo `montar_lote.py`).

## Ambiente
- Principal: Python 3.12, torch 2.11 (cu128 no PC do Luan), onnxruntime-gpu 1.23.2 (o «onnxruntime» de processador que o faster-whisper
  puxa é tirado; no Windows o onnxruntime-gpu precisa do `preload_dlls()` pra achar as DLLs do CUDA: o `base.ort_sessao` faz isso e
  avisa). Versões exatas: `servidor/requisitos/tandera.txt` (do PC dele) e `ambiente/requisitos.txt` + `ambiente/travar.txt`.
- Separados (as bibliotecas brigam): PaddleOCR 3.7 + paddlepaddle 3.3 (`requisitos/ocr.txt`), o audio-separator do BS-Roformer
  (`requisitos/sep.txt`), o msst do BandIt em Python 3.13 (`requisitos/cine.txt`).
- `ambiente/instalar.py` é o instalador do PC do Luan (Windows + CUDA): serve de receita, não de instalador pro Mac.
