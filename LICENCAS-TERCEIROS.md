# Licenças do que vem DENTRO desta pasta (de terceiros) — 02/11/2026

Peso de modelo não vem (só o AutoShot, que não tem fonte oficial); o resto se baixa da fonte (lista e licenças: `MODELOS.md`).

## AutoShot — `modelos/autoshot.onnx` (34,0 MB)
Origem: github.com/wentaozhu/AutoShot (artigo: "AutoShot: A Short Video Dataset and State-of-the-Art Shot Boundary Detection", CVPR 2023
Workshops). Peso `ckpt_0_200_0.pth` (o dos autores; cópia do espelho huggingface.co/backseollgi/AutoShot, que não declara licença no
cartão), convertido pra ONNX (mesma saída do PyTorch até 0,000003) por Luan Carvalho, sem treinar nem mudar nada.

```
MIT License

Copyright (c) 2023 Wentao Zhu

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Music-Source-Separation-Training (msst) — `terceiros/separador-cinema/msst/`
O código que roda o BandIt Plus (peça «separacao»): github.com/ZFTurbo/Music-Source-Separation-Training, commit 2ba884c, sem `docs/`,
`tests/` e `gui/`. **MIT**, Copyright (c) 2024 Roman Solovyev (ZFTurbo) — o texto inteiro está em `msst/LICENSE`.
A config `modelos-teste/bandit_plus/config_dnr_bandit_bsrnn_multi_mus64.yaml` é a da release v.1.0.3 do mesmo repositório (o peso
`model_bandit_plus_dnr_sdr_11.47.chpt` NÃO vem: baixar de lá e pôr na mesma pasta). O BandIt original (kwatcharasupat/bandit) é Apache-2.0.

## `terceiros/separador-cinema/modelos-teste/bancada/rodar_msst_stub.py`
Do Luan (Fly): roda o `msst/inference.py` com «stubs» das bibliotecas que o código do BandIt só usa pra treinar. Uso interno da Fly.

## AdaFace — `modelos/adaface/net.py`
A rede IR-101 do AdaFace (peça «rostos»), do repositório github.com/mk-minchul/AdaFace (licença do código: MIT — o texto está no
repositório). O peso `adaface_ir101_webface12m.ckpt` (1,53 GB) NÃO vem.
