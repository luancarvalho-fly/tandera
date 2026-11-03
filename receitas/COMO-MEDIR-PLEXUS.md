# Como medir: o exemplo do PLEXUS (a receita do Luan) no Tandera único

Ele (21/10): «Aí você dá o exemplo do Plexus». O Plexus é a série de animação gerada por IA da Fly (o E.T. Plexus): é FICÇÃO, tudo é
gerado, então o vídeo segue o roteiro à risca («Plexus é ficção, Luan é vida real»). Esta é a receita que ele montou (20/10), já
traduzida pros nomes das peças do motor único (`python -m tandera versao`). A sua receita vai ser outra: use `MODELO-DA-RECEITA.md`.

## A ideia: a régua é universal, a receita é de cada um
O Tandera MEDE (em que quadro corta, em que milissegundo cada palavra começa, onde cai a batida, o que está escrito na tela, como a câmera
anda). A receita diz o que olhar, em que ordem e pra quê — e é da PESSOA. No motor, receita = **quais peças ligam** («um motor só...
você sabe quando desligar e ligar um pistão»): peça desligada não carrega modelo nem placa, e a análise fica guardada por arquivo — se
outra receita pedir o mesmo vídeo depois, só roda a peça que falta.

**A EXPLICAÇÃO DA PESSOA VEM PRIMEIRO; a medida confere.** O que ela diz que o vídeo é e o que ela quer saber é o centro. Do estudo da
régua: «o contexto é o parâmetro mais importante» — medida sem contexto pergunta errado.

## Regra que vale pra tudo no Plexus: o ROTEIRO é a bússola
«Sempre com o roteiro na mão.» Toda leitura é conferida contra ele. Provado no teste T2 (outubro): com o trecho do roteiro junto, o
modelo dá nome a quem só o roteiro nomeia, MAS só quando a imagem confirma, e aponta onde o vídeo DIFERE do roteiro, sem copiar.

## Antes de rodar: o briefing (1 linha) = estágio + pra quê
| estágio | a pergunta | peças que ligam |
|---|---|---|
| **A. Geração solta** (um shot que saiu do gerador) | "Deu certo? Se não, o que mudar: no PROMPT, no ROTEIRO ou nos dois?" | `cortes`, `olho` (a ficha de cada plano), `texto` · + o traçado ficha × roteiro × prompt (é o Claude que faz, lendo a ficha). Sem som |
| **B. Montando** | montagem e storytelling | `cortes`, `fala`, `camera`, `olho` (+ a visão geral prevista pelo roteiro) |
| **C. Montado** | sonoplastia e sound design: «o entre-cenas conta muito» | a pista de som: `cortes`, `separacao`, `fala`, `entonacao`, `batida`, `musica`, `rotulos`, `sinal` (+ `efeitos` se houver uma biblioteca de efeitos indexada) |

Comandos (de dentro da pasta do Tandera):
```
python -m tandera analisar "<shot.mp4>" --pecas cortes,olho,texto --idioma pt                          (A)
python -m tandera analisar "<montado.mp4>" --pecas cortes,fala,camera,olho --idioma pt                 (B)
python -m tandera analisar "<montado.mp4>" --pecas cortes,separacao,fala,entonacao,batida,musica,rotulos,sinal --idioma pt   (C)
python -m tandera analisar "<montado.mp4>" --stem voz=VOZ.wav --stem musica=MUSICA.wav --stem efeitos=SFX.wav --pecas ...    (C com os stems da mixagem)
```
Com os stems da mixagem (voz, música, efeitos que vieram do projeto), a separação não roda (custa 0) e a fala sai da voz limpa. No
lote do servidor isso é a receita `plexus-stems` (`servidor/receitas.json`), e o `servidor/stems.py` soma as faixas de cada papel
(`[VOZES_MIXADO]`, `[MUSICAS_MIXADO]`, `[SFX_MIXADO_n]`...) num wav só, igual byte a byte no Windows e no Linux.

## A ficha do shot (estágio A e B)
- O olho (`olho`: Gemma 4 12B no Ollama) vê 2–3 quadros POR PLANO (pelos cortes medidos, inclusive nos planos curtos), com o NÚMERO, o
  TEMPO e o QUADRO escritos no canto, e a fala medida do plano junto (só pra saber QUANDO alguém fala). Quadros espaçados por igual
  pulavam um plano de 1 s e geravam "falta" falso (teste T2).
- O que vai junto na pergunta (o Claude monta): o trecho do roteiro; a **ficha do elenco** (todos os assets ligados ao shot na geração,
  com foto + nome + altura numa imagem só: com ela, a nave Feriado sai pelo nome — T1); o prompt.
- **Sempre conferir no olho:** todo "FALTA" (pode ser só a amostragem) e todo "boca aberta = fala" (o roteiro empurra pra "falando").
- **Câmera:** nenhum modelo de visão acerta sempre → vale a CURVA medida (`camera`: CoTracker3), não o que o olho diz.

## A ficha sonora (estágio C)
Junta tudo com o roteiro e o jeito de quem edita, olhando o ENTRE-CENAS: música de fundo da geração que precisa sair; mesmo lugar = mesma
cama; J-cut e reverb de quem está no mesmo lugar; fala que acaba antes da imagem e precisa de costura. O que ajuda: `sinal` (ataques do
som sem a voz a 10 ms, picos de movimento, vãos sem fala ≥ 0,4 s, eventos candidatos com as etiquetas do CED), `batida` (corte ×
batida: quantos cortes caem no quadro da batida e quanto o acaso daria), `tandera.frases(A)` (cada frase no milissegundo: onde a
última palavra acaba de verdade).

## Como responder (vale pra qualquer receita)
- Comece pelo que a pessoa perguntou, com a explicação dela como norte; depois a medida que confirma ou contradiz (diga qual).
- Cite o quadro e o tempo (`q186 · 0:07.75`). Antes de afirmar algo visual, ABRA o quadro (o olho grava os dele em `pecas/olho/`).
- Separe: **MEDIDO** (número do Tandera) · **LEITURA** (a sua interpretação) · **PERGUNTA** (o que só a pessoa sabe).
- O que não está na análise não foi medido. Nunca preencha: diga "não medido" (e qual peça mediria).
