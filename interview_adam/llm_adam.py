"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Client Mistral-7B-Instruct : un seul point de sortie vers Ollama pour tout le module.

Choix d'implémentation (vérifiés dans la documentation Ollama) :
- `/api/generate` avec `raw=true` : le gabarit Mistral `[INST] <<SYS>> … <</SYS>> … [/INST]`
  est assemblé ici, donc rien n'est superposé au template de `/api/chat` ;
- `format` = schéma JSON appliqué aussi en mode raw, mais la documentation insiste :
  « it's important to instruct the model to use JSON in the prompt » et « ideal to also pass
  the JSON schema as a string in the prompt » -> le prompt porte le schéma en texte ;
- `raw=true` ne renvoie pas de contexte : chaque appel est donc autonome (question,
  évaluation et amélioration sont indépendants), ce qui correspond à l'usage du module ;
- `keep_alive` court + `release()` : le Module 1 charge Qwen3-0.6B + LoRA sur le même GPU et
  son `unload_ollama()` ne décharge que son propre modèle ;
- aucune dépendance à torch : le module ne touche jamais le GPU directement.
"""

import json
import random
import re
import threading
import time

import requests

from interview_adam import config_adam as cfg
from interview_adam.privacy import assert_anonymized

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


# ----------------------------------------------------------------------
# Exceptions : messages destinés à l'utilisateur (pas de détail technique brut)
# ----------------------------------------------------------------------

class AdamMistralError(RuntimeError):
    """Erreur du client Mistral. `http_status` : code à renvoyer à l'UI, `retryable` : tentée à nouveau."""

    def __init__(self, message, http_status=503, retryable=False):
        super().__init__(message)
        self.message = message
        self.http_status = http_status
        self.retryable = retryable


class AdamMistralNotConfigured(AdamMistralError):
    def __init__(self, message="Le simulateur n'est pas configuré (MISTRAL_BASE_URL manquant)."):
        super().__init__(message, http_status=503)


class AdamMistralUnreachable(AdamMistralError):
    def __init__(self):
        super().__init__(
            "Impossible de joindre Ollama. Démarre-le (application Ollama ou `ollama serve`) puis réessaie.",
            http_status=503, retryable=True)


class AdamMistralModelMissing(AdamMistralError):
    def __init__(self, model):
        super().__init__(
            f"Le modèle {model} n'est pas installé. Lance : ollama pull {model}", http_status=503)


class AdamMistralUnauthorized(AdamMistralError):
    def __init__(self):
        super().__init__(
            "Le service de génération refuse la connexion (clé d'API invalide ?).", http_status=503)


class AdamMistralQuota(AdamMistralError):
    def __init__(self):
        super().__init__(
            "Le service IA est saturé pour l'instant. Réessaie dans une minute.", http_status=503, retryable=True)


class AdamMistralTimedOut(AdamMistralError):
    def __init__(self):
        super().__init__(
            "Le modèle met trop de temps à répondre. Réessaie, ou réduis le nombre de questions.",
            http_status=504, retryable=True)


class AdamMistralBusy(AdamMistralError):
    def __init__(self):
        super().__init__(
            "Une autre demande est déjà en cours sur le modèle. Réessaie dans quelques secondes.",
            http_status=503)


class AdamMistralBadJson(AdamMistralError):
    """Sortie du modèle inexploitable : déclenche le prompt de réparation côté service."""

    def __init__(self, detail=""):
        super().__init__(f"Réponse JSON invalide du modèle. {detail}".strip(), http_status=502)


# ----------------------------------------------------------------------
# Client
# ----------------------------------------------------------------------

