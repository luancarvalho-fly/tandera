# -*- coding: utf-8 -*-
"""DIÁRIO: o Gemini Flash assiste o vídeo INTEIRO (cópia 480p, imagem E som) e devolve o diário em JSON — o MESMO pedido do catálogo
(gemini_pedido.py do servidor, que fez os diários dos 682 clipes), pra busca e catálogo lerem igual. O diário é o 1º objeto JSON da
resposta (raw_decode: às vezes o Gemini escreve mais alguma coisa depois e o json.loads recusava tudo).
  PC       = chave GRÁTIS do AI Studio (~\\.gemini\\chave-api.txt DE QUEM USA; decisão do Luan: pago nunca no PC; a chave nunca vem no pacote), revezando os Flash na cota
  servidor = chave da Fly (GEMINI_API_KEY), gemini-3-flash-preview (o motor do catálogo)
A chave nunca é mostrada."""
import json, os, time, urllib.error, urllib.request

from .. import base

API_G = "https://generativelanguage.googleapis.com"
PEDIDO = """Você é o decupador de uma produtora (Fly) catalogando BRUTO de vlog (vídeo de celular). Assista o vídeo INTEIRO, imagem E SOM.
Escreva tudo em português; falas literais ficam na língua em que foram ditas. NÃO invente nome de pessoa nem de lugar que não esteja dito
ou escrito no vídeo (se não sabe, diga "não dá pra saber"). Tempos sempre em m:ss.

Responda SÓ um JSON com:
{
 "resumo": "2 a 4 frases do que acontece",
 "linha_do_tempo": [{"de": "m:ss", "ate": "m:ss", "ve": "o que se vê (ação, quem faz o quê)", "ouve": "o que se ouve além da fala: palmas, risada, grito, aplauso, buzina, motor, música, fogos, silêncio... ou vazio"}],
 "falas_de_ouro": [{"t": "m:ss", "fala": "literal", "por_que": "engraçada / forte / reação / piada / xingamento"}],
 "pessoas": {"quantas": "...", "como_sao": "... inclua a ROUPA de cada um (cor, estampa, camisa de time, fantasia, uniforme)", "quem_fala_com_a_camera": "..."},
 "reacoes": [{"t": "m:ss", "quem": "descrição", "expressao": "rindo / desconfiado / surpreso / com medo / bravo / emocionado / entediado ..."}],
 "momentos_aproveitaveis": [{"de": "m:ss", "ate": "m:ss", "tipo": "melhor reação / engraçado / clímax / b-roll bonito / olhar pra câmera / abertura", "por_que": "..."}],
 "lugar": {"onde_parece": "...", "dia_ou_noite": "...", "evento": "...", "data_comemorativa": "... ou nenhuma"},
 "camera_e_qualidade": {"tipo": "selfie / POV / drone / tripé / na mão ...", "problemas": ["tremido / escuro / estourado / vento no áudio / fala abafada ..."]},
 "escrito_e_marcas": ["placas, logos, telas, roupa com marca; CAMISA DE TIME ou de seleção: diga o time pelo nome quando der pra reconhecer (ex.: 'camisa do Flamengo, listrada rubro-negra'), com o m:ss em que aparece"],
 "energia": {"curva": "ex.: calmo → caótico", "pico": "m:ss"},
 "etiquetas": ["15 a 30 palavras-chave em português E inglês"],
 "ideias_de_uso": ["2 ou 3"]
}"""
# SENSÍVEL = só quando a pista pedir (ctx.sensivel). Ele, 03/11 ~09h: «isso no Plex[us] não precisa, só pro GAXTANDO futuramente».
# É o pedido do catálogo de 01/11 (Kakashi 16:37: «todos os brutos novos... entender se tem alguma coisa sensível... não devem ficar
# em público»; critérios confirmados por ele no mesmo dia, «na dúvida, trava»). Os 14 diários da madrugada de 03/11 saíram COM o campo
# (o pedido padrão teve ele por umas horas): o resto do diário é o mesmo pedido, então ficam valendo, sem refazer.
PEDIDO_SENSIVEL = PEDIDO.replace('\n "ideias_de_uso": ["2 ou 3"]\n}', '''
 "ideias_de_uso": ["2 ou 3"],
 "sensivel": {"tem": true/false, "trechos": [{"de": "m:ss", "ate": "m:ss", "tipo": "investimento / estrategia / contrato / dinheiro / negocio_terceiros / dado_pessoal / racismo / homofobia", "o_que": "1 frase, sem repetir número, valor ou dado pessoal"}]}
}
"sensivel" = o que NÃO pode ir a público: conversa sobre rodada de investimento ou estratégia da empresa, contrato, dinheiro e números
(faturamento, valor, cachê, salário), negócio com cliente/parceiro/patrocinador, dado pessoal aparecendo (documento, senha, endereço,
telefone, conversa de celular na tela), piada ou fala racista ou homofóbica. Na dúvida, marque "tem": true.''')
assert "sensivel" in PEDIDO_SENSIVEL and "sensivel" not in PEDIDO


