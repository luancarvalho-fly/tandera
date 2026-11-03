# TANDERA no RunPod — pra quem não tem PC forte

**Pra quê:** o Tandera completo quer uma placa NVIDIA (o Ovis, a separação, o Gemma). Sem ela, você aluga uma máquina Linux com placa por
hora no **RunPod** (runpod.io), roda o MESMO motor lá (o perfil `servidor`) e traz as análises pro seu computador. Funciona do Windows,
do Mac ou do Linux: o seu computador só monta o lote, manda e traz.

**A conta do RunPod é sua** (cartão seu, chave SSH sua). O seu Claude te guia, mas quem cria a conta, põe crédito e clica em «Deploy» é
você. **Comece SEMPRE por um piloto pequeno (menos de US$ 1)**, veja o custo real, e só depois mande o lote.

## O que é
 o MESMO motor, no perfil `servidor` (Linux + placa NVIDIA), numa máquina alugada por hora. Peças que rodam lá: preparo,
cortes, separação, fala, batida, música, rótulos, sinal, texto, ovis, olho. Serve pra analisar MUITO vídeo (um lote) ou as peças pesadas que
o seu computador não aguenta. A análise volta pro seu computador e soma no que você já tem (pela assinatura). Provado: no Linux o resultado é o MESMO do
PC (cortes no mesmo quadro, palavras no mesmo ms, rótulos 100% iguais; `referencia/02-PANELAS-LINUX.md`), e o lote por peça é igual byte a
byte e 1,6× mais rápido (`referencia/03-LOTE-POR-PECA.md`).

## Antes de tudo
**O Claude só aluga ou liga máquina paga com o «pode» da pessoa, dizendo antes o preço por hora** (e o do storage, que é
cobrado por mês mesmo com a máquina desligada). Conta, chave SSH e cartão são dela: o Claude nunca pede senha nem chave privada.

## O que alugar (o que foi medido)
- Placa: **RTX PRO 4500** (32 GB) a **US$ 0,74/h** (preço de 01/11 — confira no site antes). Qualquer NVIDIA com ≥ 16 GB e CUDA 12.8+ deve
  servir [TESTAR]; o Ovis em bf16 lote 16 (o padrão do servidor) quer ~16 GB livres.
- Imagem: uma de **PyTorch com CUDA 12.8 ou mais novo** (Ubuntu). SSH ligado com a SUA chave pública.
- Disco: os modelos ocupam ~23 GB (Whisper turbo + Ovis 12,7 GB · torch hub 1,3 GB · pesos 1,25 GB · PaddleOCR 0,15 GB · Ollama 7,5 GB) +
  ~15 GB de ambientes + os seus vídeos + ~3× os vídeos pras análises. Um **Network Volume** (storage de rede) em `/workspace` guarda os
  modelos entre uma máquina e outra (o preparar copia pro disco local); pra 1 máquina só, o disco do container basta.
- **Processador:** o aluguel libera poucos núcleos (no piloto: **6,8**, embora a máquina mostre 64). Vídeo 4K (sobretudo AV1) fica lento
  no processador (preparo, cortes e sinal decodificam o vídeo): escolha máquina com mais núcleos, ou mande vídeo menor.

## O passo a passo
Testado no WSL e, até o lote, no piloto do RunPod; os comandos do seu computador valem no Mac e no Windows. Rode-os de dentro
da pasta deste repositório, com um Python 3.10+ qualquer (montar, mandar e trazer não precisam do ambiente pesado do Tandera).

0. **Criar a máquina (você, no site runpod.io):** conta + crédito; em **Settings → SSH Public Keys** cole a sua chave PÚBLICA (o seu
   Claude te ajuda a criar uma com `ssh-keygen -t ed25519` se você não tiver; a privada nunca sai do seu computador). Depois **Pods →
   Deploy**: a placa da tabela acima, uma imagem **PyTorch** com CUDA 12.8+, disco do container ≥ 60 GB (ou um Network Volume em
   `/workspace`), e **Deploy**. Na página do pod, **Connect** mostra o `ssh root@<IP> -p <PORTA>` (o «SSH over exposed TCP»).
