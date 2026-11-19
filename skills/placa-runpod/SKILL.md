---
name: placa-runpod
description: Ligar, encher, vigiar e desligar placa de vídeo no RunPod pra rodar o Tandera (análise de vídeo/som) ou testar modelo. Use SEMPRE antes de ligar qualquer placa, quando falarem em RunPod, placa, pod, GPU alugada, lote, ou perguntarem quantas placas/quanto custa — ANTES de escrever qualquer comando.
---

# Placa no RunPod — ler ANTES de ligar

Estas regras saíram de rodadas reais do Tandera (out–nov/2026). Cada uma existe porque o erro custou dinheiro ou uma noite de trabalho.

## 0. Antes de qualquer coisa
- **Mostrar o lote e esperar o «pode ligar» do dono da conta:** o quê, por quê, placa, tempo e custo no pior caso.
- **Uma conta por assunto.** Trabalho da empresa na conta da empresa; coisa pessoal na conta pessoal. Nunca misturar chave nem placa.
- A chave da API e a chave SSH ficam em arquivos FORA de qualquer repositório; nunca imprimir a chave, nunca colar no chat.

## 0c. Checklist de ligar (responder cada linha no plano; linha sem resposta = não liga)
| # | Pergunta | O que acontece se pular |
|---|---|---|
| 1 | O **motor** (código, ambientes, pesos) está no **storage** (ou a 1ª placa instala nele antes das outras)? | cada placa instala do zero (~12–25 min parada) |
| 2 | **Disco ≥ 250 GB** em TODA placa (motor ~60 GB + teste + vídeos)? | o disco enche e a fila nunca começa |
| 3 | O pacote leva **todos os pesos que só existem no PC** (ex.: BandIt Plus + msst pra separação) e a placa **confere** que chegaram? | a peça falha em todos os vídeos |
| 3b | Todo vídeo em **1080p** (ou a máxima dele), conferido no `ffprobe` (resolução e duração)? | olho e OCR jogados fora; refazer tudo |
| 4 | Cada placa **cheia desde o início**? O `rodar_lote` lê o lote uma vez só: item somado depois não roda sem outra passada. | placa parada ou rodando um vídeo só |
| 5 | A fila **refaz os falhos sozinha** no fim (`rodar → --refazer-falhos → rodar`)? O `--refazer-falhos` só devolve pra fila e sai. | vídeo falho fica falho |
| 6 | **Vigia** ligado (bloco fechado, FALHOU, fila no FIM) e o 1º bloco conferido? | defeito descoberto horas depois |
| 6b | No 1º bloco, conferir a **SAÍDA de cada peça, não o ✓**: olho com quadros, separação com stems, fala com palavras, ovis com vetores. | peça sai ✓ vazia (já aconteceu com o olho: ~2 h sem imagem) |
| 7 | Teste em placa: insumos prontos antes de a instalação acabar; asset que já existe = usar ele. | placa instalada e parada |
| 8 | Fila INTEIRA acabou → trazer as análises, conferir a contagem e **apagar a placa na hora**. | placa ligada à toa |

Custo/tempo no plano: contar a peça **olho** (Gemma lê cada plano; ~38 s por minuto de vídeo com 1 pedido por vez).

## 1. A placa
- O **chip de vídeo (NVDEC)** decide: a **RTX PRO 4500 Blackwell Server Edition** tem 3 chips e abre o 4:2:2 das câmeras no chip
  (preparo 137 → 51 s no 4K). A 5090 do RunPod NÃO abre o chip. Abrir o vídeo sempre pelo chip (`-hwaccel cuda`).
- Ordem: PRO 4500 SE → PRO 4500 → PRO 4000 → A40 (A40 também pra repositório preso no CUDA 12.4, que não compila na Blackwell).
- Nos primeiros 30 s: testar o chip (`_nvdec_funciona`) e a internet. Preferir a Europa (EU-RO-1): baixava ~40× mais rápido que os EUA.
- A PRO 4500 vive sem vaga: «Deploy when available» deixa o pedido na fila.
- Ligar **pelo script** (placa ligada pela tela vem sem chave SSH e com disco pequeno; consertar reinicia). Nome: «Placa 1», «Placa 2»…

## 2. Encher cada placa (o que mais economiza)
- Uma placa tem ~48 núcleos e fica com a placa de vídeo parada fora da transcrição: rodar **vários vídeos por placa**.
- **2 linhas de vídeo na mesma placa** dividindo os modelos (Ovis 1 por vez) rendeu +40 %. Dois motores inteiros não cabem em 32 GB.
- Duas filas na mesma placa = **cada uma com a sua pasta de trabalho** (`TANDERA_TRABALHO=/root/trabalho_x1 …`); senão uma
  sobrescreve o bloco da outra. Nunca 2 filas com a peça ovis ao mesmo tempo (17 GB cada).
- Medir na 1ª placa (`nproc`, `nvidia-smi`, memória) antes de dividir. Encher as placas e, se sobrar fila, ligar mais — nunca placa meio vazia.

## 3. Motor no storage, vídeo pelo Drive
- **Variável** (os vídeos): o PC baixa ANTES e sobe pro Drive; a placa puxa do Drive (~80 MB/s; conexão direta ~9 MB/s).
- **Motor**: no storage do RunPod; a placa copia pro disco dela e começa. Ordem: criar o storage → 1ª placa instala o motor nele →
  as outras montam e começam em minutos → no fim, secar.
