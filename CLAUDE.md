# Pro Claude que abriu este repositório: como instalar e usar o TANDERA

Este é o **TANDERA**, o motor de análise de vídeo e som da Fly (do Luan Carvalho). Quem te mandou aqui quer, quase sempre, "instala o
Tandera" ou "analisa este vídeo". Fale em português simples: a maioria do time edita vídeo, não programa. **Um passo de cada vez, e
peça o OK antes de instalar qualquer coisa** (são GBs de modelos; permissão do sistema é a pessoa que clica).

## 0. Leia antes
- `LEIA-ME.md` — o manual do motor (a lei: UM motor, sempre o mais novo; como usar; as variáveis `TANDERA_*`).
- `MODELOS.md` — cada modelo: fonte oficial, tamanho, licença.
- `GEMMA-E-GEMINI.md` — quem descreve o vídeo (Gemma local = o padrão; Gemini = opcional, com os créditos diários da chave da pessoa).
- `RUNPOD.md` — pra quem não tem placa NVIDIA.

## 1. Qual caminho (decida com a pessoa, depois do PC check)
Rode `py -3 pc_check.py` (Windows; só LÊ o PC) e explique o resultado. Então:

| a máquina dela | o caminho |
|---|---|
| **Windows + NVIDIA com 8 GB ou mais** (N2) | instalação completa no PC (seção 2). 12 GB+ roda tudo; 8 GB roda tudo, mais devagar (uma peça por vez). |
| **Windows sem NVIDIA, ou NVIDIA < 8 GB** (N0/N1) | as peças leves no processador (`--sem-placa`: cortes, fala, batida, música, rótulos, sinal, texto) + o pesado no **RunPod** (`RUNPOD.md`). |
| **Mac** | em porte (`MAC.md`): o motor roda no processador do Mac (`--sem-placa`) com um ambiente sem CUDA; o pesado vai pro RunPod. Diga que é experimental. |
| **Linux + NVIDIA** | o `servidor/preparar_tandera.sh` é a instalação (é o que o RunPod usa). |

## 2. Instalação completa no Windows + NVIDIA
Pergunte onde instalar (sugestão: `%LOCALAPPDATA%\Programs\Tandera-Fly`; precisa de ~60 GB livres: ~45 GB de modelos + ~15 GB de ambientes) e clone lá:
`git clone https://github.com/luancarvalho-fly/tandera "<pasta>"` (sem git: Code → Download ZIP e extrair). Tudo abaixo é DE DENTRO
dessa pasta.

1. **Programas:** Python **3.12** (`winget install Python.Python.3.12`), ffmpeg (`winget install Gyan.FFmpeg`), o driver NVIDIA em dia
   (CUDA 12.8+: o `nvidia-smi` mostra). Ollama pro `olho`: `winget install Ollama.Ollama`.
2. **Ambiente principal** (`.venv`, torch com CUDA 12.8):
   ```
   py -3.12 -m venv .venv
   .venv\Scripts\python -m pip install uv
   .venv\Scripts\python ambiente\instalar.py
   ```
   O log fica em `ambiente\instalar.log` (leia o fim: cada passo diz `-> código 0`).
3. **Os ambientes separados** (as bibliotecas brigam entre si; versões EXATAS em `servidor\requisitos\`):
   ```
   .venv\Scripts\python ambiente\instalar.py --ocr
   .venv\Scripts\python -m uv venv --python 3.12 .venv-sep
   .venv\Scripts\python -m uv pip install --python .venv-sep\Scripts\python.exe -r servidor\requisitos\sep.txt --extra-index-url https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match
   .venv\Scripts\python -m uv venv --python 3.13 .venv-cine
   .venv\Scripts\python -m uv pip install --python .venv-cine\Scripts\python.exe -r servidor\requisitos\cine.txt --extra-index-url https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match
   ```
   (`.venv-ocr` = texto na tela · `.venv-sep` = separação BS-Roformer · `.venv-cine` = separação BandIt.)
4. **Os pesos** (o `MODELOS.md` tem a fonte de cada um): os do Hugging Face e do torch.hub baixam sozinhos na 1ª análise. À mão:
   - BandIt Plus: `model_bandit_plus_dnr_sdr_11.47.chpt` da release **v.1.0.3** de github.com/ZFTurbo/Music-Source-Separation-Training →
     `terceiros\separador-cinema\modelos-teste\bandit_plus\`.
   - CED-Base (rótulos): `.venv\Scripts\python -c "from huggingface_hub import snapshot_download as s; s('mispeech/ced-base', local_dir=r'pesos\ced-base')"`.
   - Gemma 4 (olho): `ollama pull gemma4:12b` (~8 GB).
   - As peças que NÃO são padrão (`camera`, `corpo`, `boca`, `rostos`, `pisada`, `efeitos`) têm pesos e repositórios próprios
     (`MODELOS.md`); só instale se a pessoa pedir essas peças.
5. **Gemini (opcional):** pergunte se ela quer o diário do Gemini com os créditos diários grátis; se sim, siga o `GEMMA-E-GEMINI.md`
   (a chave fica SÓ no computador dela; nunca peça pra ela colar a chave no chat).
6. **Prova** (o vídeo de resultado conhecido, 12 s, ~1 min):
   ```
   tandera.cmd versao
   tandera.cmd analisar exemplo\sintetico\exemplo-sintetico.mp4 --pecas cortes,fala,entonacao,batida,musica,rotulos,sinal --stem voz=exemplo\sintetico\voz.wav --stem musica=exemplo\sintetico\musica.wav --idioma pt --sem-placa
   .venv\Scripts\python exemplo\comparar.py "<a pasta que ele imprimir no fim>" exemplo\sintetico\resultado-pc-processador
   ```
   Tudo IGUAL ou PERTO = instalado certo. Depois rode de novo SEM o `--sem-placa` pra provar a placa.

## 3. Usar
`tandera.cmd analisar <vídeo>` (as peças padrão; só roda o que falta ou mudou) · `--pista <nome>` (as receitas prontas:
`tandera.cmd pistas` lista) · `checklist --somar <pasta> --grupo G --pista P` (a lista do que analisar) + `fila --checklist --ate 08:30` (roda a lista em
blocos, ex. de madrugada, só o que falta) · o resto no `LEIA-ME.md`.
A análise de cada vídeo fica em `analises\<nome>_<assinatura>\` com um `RESUMO.md` legível.

## Regras
- **Placa: um trabalho pesado por vez.** Não rode o Tandera na placa com o Premiere aberto (o Tandera recusa sozinho no Windows).
- **Nada de chave, senha ou token** no repositório, no chat ou em pasta sincronizada.
- **Dinheiro:** RunPod e Gemini pago custam. Diga o preço antes e espere o «pode».
- **Melhoria de peça** volta pro Luan (o motor é um só): não crie um Tandera paralelo. Abra uma *issue* ou mande um Kakashi.