class SemCota(RuntimeError):
    """a cota grátis do Gemini acabou em TODOS os Flash: não adianta tentar de novo até ela voltar (madrugada de 03/11: 19 diários
    gastaram ~5 min cada pra ouvir 429 de todos). Fica marcado: os próximos diários do mesmo processo falham na hora."""


_SEM_COTA = [0.0]          # até quando (time.time()) não vale tentar
# 03/11 de manhã: o gemini-3.8-flash da chave grátis passou a segurar a resposta até o tempo limite (15 min) — a 1ª tentativa dos
# 19 diários morreu assim. Desiste em 7 min e passa pro próximo Flash da lista (um vídeo de 11 min responde em ~4–5 min quando anda).
ESPERA_S = 420

# 01/11 (Luan: «a gente quer um filtro pra fotos... entender quem tá nas fotos, o que que tá fazendo na foto»): a FOTO responde no MESMO
# formato do diário do vídeo, com a linha do tempo de um item só (o PEDIDO_FOTO do catálogo, trazido em 02/11 com a pista bruto).
def _foto(pedido):
    return pedido.replace(
        "catalogando BRUTO de vlog (vídeo de celular). Assista o vídeo INTEIRO, imagem E SOM.",
        "catalogando FOTOS do bruto de vlog. Olhe a FOTO inteira, com atenção a quem aparece, o que cada um faz, onde é, e o que está escrito.",
    ).replace(
        "Responda SÓ um JSON com:",
        'É uma FOTO, não vídeo: "linha_do_tempo" tem UM item só, com "de" e "ate" = "0:00", "ve" = a descrição completa da cena e "ouve" = "";\n'
        '"falas_de_ouro" = []; "energia" = {"curva": "", "pico": ""}; nos tempos use sempre "0:00".\n\nResponda SÓ um JSON com:',
    )


PEDIDO_FOTO = _foto(PEDIDO)
assert PEDIDO_FOTO.count("FOTO") >= 2, "o PEDIDO mudou e o PEDIDO_FOTO não achou onde trocar"


def _chave():
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if k: return k, "chave da Fly (GEMINI_API_KEY)"
    if os.path.exists(base.CHAVE_GEMINI): return open(base.CHAVE_GEMINI, encoding="utf-8").read().strip(), "chave grátis do AI Studio (PC)"
    raise RuntimeError("sem chave do Gemini (nem GEMINI_API_KEY nem ~/.gemini/chave-api.txt)")


def _chamar(metodo, url, dados=None, cab=None, timeout=900):
    cab = dict(cab or {}); cab["x-goog-api-key"] = _chave()[0]
    return urllib.request.urlopen(urllib.request.Request(url, data=dados, headers=cab, method=metodo), timeout=timeout)


def modelos_flash():
    """servidor: o modelo do catálogo. PC: os Flash que a conta enxerga (o mais novo primeiro), pra revezar a cota grátis. Nunca Pro."""
    if os.environ.get("GEMINI_MODELO"): return [os.environ["GEMINI_MODELO"]]
    try:
        ms = json.load(_chamar("GET", f"{API_G}/v1beta/models?pageSize=200", timeout=60)).get("models", [])
        nomes = [m["name"].split("/")[-1] for m in ms if "generateContent" in m.get("supportedGenerationMethods", [])]
        fl = [n for n in nomes if "flash" in n and "pro" not in n and "image" not in n and "tts" not in n and "live" not in n and "lite" not in n]
        return sorted(fl, key=lambda n: (n != "gemini-3.8-flash", n != "gemini-3-flash-preview", n)) or ["gemini-3.8-flash"]
    except Exception:
        return ["gemini-3.8-flash", "gemini-3-flash-preview"]


def _desembrulha(x):
    """02/11 (Eagle's Life, catálogo): 32 de ~4.000 diários vieram como [ {...} ] — o diário certo, embrulhado numa lista"""
    return x[0] if isinstance(x, list) and len(x) == 1 and isinstance(x[0], dict) else x


