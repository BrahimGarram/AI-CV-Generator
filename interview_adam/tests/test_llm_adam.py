"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Client Mistral : shape de la requête (raw, format, keep_alive, gabarit assemblé ici) et
comportement face aux pannes (modèle absent, quota, timeout, réseau coupé, JSON cassé).

Aucun appel réseau : `requests.post` est remplacé.
"""

import json

import pytest
import requests

from interview_adam import config_adam as cfg
from interview_adam import llm_adam
from interview_adam.llm_adam import (AdamMistralBadJson, AdamMistralModelMissing, AdamMistralQuota,
                                     AdamMistralTimedOut, AdamMistralUnreachable, AdamMistralUnauthorized,
                                     AdamMistralClient)
from interview_adam.privacy import PrivacyError
from interview_adam.schemas_adam import EVALUATION_SCHEMA

PROMPT = "[INST] <<SYS>>\nrôle\n<</SYS>>\n\nquestion [/INST]"
GOOD = {"response": json.dumps({"score": 8, "criteria": {}})}


class Recorder:
    def __init__(self, replies):
        """replies : liste de (Response | Exception)-consommés dans l'ordre.

        Une fois la liste épuisée, la dernière réponse est rejouée : les tests de retry
        n'ont pas besoin d'écrire trois fois la même réponse.
        """
        if not replies:
            raise AssertionError("au moins une réponse simulée est nécessaire")
        self.replies = list(replies)
        self.last = replies[-1]
        self.requests = []

    def __call__(self, url, json=None, timeout=None, headers=None):
        self.requests.append({"url": url, "payload": json, "timeout": timeout, "headers": headers})
        outcome = self.replies.pop(0) if self.replies else self.last
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class Response:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("pas de json")
        return self._payload


@pytest.fixture
def patched_sleep(monkeypatch):
    monkeypatch.setattr(llm_adam.time, "sleep", lambda *_: None)
    monkeypatch.setattr(llm_adam.random, "uniform", lambda *_: 0)


@pytest.fixture
def client():
    return AdamMistralClient(base_url="http://ollama.test:11434", model="mistral:7b-test", api_key="")


def install(monkeypatch, replies):
    recorder = Recorder(replies)
    monkeypatch.setattr(llm_adam.requests, "post", recorder)
    return recorder


# ----------------------------------------------------------------------
# Forme de la requête
# ----------------------------------------------------------------------

def test_uses_generate_endpoint_in_raw_mode_with_own_template(client, monkeypatch, patched_sleep):
    recorder = install(monkeypatch, [Response(200, GOOD)])
    client.generate_json(PROMPT, EVALUATION_SCHEMA)

    payload = recorder.requests[0]["payload"]
    assert recorder.requests[0]["url"] == "http://ollama.test:11434/api/generate"
    assert payload["raw"] is True
    assert payload["prompt"] == PROMPT
    assert payload["prompt"].count("[INST]") == 1, "le gabarit ne doit pas être doublé"


def test_sends_the_json_schema_and_keep_alive(client, monkeypatch, patched_sleep):
    recorder = install(monkeypatch, [Response(200, GOOD)])
    client.generate_json(PROMPT, EVALUATION_SCHEMA)
    payload = recorder.requests[0]["payload"]
    assert payload["format"] == EVALUATION_SCHEMA
    assert payload["keep_alive"] == cfg.KEEP_ALIVE
    assert payload["stream"] is False


def test_options_cap_context_and_predict(client, monkeypatch, patched_sleep):
    recorder = install(monkeypatch, [Response(200, GOOD)])
    client.generate_json(PROMPT, EVALUATION_SCHEMA, temperature=0.2)
    options = recorder.requests[0]["payload"]["options"]
    assert options["temperature"] == 0.2
    assert options["num_ctx"] == cfg.NUM_CTX
    assert options["num_predict"] == cfg.MAX_NEW_TOKENS


def test_num_gpu_only_sent_when_pinned(client, monkeypatch, patched_sleep):
    recorder = install(monkeypatch, [Response(200, GOOD), Response(200, GOOD)])
    client.generate_json(PROMPT, EVALUATION_SCHEMA)
    assert "num_gpu" not in recorder.requests[0]["payload"]["options"]

    monkeypatch.setattr(cfg, "NUM_GPU", 0)
    client.generate_json(PROMPT, EVALUATION_SCHEMA)
    assert recorder.requests[1]["payload"]["options"]["num_gpu"] == 0


def test_timeout_is_connect_then_read(client, monkeypatch, patched_sleep):
    recorder = install(monkeypatch, [Response(200, GOOD)])
    client.generate_json(PROMPT, EVALUATION_SCHEMA)
    assert recorder.requests[0]["timeout"] == (cfg.TIMEOUT_CONNECT, cfg.TIMEOUT_READ)


def test_bearer_header_only_when_key_provided(monkeypatch, patched_sleep):
    recorder = install(monkeypatch, [Response(200, GOOD), Response(200, GOOD)])
    AdamMistralClient(base_url="http://x", model="m").generate_json(PROMPT, EVALUATION_SCHEMA)
    assert "Authorization" not in recorder.requests[0]["headers"]

    AdamMistralClient(base_url="http://x", model="m", api_key="secret").generate_json(PROMPT,
                                                                                      EVALUATION_SCHEMA)
    assert recorder.requests[1]["headers"]["Authorization"] == "Bearer secret"


def test_release_asks_ollama_to_unload_the_model(client, monkeypatch):
    recorder = install(monkeypatch, [Response(200, {"response": ""})])
    assert client.release() is True
    payload = recorder.requests[0]["payload"]
    assert payload["keep_alive"] == 0
    assert payload["model"] == "mistral:7b-test"


# ----------------------------------------------------------------------
# Parsing de la sortie
# ----------------------------------------------------------------------

def test_parses_a_plain_json_response(client, monkeypatch, patched_sleep):
    install(monkeypatch, [Response(200, {"response": '{"score": 6, "criteria": {}}'})])
    assert client.generate_json(PROMPT, EVALUATION_SCHEMA)["score"] == 6


def test_tolerates_markdown_fences_and_surrounding_text(client, monkeypatch, patched_sleep):
    install(monkeypatch, [Response(200, {"response": "```json\n{\"score\": 6}\n```"})])
    assert client.generate_json(PROMPT, EVALUATION_SCHEMA)["score"] == 6
    install(monkeypatch, [Response(200, {"response": "Voici : {\"score\": 5} j'espère que ça aide"})])
    assert client.generate_json(PROMPT, EVALUATION_SCHEMA)["score"] == 5


def test_raises_bad_json_when_nothing_parses(client, monkeypatch, patched_sleep):
    install(monkeypatch, [Response(200, {"response": "je préfère répondre en prose"})])
    with pytest.raises(AdamMistralBadJson):
        client.generate_json(PROMPT, EVALUATION_SCHEMA)


def test_rejects_a_json_array_instead_of_object(client, monkeypatch, patched_sleep):
    install(monkeypatch, [Response(200, {"response": "[1, 2]"})])
    with pytest.raises(AdamMistralBadJson):
        client.generate_json(PROMPT, EVALUATION_SCHEMA)


# ----------------------------------------------------------------------
# Pannes
# ----------------------------------------------------------------------

def test_model_missing_mentions_ollama_pull(client, monkeypatch, patched_sleep):
    install(monkeypatch, [Response(404, {"error": "model not found"})])
    with pytest.raises(AdamMistralModelMissing) as excinfo:
        client.generate_json(PROMPT, EVALUATION_SCHEMA)
    assert "ollama pull mistral:7b-test" in str(excinfo.value)
    assert excinfo.value.http_status == 503


def test_quota_is_retried_then_reported(client, monkeypatch, patched_sleep):
    recorder = install(monkeypatch, [Response(429, {"error": "too many requests"}),
                                     Response(429, {"error": "too many requests"}),
                                     Response(429, {"error": "too many requests"})])
    with pytest.raises(AdamMistralQuota):
        client.generate_json(PROMPT, EVALUATION_SCHEMA)
    assert len(recorder.requests) == cfg.RETRIES + 1


def test_server_error_is_retried_then_reported(client, monkeypatch, patched_sleep):
    recorder = install(monkeypatch, [Response(500, None, "boom"), Response(200, GOOD)])
    assert client.generate_json(PROMPT, EVALUATION_SCHEMA)["score"] == 8
    assert len(recorder.requests) == 2


def test_timeout_is_retried_then_504_style_error(client, monkeypatch, patched_sleep):
    recorder = install(monkeypatch, [requests.Timeout(), Response(200, GOOD)])
    assert client.generate_json(PROMPT, EVALUATION_SCHEMA)["_model"] == "mistral:7b-test"
    assert len(recorder.requests) == 2

    install(monkeypatch, [requests.Timeout() for _ in range(cfg.RETRIES + 1)])
    with pytest.raises(AdamMistralTimedOut) as excinfo:
        client.generate_json(PROMPT, EVALUATION_SCHEMA)
    assert excinfo.value.http_status == 504


def test_connection_error_says_ollama_must_be_started(client, monkeypatch, patched_sleep):
    install(monkeypatch, [requests.ConnectionError() for _ in range(cfg.RETRIES + 1)])
    with pytest.raises(AdamMistralUnreachable) as excinfo:
        client.generate_json(PROMPT, EVALUATION_SCHEMA)
    assert "Ollama" in str(excinfo.value)


def test_auth_failure_is_not_retried(client, monkeypatch, patched_sleep):
    recorder = install(monkeypatch, [Response(401, {"error": "invalid key"})])
    with pytest.raises(AdamMistralUnauthorized):
        client.generate_json(PROMPT, EVALUATION_SCHEMA)
    assert len(recorder.requests) == 1


def test_ollama_memory_error_explains_the_gpu(client, monkeypatch, patched_sleep):
    install(monkeypatch, [Response(500, {"error": "cuda out of memory"})])
    with pytest.raises(Exception) as excinfo:
        client.generate_json(PROMPT, EVALUATION_SCHEMA)
    assert "mémoire" in str(excinfo.value).lower()


def test_missing_base_url_is_a_configuration_error():
    with pytest.raises(Exception) as excinfo:
        AdamMistralClient(base_url="", model="m").generate_json(PROMPT, EVALUATION_SCHEMA)
    assert "configuré" in str(excinfo.value).lower()


# ----------------------------------------------------------------------
# Confidence : dernier garde-fou avant départ
# ----------------------------------------------------------------------

def test_refuses_to_send_an_email_to_the_model(client, monkeypatch):
    recorder = install(monkeypatch, [Response(200, GOOD)])
    with pytest.raises(PrivacyError):
        client.generate_json("[INST] contact : quelquun@exemple.fr [/INST]", EVALUATION_SCHEMA)
    assert recorder.requests == []


def test_is_available_reports_missing_model(client, monkeypatch):
    monkeypatch.setattr(llm_adam.requests, "get",
                        lambda url, timeout=None: Response(200, {"models": [{"name": "llama3:latest"}]}))
    available, reason = client.is_available()
    assert available is False and "mistral:7b-test" in reason

    monkeypatch.setattr(llm_adam.requests, "get",
                        lambda url, timeout=None: Response(200, {"models": [{"name": "mistral:7b-test"}]}))
    assert client.is_available() == (True, "ok")