class AdamMistralClient:
    """Client HTTP unique, avec timeout, retry à backoff et exceptions explicites."""

    def __init__(self, base_url=None, model=None, api_key=None):
        self.base_url = (base_url if base_url is not None else cfg.MISTRAL_BASE_URL).rstrip("/")
        self.model = model or cfg.MISTRAL_MODEL
        self.api_key = api_key if api_key is not None else cfg.MISTRAL_API_KEY
        self._semaphore = threading.BoundedSemaphore(max(1, cfg.MAX_CONCURRENT_LLM_CALLS))

    # -- utilitaires ---------------------------------------------------

    @property
    def generate_url(self):
        return f"{self.base_url}/api/generate"

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _acquire(self):
        if not self._semaphore.acquire(timeout=cfg.SEMAPHORE_TIMEOUT):
            raise AdamMistralBusy()

    # -- appels --------------------------------------------------------

    def generate_json(self, prompt, schema, temperature=0.4, max_tokens=None):
        """
        Envoie un prompt déjà au format `[INST]…[/INST]` et renvoie un dict.
        Le contenu est contrôlé côté confidentialité avant départ : c'est le dernier rempart.

        `stream=false` est délibéré : la sortie est un JSON imposé par la grammaire `format`,
        donc les tokens intermédiaires ne sont pas exploitables avant la fin (un JSON tronqué
        n'est pas lisible), et le chemin réparation/repli ne peut pas être streamé. L'affichage
        de progression pendant un appel CPU long se fait côté interface (message temporisé),
        sans coûter un StreamingResponse à travers route + service + client + Angular.
        """
        if not self.base_url:
            raise AdamMistralNotConfigured()
        assert_anonymized(prompt)

        payload = {
            "model": self.model,
            "prompt": prompt,
            "raw": True,
            "stream": False,
            "format": schema,
            "keep_alive": cfg.KEEP_ALIVE,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens or cfg.MAX_NEW_TOKENS,
                "num_ctx": cfg.NUM_CTX,
                "repeat_penalty": 1.1,
            },
        }
        if cfg.NUM_GPU >= 0:
            payload["options"]["num_gpu"] = cfg.NUM_GPU

        self._acquire()
        try:
            text = self._post_for_text(payload)
        finally:
            self._semaphore.release()

        data = _parse_json(text)
        data["_model"] = self.model
        return data

    def _post_for_text(self, payload):
        """POST avec retries (timeout, réseau, 429, 5xx). Retourne le texte brut du modèle."""
        last_error = None
        for attempt in range(cfg.RETRIES + 1):
            if attempt:
                time.sleep(cfg.BACKOFF_BASE * attempt + random.uniform(0, 1))
            try:
                response = requests.post(
                    self.generate_url, json=payload,
                    timeout=(cfg.TIMEOUT_CONNECT, cfg.TIMEOUT_READ), headers=self._headers())
            except requests.Timeout:
                last_error = AdamMistralTimedOut()
                continue
            except requests.RequestException:
                last_error = AdamMistralUnreachable()
                continue

            if response.status_code == 404:
                raise AdamMistralModelMissing(payload["model"])
            if response.status_code in (401, 403):
                raise AdamMistralUnauthorized()
            if response.status_code == 429:
                last_error = AdamMistralQuota()
                continue
            if response.status_code >= 500:
                last_error = _upstream_error(response, payload["model"])
                continue
            if response.status_code >= 400:
                raise _upstream_error(response, payload["model"])

            try:
                body = response.json()
            except ValueError:
                raise AdamMistralBadJson("Ollama a renvoyé une réponse non JSON.") from None
            if body.get("error"):
                raise _ollama_error(body["error"], payload["model"])
            text = body.get("response")
            if text is None:
                raise AdamMistralBadJson("Champ `response` absent.")
            return _clean_text(text)

        raise last_error

    def release(self):
        """
        Libère la VRAM occupée par Mistral (keep_alive=0), pour que le Module 1 puisse
        charger Qwen3-0.6B + LoRA sur la même carte. Échec silencieux : c'est un confort.
        """
        if not self.base_url:
            return False
        try:
            requests.post(self.generate_url,
                          json={"model": self.model, "prompt": "", "raw": True,
                                "stream": False, "keep_alive": 0},
                          timeout=(5, 15), headers=self._headers())
            return True
        except requests.RequestException:
            return False

    def is_available(self):
        """True si Ollama répond et que le modèle est présent (utilisé par le diagnostic)."""
        if not self.base_url:
            return False, "MISTRAL_BASE_URL absent"
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=(5, 10))
        except requests.RequestException:
            return False, "Ollama injoignable"
        if response.status_code != 200:
            return False, f"Ollama a répondu {response.status_code}"
        names = [m.get("name", "") for m in response.json().get("models", [])]
        wanted = self.model.split(":")[0]
        if not any(n == self.model or n.split(":")[0] == wanted for n in names):
            return False, f"modèle {self.model} non installé"
        return True, "ok"


# ----------------------------------------------------------------------
# Fonctions utilitaires
# ----------------------------------------------------------------------

def _clean_text(text):
    return _THINK_RE.sub("", str(text)).strip()


def _parse_json(text):
    """Charge la sortie du modèle en tolérant les fences et le texte environnant."""
    raw = (text or "").strip()
    raw = _FENCE_RE.sub("", raw).strip()
    try:
        data = json.loads(raw)
    except ValueError:
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end <= start:
            raise AdamMistralBadJson(f"(attendu un objet JSON, reçu {raw[:60]!r})") from None
        try:
            data = json.loads(raw[start:end + 1])
        except ValueError as error:
            raise AdamMistralBadJson(f"({error})") from error
    if not isinstance(data, dict):
        raise AdamMistralBadJson("(le modèle n'a pas renvoyé d'objet JSON)")
    return data


def _looks_like_model_absence(message):
    lowered = str(message).lower()
    return "not found" in lowered or "does not exist" in lowered


def _looks_like_memory(message):
    lowered = str(message).lower()
    return any(word in lowered for word in ("memory", "cuda", "oom", "vram"))


def _ollama_error(message, model):
    if _looks_like_model_absence(message):
        return AdamMistralModelMissing(model)
    if _looks_like_memory(message):
        return AdamMistralError(
            "Mémoire insuffisante pour charger le modèle. Réessaie dans un instant "
            "(une génération de CV utilise peut-être le GPU).", http_status=503)
    return AdamMistralError(f"Le service IA a refusé la demande : {str(message)[:200]}", http_status=503)


def _upstream_error(response, model=""):
    """
    Erreur HTTP renvoyée par le serveur Ollama. Le corps est scruté : une panne de mémoire
    est une contention GPU avec le Module 1, et le message doit le dire plutôt que renvoyer
    un « service indisponible » inutilisable.
    """
    detail = ""
    try:
        detail = str(response.json().get("error", ""))[:200]
    except ValueError:
        detail = (response.text or "")[:200]
    if model and detail and _looks_like_model_absence(detail):
        return AdamMistralModelMissing(model)
    if detail and _looks_like_memory(detail):
        return _ollama_error(detail, model)
    if response.status_code >= 500:
        return AdamMistralError(
            "Le service IA est momentanément indisponible. Réessaie dans une minute.",
            http_status=503, retryable=True)
    return AdamMistralError(f"Requête refusée par le service IA. {detail}".strip(), http_status=503)


# Instance partagée par le routeur et le service.
client = AdamMistralClient()
