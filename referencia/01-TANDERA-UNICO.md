# O Tandera único — o relatório da medida (01/11/2026, 03:20–04:55, no PC do Luan)

> Versão limpa do relatório de 01/11 (`estudo\tandera-unico-2026-11-01\RELATORIO.md` no PC dele): caminhos do PC e nomes de apps
> pessoais tirados; os números são os medidos. «V009» = um vlog do Plexus (96 s, 1080×1920, 24 q/s), o vídeo de prova.

## O que é o Tandera agora (medido no V009, uma peça por vez na placa, RTX 5070 12 GB)
| peça | modelo | versão | onde | tempo no V009 | placa (pico no total · uso médio) |
|---|---|---|---|---|---|
| preparo | ffmpeg (abre 1 vez, giro à mão, 1ª trilha que abre) | 2026-11-01 | processador | 7,5 s | — |
| cortes | AutoShot ∪ TransNetV2 (+ pixel = possível jump cut) | 2026-11-01 | placa | 12,1 s | 3,7 GB · 5% |
| separacao | BS-Roformer → BandIt Plus | 2026-10-21 | placa | 97,5 s | 6,3 GB · 21% |
| fala | Whisper large-v3-turbo + MMS_FA (ms) | 2026-11-01b (hoje 01c) | placa | 31,0 s | 3,6 GB · 10% |
| entonacao | Praat | 2026-10-18 | processador | 0,5 s | — |
| batida | Beat This! + ataque + grade | 2026-10-20 | placa | 10,2 s | 3,7 GB · 1% |
| musica | medidor da régua (partes, subidas, drops) | 2026-10-19 | placa | 9,8 s | 3,7 GB · 4% |
| rotulos | CED-Base (etiquetas do som sem a voz) | 2026-11-01 | placa | 22,2 s | 3,8 GB · 3% |
| sinal | ataques, picos de movimento, vãos, eventos | 2026-11-01 | processador | 6,2 s | — |
| camera | CoTracker3 (autocast fp16) | 2026-11-01b | placa | 56,1 s | 8,9 GB · 48% |
| corpo | Sapiens2-1B fp16 + DETR | 2026-11-01 | placa | 435,0 s | 5,2 GB · 72% |
| boca | OpenFace 3.0 (pelo WSL) | 2026-10-21 | placa | 357,8 s | 3,9 GB · 4% |
| rostos | SCRFD + AdaFace + EmotiEffLib b0 | 2026-11-01 | placa | 11,3 s | 2,6 GB · 3% |
| texto | PaddleOCR 3.7 (na placa, ambiente separado) | 2026-11-01 | placa | 39,5 s | 2,4 GB · 6% |
| imagem | SigLIP 2 so400m | 2026-11-01 | placa | 8,5 s | 4,5 GB · 20% |
| som | CLAP larger_clap_general | 2026-11-01 | placa | 13,1 s | 2,8 GB · 2% |
| ovis | Ovis-Omni-Embedding-3B (PC: 8 bits, lote 4) | 2026-11-01 | placa | 25,6 s | 8,9 GB · 31% |
| diario | Gemini Flash (chave grátis do PC) | 2026-11-01 | nuvem | 232,9 s | — |
| busca | BM25 + Qwen3-Embedding-8B (4 bits) | 2026-11-01 | placa | 21,6 s | 6,7 GB · 7% |
| olho | Gemma 4 12B (Ollama) | 2026-10-23 | placa | 372,1 s | 10,5 GB · 39% |
| efeitos | encaixe na onda contra a biblioteca | 2026-10-20 | placa | 108,8 s | 5,6 GB · 60% |
| pisada (ferramenta) | MediaPipe Pose heavy | 2026-11-01 | processador | (por trecho) | — |

**Soma: 1.879 s (~31 min) pras 21 peças no V009.** Placa parada (Windows + o Whisper do ditado dele): ~3 GB.

## Como ele é
- **Um motor só:** o pacote `tandera/` (uma peça por arquivo em `tandera/pecas/`), o `manifesto.py` (peça · modelo · versão · onde · de
  que depende · perfis) e uma entrada única (`python -m tandera ...`). A base do código é o motor do servidor do catálogo da Fly (preparo
  com o giro, a 1ª trilha que abre, Ovis em lote que divide no OutOfMemory, SCRFD + AdaFace + expressão, PaddleOCR na placa em ambiente
  separado, Gemini com `raw_decode`) + as medidas finas da régua de outubro (corte no quadro, fala no ms, batida, câmera, corpo, boca,
  efeitos) + as contas de sinal de agosto — sem número de versão.
- **Análise guardada e incremental:** `analises/<nome>_<assinatura>/analise.json` grava, por peça, a versão, com que versões das entradas
  ela foi feita, perfil, tempo e placa. Roda só a peça que falta, que mudou de versão, ou cuja entrada mudou. Achada pela ASSINATURA.
