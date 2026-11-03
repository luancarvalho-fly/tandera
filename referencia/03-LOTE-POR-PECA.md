# O Tandera em LOTE: cada modelo carregado UMA vez por bloco (01/11/2026)

> Versão limpa do relatório de 01/11 (`RELATORIO-LOTE.md` no PC dele): nomes de cliente viraram o TIPO do vídeo. Prova no WSL (RTX 5070).
> O lote é o `tandera/lote.py` + `servidor/rodar_lote.py --bloco N` (padrão 12). No computador de cada um (um vídeo) nada muda.

1. **1,6× mais rápido na prova:** 7 vídeos (822 s) levaram **1.364 s vídeo por vídeo × 852 s em lote** = 1,66 → 1,04 s de máquina por s
   de vídeo (−38%).
2. **O resultado saiu IGUAL byte a byte** (cortes, palavras no ms, batidas, rótulos, sinal, texto, Ovis com cosseno 1,000 e até o texto do
   olho/Gemma, que tem semente fixa). E bate com a análise feita ANTES da mudança.
3. **O carregar pesava ~41% do tempo** no jeito antigo (~565 de 1.364 s); no lote caiu pra ~19% (164 s); num bloco de 12, ~116 s por bloco.
4. **O PC não mudou:** o V009 com stems no Windows continua «6 guardadas, 0 s».

## Peça por peça (7 vídeos, 822,3 s; «antes» = `--bloco 0`, um `tandera analisar` por vídeo; «lote» = blocos de 4 e 3)
| peça | onde | antes (s) | antes s/s | lote (s) | lote s/s | carregar no lote |
|---|---|---|---|---|---|---|
| preparo | processador | 62,0 | 0,075 | 146,3* | 0,178* | — (roda AO LADO da placa, já no próximo bloco) |
| cortes | placa | 257,9 | 0,314 | 125,2 | 0,152 | 4,4 s |
| separação | placa | 186,0 | 0,226 | 147,6 | 0,179 | ~77 s (2 × ~38 s) |
| fala | placa | 94,8 | 0,115 | 45,8 | 0,056 | 8,4 s |
| batida | placa | 12,0 | 0,015 | 10,1 | 0,012 | 0,8 s |
| música | placa | 13,9 | 0,017 | 12,0 | 0,015 | 0,4 s (o mesmo Beat This! da batida) |
| rótulos | placa | 14,1 | 0,017 | 9,4 | 0,011 | 3,4 s |
| sinal | processador | 75,9 | 0,092 | 130,7* | 0,159* | — (ao lado da placa) |
| texto | placa | 96,6 | 0,117 | 80,9 | 0,098 | 17,1 s |
| ovis | placa | 53,2 | 0,065 | 46,7 | 0,057 | 11,5 s |
| olho | placa | 460,9 | 0,561 | 310,0 | 0,377 | 40,8 s |
| **parede (o que se paga)** | | **1.364,1** | **1,659** | **852,4** | **1,037** | |
\* no lote o preparo e o sinal dividem os núcleos com o preparo do próximo bloco: cada um demora mais, mas não soma na parede.

Vídeos: 3 vlogs do Plexus com stems (72–80 s), 2 trechos de 2 min de tutorial 4K AV1 (com olho), 1 trailer vertical (75 s) e 1 sessão do
Kakashi (4,7 min, tela 1080p a 5 q/s, `fala.wav` + `pc.wav` como stems).

## O que pesa
- Do trabalho de placa, o maior é **o olho: 269 s, 43%** (só em 3 dos 7 vídeos; 0,91 s/s no tutorial). Depois a separação pelo modelo
  (~0,21 s/s), o Ovis (0,14), os cortes (0,13, quase tudo abrindo o 4K AV1: a placa fica em 12%) e o texto (0,10).
- O que o lote piorou: com o preparo do próximo bloco e o sinal ao lado, as peças que dependem do processador ficaram mais lentas por
  vídeo. `--preparo-juntos` (padrão 3) pode baixar se pesar.

## Custo previsto de um inventário grande (~36 h de vídeo, a maior parte tutorial; RTX PRO 4500 a US$ 0,74/h)
| cenário | máquina (h) | US$ |
|---|---|---|
| vídeo por vídeo, régua da 5070, tudo em fila | 48,1 | 35,6 |
| lote, régua da 5070 | 36,0 | 26,6 |
| **lote, previsto no RunPod** (fator 1,7× só na parte em que a placa trabalha) | **29,6** | **21,9** |
| teto do lote | 42,9 | 31,8 |
Quem decide o custo é o tutorial longo, e dentro dele o olho. Duas máquinas = metade do tempo, mesmo custo. Fora da conta: o storage de
rede e o envio pela internet.

## O que mudou no código (o «O que não mudou» também importa)
`tandera/lote.py` (novo: peça por peça, com a MESMA regra de decidir e de guardar do `motor.rodar()`); `tandera/base.py` (`SEGURAR`,
`segurado()`, `largar`, `soltar_segurados`: fora do lote `segurado()` só chama o `carregar()`); as peças cortes, fala, batida, música,
rótulos, texto, ovis, olho e separação ganharam `aquecer` / modelo segurado; `servidor/rodar_lote.py` (`--bloco 12` padrão; o processador
prepara o PRÓXIMO bloco; `tandera.lote` num processo por bloco); `servidor/montar_lote.py` (lê o `receitas.json`). **Não mudou:**
`motor.py`, `armazem.py`, `manifesto.py` (nenhuma versão de peça mudou), `__init__.py`, `__main__.py`.

## Achados
1. O tempo da peça que roda ao lado saía errado (do envio até o fim do bloco): consertado antes da prova (soma de cada vídeo).
2. As sessões do Kakashi do PAINEL do Premiere não têm `fala.wav` (têm `audio.wav` + `pc.wav`): a receita `kakashi` (voz = `fala.wav`) só
   serve pras do gravador do PC. Não mexi na receita.
3. O olho no Kakashi gera 1 ficha por sessão (tela sem corte = 1 plano): custa pouco e diz pouco.

## O que NÃO foi provado
A máquina real do RunPod em blocos (o piloto, `04`, rodou vídeo por vídeo); blocos de 12 (a prova usou 4 e 3); uma máquina morrendo no meio
de um bloco; duas máquinas dividindo a fila em blocos.
