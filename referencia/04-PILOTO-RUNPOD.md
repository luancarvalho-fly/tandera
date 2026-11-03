# O piloto numa máquina DE VERDADE do RunPod (RTX PRO 4500) — 01/11/2026, 21:08 → 21:48

> Versão limpa do relatório do piloto (`RELATORIO-PILOTO.md` no PC dele): sem IP, porta, chave, nome de máquina, de storage ou de cliente
> (os vídeos viraram o TIPO). É a única rodada em máquina alugada com relatório fechado.

**Depois do piloto, na mesma noite (rascunho do relatório dele de 02/11 01:54, ainda SEM o custo):** 3 máquinas RTX PRO 4500 analisaram
~25 h de vídeo (tutoriais 17,2 h em 2 passadas — o vídeo inteiro com fala, texto e rótulos, e as peças pesadas só nas «janelas de
exemplo» —, gravações do Kakashi 6,9 h, vlogs do Plexus 0,9 h, trailers 0,2 h): liberadas 21:50, instaladas 22:03, lote 22:31 → tutoriais
prontos 01:20. Tudo voltou pro PC e foi achado pela assinatura (100%), 0 falha no fim. Tropeços que ele anotou: o NVENC sem driver (o corte
das janelas caiu pro processador por 30 min), o Gemma comendo o processador, falta de memória na placa com 3 trabalhadores numa máquina, o
disco enchendo, e a cota de download do Google Drive travando a subida do resto. Ordem de grandeza do custo (CONTA MINHA a partir desses
horários, não medida: 3 máquinas × ~3,5 h × US$ 0,74 ≈ US$ 8): o número de verdade é o do relatório final dele.

1. **Deu certo em parte:** trailer, vlog do Plexus (com stems) e uma sessão do Kakashi rodaram até o fim na placa real, sem falha. O
   tutorial 4K foi parado no prazo com 7 das 9 peças prontas. As 4 assinaturas calculadas no PC batem com as do servidor.
2. **Tempo total:** 39 min de relógio: instalar **7,1 min** (sem o Ollama) + lote **17,5 min** + envio e volta.
3. **Custo do piloto: ~US$ 0,48** (0,65 h × US$ 0,74): instalar US$ 0,09 · lote US$ 0,22 · o resto envio e espera.
4. **O que travou:** (a) **o processador no 4K**: o aluguel libera só **6,8 núcleos** (`/sys/fs/cgroup/cpu.max` = 680000/100000), embora
   a máquina mostre 64. No tutorial 4K, preparo + cortes + sinal levaram 622 de 792 s, com a placa a ~1%: o gargalo é decodificar AV1 4K
   no processador, não a placa. (b) A **volta pela internet é lenta** (~0,1–0,7 MB/s): use `trazer.py --sem-audio`.

## Peça por peça (segundos de máquina · pico de VRAM da peça / uso médio da placa)
| peça | trailer (74,8 s, 1080×1920, sem stems) | Plexus (80,4 s, 1080×1920, stems) | Kakashi `tela.mp4` (280 s, 1920×1080, stems fala/pc) | tutorial (548,6 s, **4K AV1**, sem stems) |
|---|---|---|---|---|
| preparo | 10,6 | 15,4 | 4 | **144,3** (processador) |
| cortes | 21,5 · 1,03 GB / 1% | 21,0 · 1,09 GB / 0% | 6,0 · 1,09 GB / 1% | **234,2** · 1,13 GB / **1%** |
| separação | 46,2 · 3,15 GB / 21% | 0,4 (stems) | 0,2 (stems) | 124,3 · 3,15 GB / 53% |
| fala | 6,1 · 2,96 GB / 9% | 6,2 · 2,96 GB / 13% | 7,8 · 2,94 GB / 21% | 13,5 · 3,03 GB / 37% |
| batida | 2,6 · 1,09 GB / 5% | 2,0 | — | 8,3 · 1,46 GB / 7% |
| música | 7,5 · 1,09 GB / 3% | 2,7 | — | 21,3 · 1,46 GB / 2% |
| rótulos | 3,2 · 1,27 GB / 0% | 1,9 · 1,27 GB / 0% | 3,1 · 1,26 GB / 0% | 2,6 · 1,27 GB / 8% |
| sinal | 8,9 | 9,2 | — | **243,1** (processador: lê o AV1 pelo ffmpeg) |
| texto | — | — | 16,8 · 1,97 GB / 25% | parado no prazo |
| ovis | — | — | — | não rodou (prazo) |
| olho | fora (receita) | fora (receita) | fora (sem Ollama no piloto) | fora (sem Ollama no piloto) |
| **total do Tandera** | **108 s** | **60 s** | **39 s** | **791,6 s** nas 8 que terminaram |
| **por segundo de vídeo** | **1,44×** | **0,75×** | **0,14×** | ~**1,9×** (1,44× medido + ~0,45× estimado do texto e do Ovis) |
| VRAM pico (máquina) | 2,7 GB | 2,5 GB | 2,5 GB | 2,7 GB |

