---
name: analise-de-video
description: Analisar vídeo com o motor TANDERA (o manual de uso do Tandera pro Claude). Use SEMPRE que pedirem pra analisar um vídeo, estudar um vídeo de referência («estuda esse vídeo», «analisa esse trailer / esse tutorial / esse corte»), comparar bruto × editado, achar «o momento em que…» no material, medir cortes, fala, batida ou música, decupar bruto, conferir uma geração de IA, medir montagem de gameplay, transcrever com palavra no milissegundo pra sincronizar fala e boca numa troca de voz, ou criar uma skill a partir de vídeos de referência — e ANTES de rodar o Tandera ou de mandar um vídeo pra qualquer modelo descrever. Diz qual pista e bateria ligar, como conferir a saída de cada peça e como concluir sem inventar.
---

# Análise de vídeo com o TANDERA — medir antes de opinar

O Tandera (este repositório) MEDE o vídeo; esta skill diz o que ligar, como conferir e como tirar conclusão. Instalação: `CLAUDE.md`.
Comandos e variáveis: `LEIA-ME.md`. Placa alugada: skill `placa-runpod` + `RUNPOD.md`. Fale com a pessoa em português simples.

## 1. Por que o Tandera, e não «manda o vídeo pro modelo e pede análise»
| mandar o vídeo inteiro pra um modelo | o Tandera |
|---|---|
| o modelo olha poucos quadros por segundo: corte que cai entre dois quadros amostrados some | cada corte no quadro exato (AutoShot + TransNetV2, um conferindo o outro) |
| tempo «mais ou menos»: não dá pra casar corte com palavra ou com batida | cada palavra no milissegundo; batida no ataque; ataques do som a 10 ms |
| escreve o que é PROVÁVEL num vídeo daquele tipo, com a mesma confiança do que viu | cada número vem de uma peça com modelo e versão; o que não foi medido fica «não medido» |
| cada pergunta = mandar o vídeo de novo (custo, cota) e a resposta muda | a análise fica guardada pela assinatura do arquivo; rodar de novo só refaz a peça que mudou |
| um vídeo por vez | o material inteiro buscável (Ovis), lote de centenas de vídeos, checklist do que falta |

Analogia: pedir pro modelo «analisar» é perguntar pra alguém que viu o vídeo em 2× com o som baixo; o Tandera é a régua e o cronômetro.
O modelo que descreve continua lá dentro (peças `diario` e `olho`), mas como UMA peça, conferida contra as medidas — nunca como a verdade.
Cada modelo do motor entrou por teste contra gabarito, não por fama (`tandera/manifesto.py` → `TROCAS`): o detector de corte antigo
perdia 17 de 59 cortes; o tempo de palavra do Whisper sozinho erra ~0,14–0,24 s, e alinhado pelo MMS o começo cai a ~8 ms.

## 2. O que dá pra fazer com o Tandera (os usos reais)
| uso | como (pista · peças) |
|---|---|
| Estudar vídeos de referência e virar skill | a pista do tipo em todos os vídeos → números por vídeo + força da evidência (seção 7) |
| Achar momentos no bruto por frase («o momento em que…») | `bruto` → busca pelo Ovis (vídeo + som de cada 4 s, seção 4) e pelo diário (`buscar`) |
| Decupagem de bruto (o que presta, onde corta) | `bruto` → falas no ms (`tandera.frases`: onde a última palavra acaba de verdade), quem está no quadro, texto, takes emendados, momentos do diário; o caro (`profunda`) só nos takes escolhidos |
| Comparar bruto × editado pra entender um estilo | `bruto` no bruto, `editado` no pronto → casar os dois pela fala no ms e pelo Ovis: o que saiu, o que ficou, onde caiu cada emenda |
| Referência de som (separação, batida, música) | `trailer` ou `editado` com `--bateria reconhecimento,som` — só em material mixado |
| Conferir geração de IA | `--pecas cortes,olho,texto` no shot gerado → a ficha de cada plano contra o roteiro e o prompt (`receitas/COMO-MEDIR-PLEXUS.md`) |
| Montar vídeo de gameplay a partir do bruto | `gameplay` → fala no ms (onde cortar), cortes e texto na tela (lobby, menu, «você morreu», carregamento), Ovis (movimento e busca); sem separação |
| Medir montagem de gameplay | `editado` com `reconhecimento,som` → cortes × fala, a facecam (`rostos`: onde e quando o rosto aparece), pausas com movimento (`sinal`: vãos sem fala × picos de movimento) |
| Transcrever com palavra no ms pra sincronizar fala e boca na troca de voz | `python -m tandera fala <áudio ou vídeo> --palavras --json` (+ `boca` na bateria profunda) |

