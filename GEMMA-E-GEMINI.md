# Gemma × Gemini: quem descreve o que acontece no vídeo

O Tandera mede quase tudo com modelos que rodam na sua máquina (cortes, fala, batida, rótulos do som, texto na tela, o Ovis...). Pra
**descrever com palavras** o que se vê e o que acontece, existem dois caminhos:

| | **Gemma 4 12B** (peça `olho`) | **Gemini Flash** (peça `diario`) |
|---|---|---|
| onde roda | **na sua máquina** (Ollama), ou no RunPod | na nuvem do Google |
| custa | nada (só a sua placa) | os **créditos diários grátis** da sua chave; pago, nunca por padrão |
| precisa de | placa com ~8 GB livres (ou Mac com memória sobrando) e o Ollama | uma chave sua do Google AI Studio |
| o que faz | a FICHA de cada plano: olha 2–3 quadros com o tempo escrito e diz quem, onde, ação, linha do tempo | o DIÁRIO do vídeo inteiro: vê e OUVE (480p com som), falas de ouro, reações, momentos, etiquetas |
| limite | a velocidade da placa | a cota do dia: quando acaba, o diário para até o dia seguinte |

## A regra do time
**A gente usa o Gemma pra substituir o Gemini.** O Gemma roda na sua máquina, não tem chave, nem cota, nem conta pra pagar, e a ficha
dele passa pela mesma régua de sempre. É o padrão: o Tandera chama o `olho` (Gemma) sozinho.

**Mas você pode usar o Gemini pelos créditos diários.** A chave grátis do Google AI Studio dá alguns diários por dia (no PC do Luan, numa
manhã de 03/11/2026, foram uns 10 antes de a cota acabar). O diário do Gemini é o mais rico (ouve o som junto) e é dele que sai a
**busca por frase** (peça `busca`). Pra ligar:
1. Entre em **aistudio.google.com** com a sua conta Google → **Get API key** → crie uma chave num projeto **sem faturamento** (o plano
   grátis, sem cartão). Assim não tem como cobrar: acabou a cota, para.
2. Guarde a chave **só no seu computador**: num arquivo `~/.gemini/chave-api.txt` (no Windows: `C:\Users\<você>\.gemini\chave-api.txt`)
   ou na variável `GEMINI_API_KEY`. **Nunca** num repositório, num chat, numa pasta sincronizada.
3. Pronto: o `diario` entra sozinho nas próximas análises. Ele reveza os modelos Flash que a sua conta tiver; quando a cota do dia
   acaba, ele marca «sem cota» e a próxima rodada (ou a fila da noite) faz o que faltou. Se a sua chave for de um projeto COM
   faturamento, cada diário é cobrado: o Luan nunca usa chave paga no PC.

Sem chave, nada quebra: o `diario` aparece como «falhou: sem chave do Gemini» no `RESUMO.md`, a `busca` (que depende dele) é pulada e
todo o resto roda, com o Gemma descrevendo cada plano.

## E no RunPod?
O perfil `servidor` (Linux) roda o `olho` (Gemma, pelo Ollama da máquina alugada). O `diario` não roda lá: é nuvem, rode no seu
computador com a sua chave (ele só precisa do vídeo em 480p, nada pesado).