- Storage é geesefs: `cp -r` (não `rsync -a`); não executa programa → programas reinstalam em cada placa (~3 min); modelos copiados
  pro disco local, nunca lidos direto do storage.
- Storage cheio no meio («Disk quota exceeded») prende item com marca de 0 bytes → apagar `entrada/<id>` dos `.feito` durante o lote.
- rclone com **client_id próprio** (o compartilhado dá 403 e freia a placa); cota de download do Drive estoura → arquivo gigante em um
  fluxo só; pasta recém-compartilhada lista vazia → listar com a conta dona e baixar por `copyid`.
- Lista com o nome REAL do arquivo (`.MP4` × `.mp4`: o rclone pula calado). O lento é a SUBIDA do PC.

### O que a placa não baixa, o PC baixa antes
- O YouTube barra o IP do servidor. Baixar no PC: `yt-dlp --js-runtimes node -N 8 -f "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba"`
  (sem `player_client`: os clientes android/ios passaram a entregar só 360p, calado). Conferir resolução e duração antes de subir.
- Instagram: `yt-dlp -f "b/bv*+ba"`. Sem o `-f` ele pode pegar o fluxo DASH de 360×360 e deixar de lado o progressivo de 720×720
  (que aparece como resolução «unknown»). Conferir com ffprobe também.
- Vídeo de câmera: subir o ORIGINAL 4K (a placa abre uma vez só).

## 4. A máquina e o motor
- Imagem `runpod/pytorch` com Ubuntu 24.04: `pip install --break-system-packages` (PEP 668). `faster-whisper` com `av==13.1.0`.
- Lançador **para no primeiro erro** (`set -e`/`check=True`); nada de «pronto» depois de falha. Temporário do lançador em pasta do
  sistema certo (o `/tmp` do Git Bash não é o do Python do Windows). Script do Windows sai com CRLF: `sed -i 's/\r$//'`.
- Trabalho pesado roda solto (`nohup … < /dev/null`); o PC confere com conexões curtas. `pkill -f <nome>` dentro do ssh mata o próprio
  ssh se o nome estiver no comando. Esperar processo = pelo PID (`kill -0 $PID`), nunca `while pgrep -f nome` (casa consigo mesmo).
- **Órfãos:** reiniciar a fila deixa vivo o `tandera.lote` do bloco (pai = 1) → conferir `pgrep -f 'tandera.lote /root'`.
- **Olho (Gemma):** quadro do ffmpeg em **BMP** (em PNG o OpenCV quebrava dentro do lote, «libpng error: bad parameters to zlib», e o
  quadro vinha vazio); o olho **falha** se um plano ficar sem quadro; 2 planos por vez (`OLHO_PARALELO=2`) com o Ollama em
  `OLLAMA_NUM_PARALLEL=2`. Ver «libpng error» no log = parar e consertar.
- Servidor de modelo que não sobe na Blackwell: procurar o caminho em PyTorch puro do próprio repositório.
- Padrão = bateria de **reconhecimento**; som/profunda só quando pedido. Separação de voz/música/efeitos **nunca em bruto de câmera**
  (só em material mixado). **Ovis em todo lote.** Sem retrabalho: só peça que falta, velha ou falha.
- Peça nova: testar numa placa contra o PC antes do lote; depois de otimizar, conferir que o resultado sai igual.
- Vídeo marcado «gire 90°» aberto pelo chip sai deitado → `-noautorotate` + giro à mão. Foto HEIC: `pillow-heif` no python do sistema.

## 5. Ligar, vigiar, apagar
- API: `POST https://api.runpod.io/v2/pods` (name, image, gpu, disk, ports ["22/tcp"], startSsh, env {PUBLIC_KEY}); listagem e SSH pelo
  GraphQL (`pod { runtime { ports } }`); apagar `DELETE /v2/pods/{id}`. API mudou = ler a doc/`openapi` na hora, sem chutar campo.
- **Vigia sempre ligado com placa no ar**, com **piso de saldo**: ao bater, traz o que foi feito e apaga as placas.
- Vigia que passa a noite roda fora da sessão do chat; conferir 10–15 min depois que o log andou.
- Não gastar o crédito do assistente com análise pesada enquanto há placa no ar: ele tem que sobrar pra vigiar.
- **Secar no fim:** conferir pela API `myself { pods networkVolumes }`; apagar placas e discos criados pra rodada. Exceção: disco fixo de
  motores mantido de propósito numa conta (decidir com o dono; disco parado custa por dia).
- Trazer no fim: lista de arquivos pela entrada do ssh (linha de comando do Windows tem limite), `tar --ignore-failed-read`,
  `MSYS_NO_PATHCONV=1` no Git Bash.

## 6. Custo
- Régua: ~US$ 0,6 por hora de vídeo no reconhecimento; com tudo ligado a PRO 4500 leva ~5× o tempo do vídeo (4K 6×, celular 3×).
  Rodar `--so-contar` antes do lote. Preço de referência (nov/2026): PRO 4500 ~US$ 0,72/h, PRO 4000 ~US$ 0,57/h, A40 ~US$ 0,59/h.

## 7. Segurança
- Chave de API, chave SSH, token do Drive, id de disco, IP e id de conta: nunca em repositório, log público ou chat.
- Login do Drive na placa é feito pelo dono, no próprio servidor (nunca copiar token do PC). Chave de outro serviço na placa só com OK
  do dono e só as variáveis necessárias. Nunca token ou cookie pessoal numa placa.