**Na troca de voz:** a régua é o áudio ORIGINAL do vídeo (onde cada palavra começa e acaba nele), não o áudio novo; olhar a boca no
quadro antes de mexer (fala em off — narração, alguém fora do quadro — não tem boca pra sincronizar); e todo relatório começa pela
COBERTURA: o que foi medido × o que não foi (ex.: «fala: 412 palavras alinhadas · boca: não medida»).

## 3. As peças (uma linha cada; versão e modelo: `python -m tandera versao`)
| peça | o que entrega | bateria |
|---|---|---|
| preparo | abre o vídeo uma vez: duração, fps, giro, folga do AAC, quadros 1/s, cópia 480p, som | reconhecimento |
| cortes | cada corte no quadro exato (+ «possível jump cut» pela diferença de pixel) | reconhecimento |
| fala | cada palavra com começo e fim no ms (Whisper large-v3-turbo + alinhamento MMS + conferência na onda) | reconhecimento |
| entonacao | altura da voz no começo e no fim de cada fala, final subindo ou descendo, sílabas por segundo | reconhecimento |
| texto | o texto que aparece na tela (PaddleOCR) | reconhecimento |
| rostos | rostos 1/s: onde, quem é (digital do rosto), expressão | reconhecimento |
| imagem | retrato de cada quadro 1/s — imagem parecida, busca por frase; SÓ VÊ (SigLIP 2) | reconhecimento |
| som | retrato do som em janelas de 5 s — som parecido; SÓ OUVE (CLAP) | reconhecimento |
| ovis | retrato VÍDEO + SOM de cada trecho de 4 s — a base da busca (seção 4) | reconhecimento |
| sinal | ataques do som, picos de movimento, vãos sem fala, eventos candidatos (conta pura; lê os rótulos, então só sai com a bateria som junto) | reconhecimento |
| diario | o vídeo inteiro descrito, vendo e ouvindo: momentos, falas fortes, etiquetas (Gemini com a chave de quem usa, ou Gemma local: `GEMMA-E-GEMINI.md`) | reconhecimento |
| busca | índice do diário: frase → momento (`python -m tandera buscar <vídeo> "frase"`) | reconhecimento |
| separacao | voz / música / efeitos em faixas separadas (BS-Roformer → BandIt Plus) | som |
| musica | partes da música, subidas, drops, viradas, respiros, energia | som |
| batida | batidas e tempos fortes no ataque; corte × batida, e quanto o acaso daria | som |
| rotulos | etiquetas do som sem a voz a cada 0,5 s: porta, motor, multidão, música… (CED-Base) | som |
| efeitos | qual arquivo da SUA biblioteca de efeitos tocou e onde (só no PC, com a biblioteca indexada) | som |
| camera | a curva do movimento de câmera em cada plano (CoTracker3) | profunda |
| corpo | corpo e fase da repetição em cada plano (Sapiens2) | profunda |
| boca | a boca mexe junto da fala medida? (OpenFace 3.0) | profunda |
| olho | a ficha de cada plano (quem, onde, ação), olhando 2–3 quadros com o tempo escrito (Gemma 4 12B local) | profunda |

Peça sem o peso instalado (`rostos`, `camera`, `corpo`, `boca` e `efeitos` só se instalam a pedido: `MODELOS.md`) sai ✗ no log e em
`falhou` no `RESUMO.md`, e as que dependem dela não rodam. No relatório ela é «não medido», nunca um palpite no lugar.

## 4. O Ovis: o «embedding» do vídeo, e por que ele
- **Embedding** = transformar um trecho numa lista de números (2.048) que funciona como um endereço num mapa: trechos parecidos ficam
  perto. Uma frase também vira endereço no mesmo mapa, então dá pra achar «o momento em que a porta bate e a música para» sem ninguém
  ter escrito isso antes.
