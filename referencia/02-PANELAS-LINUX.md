# «Panelas de som»: o Tandera rodando no Linux (perfil servidor) — 01/11/2026

> Versão limpa do relatório de 01/11 (`RELATORIO-PANELAS.md` no PC dele): nomes de cliente viraram o TIPO do vídeo, sem caminhos do PC,
> chaves ou máquinas. A prova foi no WSL (o Linux dentro do Windows), na mesma RTX 5070 do PC.

1. **Roda no Linux (provado no WSL Ubuntu-24.04, na placa):** as 11 peças do perfil servidor — preparo, cortes, separação (Roformer →
   BandIt), fala (Whisper turbo + MMS + onda), batida, música, rótulos (CED), sinal, texto (PaddleOCR), ovis, olho (Gemma 4 no Ollama) —
   instaladas pelo `servidor/preparar_tandera.sh` com as versões EXATAS do PC (`servidor/requisitos/*.txt`).
2. **Dá o mesmo resultado que o PC:** cortes no mesmo quadro (75/75), palavras com o mesmo texto e o mesmo tempo (530/530; só 2 passam de
   1 ms: 40 e 20 ms), rótulos 100% iguais, ataques no mesmo ms (294/294), batidas e música idênticas.
3. **A fila e o caminho de volta funcionam:** `montar_lote` → `enviar` (preserva a data) → `rodar_lote` (pesados primeiro, fila entre
   máquinas, stems, desliga no fim) → `trazer` (soma sem estragar). O PC achou a análise que voltou: 11 peças guardadas, 0 s.
4. **O PC não mudou:** o V009 com stems no Windows depois de tudo = 6 peças guardadas, 0 s, nada refeito.

## Peça por peça (segundos; WSL = Linux na RTX 5070; PC = Windows, mesma placa, mesma hora, só referência)
Vídeos: **V009** (vlog do Plexus, 96,5 s, 1080×1920, voz e música prontas) · **tutorial 4K** (2 min de um tutorial de cliente em 4K AV1 + Opus).

| peça | Linux? | WSL V009 | WSL tutorial | PC V009 | PC tutorial | diferença medida contra o PC |
|---|---|---|---|---|---|---|
| preparo | sim | 10,1 | 10,7 | 8,1 | 10,3 | (entrada das outras) |
| cortes | sim | 54,5 | 50,9 | 27,0 | 73,6 | 58/58 e 17/17 no mesmo quadro |
| separação | sim | 0,2 (stems) | 73,8 | 0,2 | 135,0 | tutorial: voz idêntica; música/efeitos dif. máx. 0,00018 (SNR 82 / 70 dB) |
| fala | sim | 16,7 | 18,4 | 29,8 | 9,9 | V009 195/195 palavras, texto 100% igual, 193 iguais no ms, pior 40 ms; tutorial 335/335, p95 = 0 ms |
| batida | sim | 1,8 | 4,3 | 11,0 | 4,3 | 145/145 e 152/152 idênticas (0 ms), mesmo BPM |
| música | sim | 2,8 | 6,9 | 14,4 | 7,9 | mesmas partes, mesmo BPM, mesmas subidas/viradas |
| rótulos | sim | 6,5 | 8,1 | 18,0 | 4,8 | 192/192 e 240/240 janelas com a mesma 1ª etiqueta |
| sinal | sim | 6,7 | 28,0 | 8,6 | 97,0 | ataques 86/86 e 208/208 no mesmo ms |
| texto | sim | 16,3 | 25,5 | 48,3 | 66,2 | 72/72 e 58/58 itens, os mesmos textos |
| ovis | sim | 24,3 | 29,2 | 33,3 | 50,0 | cosseno trecho a trecho ≥ 0,9945 (8 bits nos dois) |
| olho | sim | 256,1 | 145,9 | 372,1* | — | texto livre do Gemma: rodou e gravou a ficha de cada plano |
| **total** | | **396** | **401** | | | |
\* olho do PC = outra rodada, só pra ordem de grandeza.