- **Placa:** um trabalho por vez; no PC dele avisa num app de agenda (o Medidor), recusa a placa com o Premiere aberto (ou vai pro
  processador com `placa="auto"`), tira o Ollama da placa antes de cada peça e mede cada peça.
- **Dois perfis** (`pc` / `servidor`): o manifesto diz quais peças cada um roda; a análise grava o perfil que rodou.

### O Ovis no PC (12 GB): precisão × lote (24 trechos de 4 s do V009, Ollama fora da placa, Whisper do ditado nela)
| precisão | lote | s/trecho | placa no total | uso médio | retrato igual ao bf16 |
|---|---|---|---|---|---|
| bf16 | 1 | 0,27 | 11,2 GB (passa do teto) | 74% | 1,000 |
| bf16 | 4 | 1,79 (derramou) | 11,6 GB | 98% | 0,999 |
| **8 bits** | **4** | **0,34** | **8,9 GB** | **72%** | **0,991** |
| 4 bits | 4 | 0,27 | 7,1 GB | 68% | 0,953 |
Ficou 8 bits, lote 4. (8 bits e 4 bits usam o bitsandbytes, que só existe com CUDA: no Mac, bf16.)

### O que melhorou de peça no caminho (medido, versão subida)
- **fala 2026-11-01b:** o VAD e o corte de energia em −40 dB ABSOLUTO comiam fala de microfone baixo (numa sessão do Kakashi: 304
  palavras). Sem VAD e corte RELATIVO ao próprio arquivo: 421 palavras, nada perdido. No V009 os dois descartes foram «Tchau!» e
  «Obrigado.» (as alucinações clássicas). **fala 2026-11-01c** (mesmo dia): uma sessão com 100 s de silêncio digital no começo dava ZERO
  segmentos (o Whisper inventava uma frase no silêncio e repetia por cima da fala); agora ele só ouve os trechos COM SOM e cada trecho não
  herda o texto do anterior.
- **camera 2026-11-01b:** em fp32 o CoTracker3 levava a placa a 11,1 GB; com autocast fp16: 8,9 GB, 58/58 classes iguais e a mesma curva,
  40% mais rápido.
- **onnxruntime na placa (Windows):** o AutoShot caía no PROCESSADOR sem avisar (as DLLs do CUDA). `preload_dlls()` + aviso: cortes de
  64 s → 12 s.

## Os 5 testes (todos no V009)
1. **O Tandera inteiro:** as 21 peças rodaram (tabela de cima). A 2ª rodada já foi incremental de verdade: a fala mudou de versão e
   rodaram só ela e as que dependem dela + o que faltava; 13 vieram guardadas.
2. **Nada piorou (cortes), gabarito de 57 cortes, a ±0,10 s:**
   | detector | acertou | perdeu | a mais |
   |---|---|---|---|
   | agosto (histograma) | 41/57 | 16 | 1 |
   | AutoShot sozinho | 54/57 | 3 | 2 |
   | TransNetV2 sozinha | 54/57 | 3 | 2 |
   | **Tandera (AutoShot ∪ TransNetV2)** | **55/57** | **2** | 2 (talvez cortes que o gabarito não marcou) |
   Uma análise do zero do mesmo vídeo (outro nome de arquivo) repetiu cortes, etiquetas (192/192) e sinal; a fala variou 1 palavra em 200
   (Whisper em fp16).
3. **Incremental:** fingindo um CLAP novo (`--versao-de som=...`) e pedindo as 21 peças: **rodou só o `som`** (17 s; a rodada inteira 25 s),
   20 vieram guardadas, **nenhum outro arquivo mudou** (byte a byte).
4. **A trava:** 22/22 tentativas de usar o Tandera velho (agosto/outubro) falharam com o aviso em português.
5. **Cada consumidor pelo Tandera:** a régua, as skills de som e de edição dele e o **Kakashi** — numa sessão antiga do Kakashi (3 min),
   53 s no processador; a transcrição velha (do whisper-server do ditado) foi refeita sozinha porque a versão da fala mudou; 392 palavras
   × 384 da antiga, começo inteiro.

## O que não deu (e por quê)
- **Placa no máximo: não em todas.** rotulos (3%), rostos (3%), texto (6%), batida (1%), som (2%) e boca (4%) passam a maior parte do tempo
  no processador (preparar áudio/quadro, 1 quadro por vez). Funcionam; a otimização (lote no SCRFD/OCR) ficou pra depois.
- **olho (Gemma 4) a 10,5 GB** no total — no limite do teto. É o Ollama quem aloca.
- **CED × CLAP:** o CED é o melhor ETIQUETADOR (75% × Dasheng 67% × YAMNet 55%) → peça «rotulos»; «som parecido» continua o CLAP (79%).
- **Gemini:** o modelo mais novo deu 503 (servidor cheio) 4×; o Tandera caiu sozinho no seguinte. 233 s.
- **O catálogo da Fly** tem o motor dele (outro programa): um script de sincronia confere 20 pontos peça por peça (mesmo modelo, mesmo
  jeito de medir) — em 01/11, 20 iguais, 0 divergem.
