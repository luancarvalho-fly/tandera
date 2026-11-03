# Tandera — exemplo-sintetico.mp4

- vídeo: `exemplo-sintetico.mp4`
- análise guardada: `<temporária>\analises\exemplo-sintetico_3d36520a103f`

| peça | modelo | versão | perfil | onde | tempo | placa (pico / a peça somou) | quando |
|---|---|---|---|---|---|---|---|
| preparo | ffmpeg (-noautorotate + transpose à mão; select periódico > 60 s; saíd | 2026-11-01 | pc | cpu | 0.6 s | — | 2026-11-02 01:50:13 |
| cortes | AutoShot (onnx do CUTX, limiar 0,296) + TransNetV2 (transnetv2-pytorch | 2026-11-01 | pc | placa | 10.9 s | 8.41 / +-0.0 GB · 2% | 2026-11-02 01:50:26 |
| separacao | entregue pronta (musica, resto, voz): musica.wav · musica.wav · voz.wa | entregue-bcc10fed11 | pc | placa | 0.2 s | 8.35 / +-0.0 GB · 2% | 2026-11-02 01:50:26 |
| fala | Whisper large-v3-turbo (faster-whisper fp16; sem VAD; só os trechos CO | 2026-11-01c | pc | placa | 10.8 s | 8.36 / +0.01 GB · 2% | 2026-11-02 01:50:37 |
| entonacao | Praat (parselmouth) | 2026-10-18 | pc | cpu | 0.2 s | — | 2026-11-02 01:50:37 |
| batida | Beat This! (final0) + ataque na onda + grade reta ajustada | 2026-10-20 | pc | placa | 9.6 s | 8.37 / +-0.0 GB · 2% | 2026-11-02 01:50:47 |
| musica | medidor de música (Beat This! + librosa: matriz de semelhança, sem mod | 2026-10-19 | pc | placa | 12.0 s | 8.37 / +0.02 GB · 4% | 2026-11-02 01:50:59 |
| rotulos | CED-Base (mispeech/ced-base, AudioSet 527) — melhor etiquetador do tes | 2026-11-01 | pc | placa | 17.7 s | 8.46 / +0.17 GB · 6% | 2026-11-02 01:51:17 |
| sinal | conta pura (fluxo espectral com limiar local; diferença de quadro); co | 2026-11-01 | pc | cpu | 0.6 s | — | 2026-11-02 01:51:18 |

## Rodadas
| quando | perfil | rodou | guardada | falhou | pulou | tempo |
|---|---|---|---|---|---|---|
| 2026-11-02 01:50:13 | pc | preparo, cortes, separacao, fala, entonacao, batida, musica, rotulos, sinal | — | — | — | 65 s |