- O **Ovis** (Ovis-Omni-Embedding-3B) faz isso a cada 4 s com IMAGEM E SOM JUNTOS, no mesmo tempo (2 quadros/s + o áudio alinhado).
- **Por que ele e não os outros:** o SigLIP (`imagem`) só vê; o CLAP (`som`) só ouve; a `busca` só acha o que o diário escreveu (se o
  modelo que descreveu não anotou, não existe). No teste de 31/10/2026 (achar o momento certo entre os 10 primeiros): Ovis 73,6 % ×
  PE-AV 69 %.
- **Barato** (~0,12 s de máquina por segundo de vídeo): por isso entra em toda pista e em TODO lote. Fazer depois = abrir o vídeo de
  novo; ter o retrato de tudo = o material inteiro buscável. No PC roda em 8 bits (0,991 de semelhança com o bf16); no servidor, bf16.
- **Onde fica:** `pecas/ovis/retratos.npz` (um vetor por trecho, com início e fim em s); `pecas/ovis.json` diz quantos trechos.
  Buscar por frase: `ovis.texto([frase])` (em `tandera/pecas/ovis.py`) põe a frase no mesmo mapa; compare por cosseno com os retratos.
  Também acha o MESMO trecho repetido: o antes × depois de um tutorial, o mesmo take em dois vídeos.

## 5. Pistas (o TIPO de vídeo) e baterias (a FASE)
O motor é um só. A **pista** diz quais peças fazem sentido praquele tipo de vídeo; a **bateria** diz até onde ir agora. Peça desligada
não carrega modelo nem placa. `python -m tandera pistas` lista as pistas.

| bateria | o que liga | custo | quando |
|---|---|---|---|
| **reconhecimento** (padrão) | preparo, cortes, fala, entonação, texto, rostos, imagem, som, ovis, sinal, diário, busca | barata (~0,84 s de máquina por s de vídeo numa RTX 5070) | sempre: é com ela que se escolhe o material |
| **som** | separação, música, batida, rótulos, efeitos | média | só onde existe mixagem (vídeo editado, trailer, episódio). NUNCA em bruto de câmera |
| **profunda** | câmera, corpo, boca, olho | ~10× (~8,8 s por s) | só no material ESCOLHIDO, e só quando alguém pedir |

Junte com vírgula (`--bateria reconhecimento,som`). Sem `--bateria` = só o reconhecimento; aí a «separação» que a fala usa é o próprio
som do vídeo (custo 0).

| pista | quando usar | reconhecimento liga | + som | + profunda |
|---|---|---|---|---|
| `bruto` | material de câmera/celular (e foto), pra catálogo e busca | preparo, cortes, fala, rostos, texto, imagem, som, ovis, diário, busca | nada (bruto não tem mixagem) | câmera, corpo, boca, olho |
| `editado` | vídeo pronto (vlog, cliente, curso) | o mesmo do bruto + entonação | separação, música, batida, rótulos (+ sinal) | as 4 |
| `trailer` | referência de som de outro criador (trailer, reels com sound design) | cortes, fala, ovis | separação, música, batida, rótulos, efeitos (+ sinal) | as 4 |
| `plexus` / `plexus-stems` | episódio do IP de animação da Fly; `-stems` quando vêm as faixas da mixagem (a separação vira as faixas, custo 0) | cortes, fala, ovis | igual ao trailer | as 4 |
| `tutorial` | aula de som de outro criador | 2 passadas sozinhas: fala + texto + rótulos no vídeo inteiro; o pesado (cortes, separação, música, batida, sinal, ovis, olho) SÓ nas janelas de exemplo | — | — |
| `gameplay` | BRUTO de gameplay (jogo + webcam + microfone) pra montagem automática | preparo, cortes, fala, texto, ovis (as pausas pelo volume do microfone a skill de montagem mede) | nada (o som do jogo não precisa ser separado) | olho |
| `kakashi` | gravação do Kakashi (tela + microfone + som do PC já separados) | fala, texto, ovis | rótulos | olho |

**A lógica de cada pista:**
- **Bruto:** a pergunta é «o que tem aqui, e onde?» → quem aparece, o que falam, texto, retratos pra busca. Cortes entram porque bruto
  de celular às vezes vem com takes emendados. Sem mixagem → nada da bateria som (separar voz de bruto é placa jogada fora).
- **Editado:** a pergunta é «como foi montado?» → o reconhecimento inteiro; a bateria som quando a pergunta for música e ritmo. O olho
  fica de fora (o diário já descreve, e o olho é ~metade do tempo de máquina).