def _gerar(partes, pedido):
    """o pedido + o vídeo/a foto em cada Flash da lista até um responder com JSON"""
    if time.time() < _SEM_COTA[0]:
        raise SemCota("sem cota no Gemini (todos os Flash deram 429); tenta de novo depois que a cota do dia voltar (~05h)")
    corpo = json.dumps({"contents": [{"role": "user", "parts": partes + [{"text": pedido}]}],
                        "generationConfig": {"temperature": 0.15, "responseMimeType": "application/json"}}).encode()
    hist = []
    for mod in modelos_flash():
        for tent in range(4):
            try:
                j = json.load(_chamar("POST", f"{API_G}/v1beta/models/{mod}:generateContent", corpo, {"Content-Type": "application/json"},
                                      timeout=ESPERA_S))
                txt = "".join(p.get("text", "") for c in j.get("candidates", []) for p in c.get("content", {}).get("parts", [])).strip()
                if txt.startswith("```"): txt = txt.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
                txt = txt[min((i for i in (txt.find("{"), txt.find("[")) if i >= 0), default=0):]
                diario, _ = json.JSONDecoder().raw_decode(txt)
                return {"diario": _desembrulha(diario), "uso": j.get("usageMetadata"), "modelo": mod, "erros_antes": hist}
            except urllib.error.HTTPError as e:
                hist.append(f"{mod}:{e.code}")
                if e.code in (429, 404, 400, 403): break                 # cota do dia do modelo / modelo que a conta não tem → próximo
                if e.code in (500, 503): time.sleep(15 * (tent + 1)); continue
                raise RuntimeError(f"Gemini {e.code}")
            except (TimeoutError, urllib.error.URLError, OSError) as e:
                hist.append(f"{mod}:demorou ({type(e).__name__})"); break     # 03/11: travava 15 min por vídeo → o próximo Flash
            except (ValueError, KeyError) as e:
                hist.append(f"{mod}:resposta sem JSON ({str(e)[:60]})"); time.sleep(5)
    if hist and all(h.endswith((":429", ":404", ":503")) for h in hist) and any(h.endswith(":429") for h in hist):   # 503 no meio de 429 = sem cota também (03/11)
        _SEM_COTA[0] = time.time() + 3600
        raise SemCota("sem cota no Gemini: " + ", ".join(hist))
    raise RuntimeError("o Gemini não respondeu: " + ", ".join(hist))


def gemini_foto(jpg, pedido=None):
    """a foto (jpg até 1600 px) vai junto do pedido, sem a Files API"""
    import base64
    return _gerar([{"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(open(jpg, "rb").read()).decode()}}], pedido or PEDIDO_FOTO)


def gemini_video(mp4, pedido, log=base.log):
    tam = os.path.getsize(mp4)
    r = _chamar("POST", f"{API_G}/upload/v1beta/files", json.dumps({"file": {"display_name": os.path.basename(mp4)}}).encode(),
                {"X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start", "X-Goog-Upload-Header-Content-Length": str(tam),
                 "X-Goog-Upload-Header-Content-Type": "video/mp4", "Content-Type": "application/json"})
    f = json.load(_chamar("POST", r.headers["x-goog-upload-url"], open(mp4, "rb").read(),
                          {"Content-Length": str(tam), "X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize"}))["file"]
    try:
        for _ in range(120):
            if f.get("state") == "ACTIVE": break
            if f.get("state") == "FAILED": raise RuntimeError("o Google não conseguiu ler o vídeo")
            time.sleep(3); f = json.load(_chamar("GET", f"{API_G}/v1beta/{f['name']}"))
        return _gerar([{"file_data": {"mime_type": "video/mp4", "file_uri": f["uri"]}}], pedido)
    finally:
        try: _chamar("DELETE", f"{API_G}/v1beta/{f['name']}", timeout=60)
        except Exception: pass


def rodar(A, ctx):
    from . import preparo
    t = time.time()
    if A["preparo"].get("tipo") == "foto":
        r = gemini_foto(preparo.caminho(A, "foto"), _foto(PEDIDO_SENSIVEL) if getattr(ctx, "sensivel", False) else PEDIDO_FOTO)
    else:
        mp4 = preparo.caminho(A, "leve480")
        if not mp4: return {"sem_imagem": True}
        r = gemini_video(mp4, PEDIDO_SENSIVEL if getattr(ctx, "sensivel", False) else PEDIDO, ctx.log)
    return {"diario": r["diario"], "modelo": r["modelo"], "plano": _chave()[1], "uso_tokens": r["uso"], "segundos": round(time.time() - t, 1),
            "erros_antes": r["erros_antes"]}