1. **Seu computador — montar o lote** (calcula aqui a assinatura de cada vídeo, pra análise voltar com o nome certo):
   `python servidor/montar_lote.py --nome teste --video A.mp4 [--video B.mp4] [--receita tutorial] [--stem voz=V.wav --stem musica=M.wav]`
   (ou um `LEVANTAMENTO.json` com grupos: `--levantamento ... --grupos tutorial`). Sai em `lotes/montados/teste.json`.
2. **Os pesos que não se baixam sozinhos:** o `autoshot.onnx` já vem em `modelos/`; o **BandIt Plus**
   (`model_bandit_plus_dnr_sdr_11.47.chpt`, 148,9 MB) baixe da release v.1.0.3 de github.com/ZFTurbo/Music-Source-Separation-Training e
   ponha em `terceiros/separador-cinema/modelos-teste/bandit_plus/`. O BS-Roformer o servidor baixa sozinho.
3. **Seu computador — mandar** código, pesos e lote (um tar só; pula o que já está lá; recomeça se cair):
   `python servidor/enviar.py --ssh "root@<IP> -p <PORTA> -i <caminho da sua chave>" --codigo --pesos --lote lotes/montados/teste.json`
4. **Na máquina (SSH) — preparar** (~7 min; rodar de novo é seguro): `bash /workspace/tandera/codigo/servidor/preparar_tandera.sh` e
   `source /root/ativar_tandera.sh`. Ele instala ffmpeg 9.0, uv, 4 ambientes com as versões EXATAS do PC, baixa os modelos uma vez pro
   storage e confere se cada um abre na placa. (Se quiser a chave do Hugging Face: `/workspace/hf/token`; sem ela baixa mais devagar.)
5. **Na máquina — rodar:** `nohup $TANDERA_PY /root/TANDERA/servidor/rodar_lote.py --lote /workspace/tandera/lotes/teste.json --desligar > /root/lote.log 2>&1 &`
   Andamento: `$TANDERA_PY /root/TANDERA/servidor/rodar_lote.py --lote ... --estado`. Máquina que morreu no meio: `--soltar`; o que falhou:
   `--refazer-falhos` (continua do que já foi guardado).
6. **Seu computador — trazer** (soma sem estragar o que você já tem): `python servidor/trazer.py --ssh "root@<IP> -p <PORTA> -i <chave>" --sem-audio`
   (`--sem-audio` deixa os wav grandes lá: a volta pela internet é lenta).
7. **Desligar:** o `--desligar` do passo 5 desliga a máquina sozinho quando a fila acaba (`runpodctl stop pod`). **Confira no site que ela
   parou.** O storage continua cobrando por mês: apague quando não precisar mais (com o "pode").

## Quanto custa
Nas rodadas medidas (`referencia/04-PILOTO-RUNPOD.md`): o **piloto** (4 vídeos de tipos diferentes) = 39 min de relógio,
**~US$ 0,48** (instalar 7,1 min ≈ US$ 0,09; o lote 17,5 min ≈ US$ 0,22). Máquina por segundo de vídeo, sem o olho: trailer 1,44× · vlog com
stems 0,75× · gravação do Kakashi 0,14× · tutorial 4K AV1 ~1,9×. Ex.: 1 hora de trailer ≈ 1,5 h de máquina ≈ US$ 1,10. O olho (Gemma) pode
dobrar o tempo onde ele liga. Na mesma noite, 3 máquinas analisaram ~25 h de vídeo em ~3,5 h de relógio (o relatório dele ainda estava
em rascunho, sem o custo; pela conta dos horários, ~US$ 8 — não medido). Comece SEMPRE por um piloto pequeno (< US$ 1), veja o custo
real, e só depois o lote.

## Lições do RunPod
 nunca rode programa de DENTRO do `/workspace` (copie pra `/root`); com mais de uma máquina num storage «Global», o
«criar se não existe» da fila não é garantido: divida os vídeos de antemão (`--so ID,ID` em cada máquina); credenciais do seu computador
(tokens, Drive) não vão pro servidor; o `preparar_tandera.sh` escreve em `/root/...` (numa máquina só sua, ok).