- **Trailer / episódio:** o estudo é o SOM → cortes, fala e ovis já no reconhecimento; a bateria som é o coração.
- **Tutorial:** o apresentador fala o tempo todo e a prova está no EXEMPLO (antes × depois). Janela de exemplo = trecho com música
  (rótulo de música ≥ 0,5) ou onde a fala chama o exemplo («listen», «before», «after», «check this out», «here is»).
- **Kakashi:** microfone e som do PC já chegam separados → sem separação, cortes nem batida.
- **Idioma:** `trailer` e `tutorial` assumem inglês; `plexus` e `kakashi`, português. Vídeo em outra língua pede `--idioma pt` (ou
  `en`). Tutorial em português: os chamados de exemplo da fala são só em inglês, então só a música abre janela.
- **Vídeo com vários estilos dentro:** cortar em blocos e tratar cada bloco no seu tipo.

## 6. O método (sempre nesta ordem)
0. **Olhar antes de concluir.** Antes de rodar: qual é a PERGUNTA (quem pediu, pra quê), que tipo de vídeo é, o que a pessoa já disse
   dele. A explicação de quem pediu vem primeiro; a medida confere. O ponto de partida muda a pergunta:
   - só o vídeo pronto → «por que aqui?» (a intenção é hipótese, nunca fato);
   - bruto × editado do mesmo trecho → o que saiu, o que ficou, onde caiu a emenda (a prova mais forte: o corte mostra a decisão);
   - só o bruto → o que acontece e o que vale separar.
1. **Escolher a pista e a bateria** (seção 5). Sempre com `--pista` (ou `--pecas`): `analisar <vídeo>` sem nada roda TODAS as peças
   padrão do manifesto (separação, câmera, olho…), o caro. Ver o que já existe: `python -m tandera onde <vídeo>` e o `analise.json`
   dessa pasta — o que está na versão atual não roda de novo.
2. **Rodar.**
   - **PC** (Windows + NVIDIA): `python -m tandera analisar "<vídeo>" --pista editado --bateria reconhecimento,som --idioma pt`
     (`tandera.cmd` no Windows). Vários: `python -m tandera fila --pista bruto <arquivos ou pastas>`. Sem placa: `--sem-placa` (só
     as leves). Com o Premiere aberto o motor recusa a placa; um trabalho pesado por vez.
   - **RunPod** (sem placa forte, ou lote grande): ler a skill `placa-runpod` ANTES de qualquer comando e seguir o `RUNPOD.md`
     (montar o lote → enviar → preparar → rodar → trazer). No `servidor/montar_lote.py`, mande as peças da pista com `--pecas`: as
     receitas do `servidor/receitas.json` ainda não trazem o `ovis`. Dizer o preço e esperar o «pode» de quem paga. A análise volta e soma.
   - **Vídeo em 1080p** (ou a resolução máxima dele), conferido no `ffprobe`: em 360p o texto e o olho não servem.
3. **CONFERIR a saída de cada peça — o ✓ não prova nada.** O ✓ no log só diz que a peça terminou (já aconteceu de o olho sair ✓ sem
   imagem nenhuma por horas). Abrir `analises/<nome>_<assinatura>/pecas/<peça>.json` e checar:

   | peça | sinal de que funcionou |
   |---|---|
   | preparo | `fps`, `rotacao_metadado` e `folga_aac_s` com valor: o resto da conta depende deles |
   | cortes | `cortes` em número plausível pra duração; abrir 2–3 no quadro |
   | fala | `palavras` com texto e tempo, em quantidade compatível com o quanto se fala; `descartados` pequeno |
   | separacao | `stems` apontando pros wav; ouvir 5 s da voz e do resto |
   | ovis | `trechos` ≈ duração ÷ 4, e o `pecas/ovis/retratos.npz` existe |
   | texto | `itens` nos momentos em que há texto na tela |
   | olho | cada plano com `quadros` (as imagens em `pecas/olho/`) e `texto` não vazio: abrir 2 quadros e ler 2 fichas |

   E o `RESUMO.md` (peça · versão · tempo · placa). Peça vazia ou estranha = refazer SÓ ela (`--refazer <peça>`), não o vídeo inteiro.
4. **Calibrar antes de comparar tempos.** Quadro pelo NÚMERO (no ffmpeg, `-ss (F − 0,5)/fps` dá o quadro F); som em AAC chega ~21 ms
   atrasado (a `folga_aac_s` do preparo); take gravado em pé pode estar deitado no arquivo; tempo de fala SEMPRE pelas palavras
   alinhadas (`tandera.frases(A)`), nunca pelo segmento do Whisper.
