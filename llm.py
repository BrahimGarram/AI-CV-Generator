"""
Appel au LLM de conversation avec une sortie JSON imposée.

Deux fournisseurs (choisis dans config.py / .env) :
- "gemini" : API Google Gemini (gemini-2.5-flash, clé gratuite sur aistudio.google.com) ;
- "ollama" : modèle local (hors ligne, moins intelligent).
"""

import copy
import json
import re
import time

import requests

from config import (
    GEMINI_API_KEY, GEMINI_FALLBACK_MODELS, GEMINI_MODEL, GEMINI_THINKING_BUDGET,
    LLM_PROVIDER, OLLAMA_BASE, OLLAMA_CHAT_URL, OLLAMA_MODEL,
)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class LLMError(RuntimeError):
    """Erreur affichable à l'utilisateur (clé manquante, quota, réseau...)."""


# ----------------------------------------------------------------------
# Gemini
# ----------------------------------------------------------------------

def _to_gemini_schema(schema):
    """JSON Schema -> format OpenAPI attendu par Gemini (types en majuscules, nullable)."""
    schema = copy.deepcopy(schema)

    def convert(node):
        if not isinstance(node, dict):
            return node
        out = {}
        types = node.get("type")
        if isinstance(types, list):
            non_null = [t for t in types if t != "null"]
            out["type"] = non_null[0].upper() if non_null else "STRING"
            if "null" in types:
                out["nullable"] = True
        elif isinstance(types, str):
            out["type"] = types.upper()
        for key in ("enum", "description", "required"):
            if key in node:
                out[key] = node[key]
        if "properties" in node:
            out["properties"] = {k: convert(v) for k, v in node["properties"].items()}
            out["propertyOrdering"] = list(node["properties"])
        if "items" in node:
            out["items"] = convert(node["items"])
        return out

    return convert(schema)


class _Unavailable(Exception):
    """Modèle surchargé / quota atteint / pas de réponse : on peut essayer le modèle de secours."""


def _gemini_chat_json(system, messages, schema, temperature):
    models = list(dict.fromkeys([GEMINI_MODEL] + GEMINI_FALLBACK_MODELS))
    for index, model in enumerate(models):
        try:
            # Modèle principal : réponse rapide exigée ; secours : plus de patience.
            data = _gemini_call(model, system, messages, schema, temperature,
                                retries=2 if index == len(models) - 1 else 0,
                                read_timeout=60 if index == len(models) - 1 else 30)
            data["_model"] = model
            return data
        except _Unavailable as error:
            if index == len(models) - 1:
                raise LLMError(str(error)) from error
            print(f"[{model} indisponible, bascule sur {models[index + 1]}]")


def _gemini_call(model, system, messages, schema, temperature, retries, read_timeout):
    if not GEMINI_API_KEY:
        raise LLMError(
            "Clé Gemini manquante. Crée un fichier .env dans le dossier du projet avec :\n"
            "GEMINI_API_KEY=ta_cle  (clé gratuite sur https://aistudio.google.com/apikey)"
        )
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [
            {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
            for m in messages
        ],
        "generationConfig": {
            "temperature": temperature,
            "responseMimeType": "application/json",
            "responseSchema": _to_gemini_schema(schema),
            "thinkingConfig": {"thinkingBudget": GEMINI_THINKING_BUDGET},
        },
    }
    url = GEMINI_URL.format(model=model)
    headers = {"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"}

    for attempt in range(retries + 1):
        try:
            response = requests.post(url, headers=headers, json=body, timeout=(10, read_timeout))
        except requests.Timeout as error:
            raise _Unavailable(f"{model} ne répond pas.") from error
        except requests.RequestException as error:
            raise LLMError(f"Impossible de joindre Gemini (connexion internet ?) : {error}") from error

        if response.status_code == 429 or response.status_code >= 500:
            # Quota par minute du niveau gratuit ou surcharge : on patiente puis on réessaie.
            if attempt < retries:
                time.sleep(6 * (attempt + 1))
                continue
            raise _Unavailable(f"{model} est saturé ou le quota gratuit est atteint. Réessaie dans une minute.")
        if response.status_code in (400, 403):
            detail = response.json().get("error", {}).get("message", response.text[:200])
            raise LLMError(f"Requête refusée par Gemini (clé invalide ?) : {detail}")
        response.raise_for_status()
        break

    data = response.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        reason = data.get("promptFeedback", {}).get("blockReason") or data.get("candidates", [{}])[0].get("finishReason")
        raise LLMError(f"Gemini n'a pas renvoyé de réponse ({reason}).")
    return _parse_json(text)


# ----------------------------------------------------------------------
# Ollama (local)
# ----------------------------------------------------------------------

def _ollama_chat_json(system, messages, schema, temperature):
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "system", "content": system}] + messages,
        "format": schema,
        "stream": False,
        "think": False,
        "keep_alive": "15m",
        "options": {"temperature": temperature, "repeat_penalty": 1.1, "num_predict": 2500, "num_ctx": 16384},
    }
    try:
        response = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=(10, 600))
    except requests.ConnectionError as error:
        raise LLMError("Ollama ne répond pas. Lance l'application Ollama puis réessaie.") from error
    if response.status_code == 404:
        raise LLMError(f"Modèle {OLLAMA_MODEL} non installé. Lance : ollama pull {OLLAMA_MODEL}")
    response.raise_for_status()
    content = response.json()["message"]["content"]
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    return _parse_json(content)


def unload_ollama():
    """Libère la VRAM avant de charger le générateur (utile seulement avec Ollama)."""
    try:
        requests.post(f"{OLLAMA_BASE}/api/generate", json={"model": OLLAMA_MODEL, "keep_alive": 0}, timeout=5)
    except requests.RequestException:
        pass


# ----------------------------------------------------------------------

def _parse_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise LLMError(f"Réponse JSON invalide du LLM : {error}") from error
    if not isinstance(data, dict):
        raise LLMError("Le LLM n'a pas renvoyé un objet JSON.")
    return data


def chat_json(system, messages, schema, temperature=0.4):
    """
    messages = [{"role": "user"|"assistant", "content": str}, ...] -> dict conforme au schéma.
    Le dict contient aussi "_model" (modèle qui a répondu) et "_seconds" (durée).
    """
    start = time.time()
    if LLM_PROVIDER == "ollama":
        data = _ollama_chat_json(system, messages, schema, temperature)
        data["_model"] = OLLAMA_MODEL
    else:
        data = _gemini_chat_json(system, messages, schema, temperature)
    data["_seconds"] = round(time.time() - start, 1)
    print(f"[LLM] réponse de {data['_model']} en {data['_seconds']} s")
    return data