## Instalar (medido)
| etapa | s |
|---|---|
| pacotes do sistema + ffmpeg 9.0 + uv | 15 |
| 4 ambientes (tandera 3.12.15, sep 3.12.15, cine 3.13.15, ocr Paddle 3.3.1 baixado da Paddle) | 338 |
| modelos (MMS_FA 1,2 GB a ~290 MB/s, Beat This, CED + etiquetas, PP-OCRv5) | 67 |
| conferência (torch 2.11+cu128 vê a placa, onnxruntime, ctranslate2, Paddle cuda) | 6 |
| **total** | **426 s = 7,1 min** |
Sem cache prévio do Whisper turbo e do Ovis (12,6 GB): + ~1 min a ~290 MB/s. Com o Ollama + gemma4:12b (7,5 GB): + ~1–2 min.

## Previsão pra um inventário de ~34 h de vídeo (pelos fatores medidos AQUI)
Sem o olho ≈ 37 h de máquina ≈ **US$ 27**; com o olho (não medido na PRO 4500; estimado do WSL) ≈ 62–76 h ≈ **US$ 46–56**. O peso está no
4K, e é PROCESSADOR. Duas máquinas = metade do tempo, mesmo custo.

## O que ficou anotado pra consertar no servidor (não mexido no código até 02/11)
- O `preparar_tandera.sh` escreve em caminhos fixos da raiz (`/root/venv_ocr`, `/root/hf_local`, `/root/TANDERA`, `/root/ativar_tandera.sh`):
  numa máquina SÓ SUA não tem problema; numa máquina dividida com outro programa, precisa de um prefixo (ex.: `TANDERA_RAIZ`). O
  `rodar_lote.py` também tem `/root/ollama.log` fixo.
- 4K AV1: preparo + cortes + sinal leem o vídeo no processador; com ~7 núcleos o 4K é ~3/4 do tempo. Vale decodificar na placa (NVDEC) ou
  alugar máquina com mais núcleos liberados.
- `montar_lote --stem papel=...` pula a tolerância de duração dos stems.

## Lições de usar o RunPod (das notas dele, 01/11, generalizadas)
- **O storage de rede (`/workspace`) é lento e esquisito:** nunca rode programa de DENTRO dele — copie pra `/root` antes (um `cp` de dentro
  travou uma máquina). Em storage «Global», arquivo novo demora a aparecer nas outras máquinas e o «criar se não existe» (O_EXCL) NÃO é
  garantido: com mais de uma máquina, divida a fila de antemão (`rodar_lote.py --so ID,ID` por máquina) em vez de confiar na fila.
- **Desligar no fim:** `runpodctl stop pod $RUNPOD_POD_ID` (a variável está em `/proc/1/environ`; a sessão SSH não herda) — o
  `rodar_lote.py --desligar` já faz isso.
- **Ordem:** piloto (< US$ 1, 1 vídeo de cada tipo) → custo real → lote.
- Chave do Hugging Face: sem ela baixa, só mais devagar. Credenciais (Drive, tokens) do seu computador NÃO vão pro servidor.