5. **Ler as fichas** — o `RESUMO.md`, a ficha de cada plano (olho), o diário — e, antes de afirmar qualquer coisa visual, ABRIR o
   quadro. Todo «falta X» do olho pode ser só a amostragem; movimento de câmera vale pela curva medida, não pelo que o olho diz; o que
   o diário e o olho escrevem é pista, não fato.
6. **Só então concluir**, citando tempo e quadro (`q186 · 0:07.75`) e separando **MEDIDO** (número do Tandera) · **LEITURA** (a sua
   interpretação) · **PERGUNTA** (o que só a pessoa sabe). O que não está na análise não foi medido: «não medido (a peça X mediria)».
   Coincidência existe: corte em cima da batida só diz algo quando comparado com o acaso (a peça `batida` faz essa conta).

## 7. De vídeos de referência a uma skill
1. **Pergunta e tipo primeiro:** uma skill por tipo de vídeo ou estilo (trailer não ensina vlog). Vídeo misturado = blocos.
2. **Mesma pista, mesma bateria, mesmas versões de peça** em todos os vídeos (o `analise.json` guarda a versão de cada peça); senão os
   números não se comparam.
3. **Medir números por vídeo, não impressões:** duração dos planos (mediana e faixa), cortes por minuto, corte → palavra e corte →
   batida (ms, e quanto o acaso daria), quanto a música abaixa sob a voz, vãos sem fala, quantas vezes entra texto, quanto a câmera
   anda. Sempre com o n de vídeos e a faixa, não só a média.
4. **Força da evidência = em quantos vídeos aparece, no mesmo contexto** (escala proposta; quem decide o que é regra é o dono do estilo):

   | aparece em | vira |
   |---|---|
   | 1 vídeo | CASO (com o contexto e o tempo) |
   | alguns, não a maioria | INDÍCIO / «depende» — e o «depende» é informação: dizer de quê |
   | a maioria, no mesmo contexto | PADRÃO candidato |
   | todos, e confirmado por quem é dono do estilo | REGRA |

5. **Regra × caso único:** o que mudou junto com o contexto (cena, música, pessoa, plataforma) é caso, por mais bonito que seja. Nunca
   cortar o «às vezes» nem o «geralmente» de uma fala.
6. **Testar a tese no próximo:** escrever a regra com N−1 vídeos e ver se ela prevê o vídeo que ficou de fora. Não previu = não é regra.
7. **O que os dados NÃO permitem concluir:** a INTENÇÃO (a medida diz quando, não por quê: vira hipótese e pergunta); que algo
   «funciona» ou dá audiência (sem comparação controlada); que vale pra todo criador (vale pros vídeos medidos); nada do que não foi
   medido; e descrição de modelo (olho, diário) não é prova.
8. **Formato de cada regra na skill nova:** a regra · o número medido · em quantos de quantos vídeos · o contexto em que vale · um
   exemplo com tempo (`vídeo · 0:12.40`) · a força. Molde: `receitas/MODELO-DA-RECEITA.md`; exemplo: `receitas/COMO-MEDIR-PLEXUS.md`.

## 8. O que não fazer
- Mandar o vídeo pra um modelo e chamar a resposta de análise; concluir por uma miniatura ou por um quadro só.
- `analisar` sem `--pista`/`--pecas` (roda tudo); bateria som em bruto de câmera; profunda «por garantia» em tudo (10× o custo).
- Lote sem o Ovis.
- Refazer o que já está guardado na versão atual, ou apagar a análise pra rodar de novo (use `--refazer <peça>`).
- Acreditar no ✓ sem abrir a saída.
- Medir no som misturado o que precisa da faixa certa (risada, música parando, silêncio da fala): sem a separação, «não medido».
- Pôr intenção na boca do criador; transformar um caso em regra.
- Escrever um script de análise próprio ou um «Tandera paralelo»: melhoria de peça entra no motor (`tandera/manifesto.py`) — abra uma
  *issue*.
- Ligar placa paga sem dizer o preço e ouvir o «pode»; chave no chat ou em repositório.
- Rodar na placa com o Premiere aberto, ou dois trabalhos pesados ao mesmo tempo.