### Ficam só no PC (perfil `pc`)
entonação (Praat no processador, 0,5 s — sobe fácil) · câmera e corpo (repositório e pesos à parte: CoTracker3, Sapiens2) · boca (OpenFace,
que no PC já roda pelo WSL) · rostos (o instalador do servidor não monta) · imagem, som (não pedidos pro lote de som) · diário, busca (o
diário precisa da chave do Gemini de quem usa) · efeitos (precisa da biblioteca de efeitos) · pisada (ferramenta).

## O que mudou no código pra rodar no Linux
| arquivo | o que mudou | por quê |
|---|---|---|
| `tandera/base.py` | caminhos **por máquina**: Windows = os do PC dele (no PACOTE também viraram variável); Linux = variáveis `TANDERA_*` (sem elas, onde o instalador põe). Perfil: Linux = «servidor». Cronômetro: `time.monotonic()` | o relógio do WSL pulou ~2 min pra trás durante a prova |
| `tandera/__init__.py` | `no_ambiente()` compara com o ambiente do `base.PY` | no servidor o ambiente é `/root/venv_tandera` |
| `tandera/armazem.py` | `nome_da_pasta(nome, assinatura)` separado | o lote calcula no computador de quem manda o nome da pasta que o servidor vai usar |
| `tandera/pecas/separacao.py` | `--model_file_dir` do Roformer quando existe; o Python do BandIt vem de `base.PY_CINE` | no Linux o modelo mora no disco da máquina |
| `tandera/pecas/olho.py` | a fonte do carimbo de tempo = `base.FONTE` (Linux: Liberation Sans Bold, mesma medida da Arial Bold) | `C:\Windows\Fonts` não existe |
| `tandera/sinal.py` | se o OpenCV não abre NENHUM quadro, lê pelo ffmpeg e faz a MESMA conta | o OpenCV do Linux não abre AV1: o sinal saía com 0 picos de movimento |

## Achados da prova
1. **Rótulos falhavam no Linux** («não conectou no Hugging Face»): o código do CED-Base busca a lista das 527 etiquetas em OUTRO repositório
   (`topel/ConvNeXt-Tiny-AT`); no PC estava no cache. O instalador agora baixa.
2. **AV1 no OpenCV do Linux:** consertado no `sinal.py`.
3. **Ollama com systemd** (WSL): o instalador do Ollama sobe um serviço próprio que guarda o modelo em outro lugar; o script desliga esse
   serviço e usa o do Tandera (no RunPod não há systemd).
4. **Soma de stems com 2 bytes diferentes** entre Windows e Linux (o soundfile grava a HORA no cabeçalho) → outra assinatura → o PC
   refaria tudo. Agora o wav é escrito à mão, sem hora: mesmo sha1, mesma versão nos dois (`servidor/stems.py`).
5. **Stems do Plexus fora do tamanho do vídeo** (15 de 27 projetos): o lote NÃO usa stem desalinhado (±0,5 s); esses separam pelo modelo.

## Custo estimado (régua: RTX PRO 4500 a US$ 0,74/h, pelo tempo medido no WSL; as 11 peças)
- tutorial 4K, sem stems: 401 s de máquina pra 120 s de vídeo = **3,3×** (o olho é 1,2× disso);
- vlog do Plexus, com stems: 396 s / 96,5 s = **4,1×** (o olho é 2,7×: 59 planos em 96 s); sem stems soma ~0,6× da separação.
- Pra ~11 h de vídeo (a maior parte tutorial): ~40 h de máquina ≈ **US$ 30** com o olho, ~US$ 18 sem. É um TETO (a PRO 4500 tem ~70%
  mais núcleos de placa que a 5070 e 32 GB). Fora a placa: o storage de rede (cobrado por GB/mês) e o envio pela internet.
- (O lote por peça, `03-LOTE-POR-PECA.md`, baixou isso; o piloto real, `04-PILOTO-RUNPOD.md`, mostrou que no 4K o gargalo é o processador.)

## O que NÃO foi provado aqui
A máquina real do RunPod (veio no piloto, `04`); o Ovis em bf16 lote 16 (o padrão do perfil servidor: no WSL foi 8 bits lote 4, igual ao
PC); o olho comparado número a número (é texto livre); `enviar.py --ssh` e `trazer.py --ssh` de verdade (provados pelo mesmo tar com `--wsl`).
