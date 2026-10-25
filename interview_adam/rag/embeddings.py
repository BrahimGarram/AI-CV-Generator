"""
Author: Adam | Module: AI Job Interview Simulator | Project: SmartCareer AI, IA for Software Engineering 2026-2027

Plongeon d'embeddings du module : `all-MiniLM-L6-v2` chargé via `transformers`, sans
dépendance à sentence-transformers (qui est lui-même un wrapper de transformers + un
pooling manuel : on fait le pooling nous-mêmes, une dépendance de moins à épingler).

Deux contraintes matérielles, toutes deux non négociables ici :

* **CPU only.** Le GPU est déjà occupé par Qwen3-0.6B + LoRA du Module 1 pendant une
  génération de CV, et Mistral-7B tourne sur la carte le reste du temps. 384 dimensions
  sur ~70 fragments se calculent en une poignée de secondes sur un cœur CPU : le GPU
  n'apporte rien et coûte un crash mémoire.
* **Import différé de torch.** `interview_adam` est importé par `app/api.py` au démarrage
  de l'API. Importer torch à l'import coûterait plusieurs secondes et de la RAM à chaque
  lancement, même quand personne n'utilise le RAG. torch n'est donc importé qu'au premier
  `embed()`, et le modèle n'est construit qu'une fois (cache de classe).

Tout échec ici se traduit en `AdamEmbeddingError` : l'appelant (le retriever) décide de
tomber en mode « sans RAG » plutôt que de faire échouer un entretien.
"""

import threading

from interview_adam import config_adam as cfg

# MiniLM-L6-v2 : 384 dimensions, max 512 tokens de contexte.
EMBEDDING_DIM = 384
MAX_SEQ_LENGTH = 512

_CACHE = {}
_CACHE_LOCK = threading.Lock()


class AdamEmbeddingError(RuntimeError):
    """Modèle absent, non téléchargeable, ou calcul impossible : le RAG devient indisponible."""


class AdamEmbedder:
    """
    `embed(texts)` rend un tableau `(n, EMBEDDING_DIM)` en float32, chaque ligne normalisée
    en L2. La normalisation est ce qui autorise `IndexFlatIP` à calculer un cosinus
    (produit scalaire sur des vecteurs unitaires) et rend les scores comparables d'un appel
    à l'autre.

    Les instances partagent le même modèle chargé en mémoire : ouvrir un retriever par
    requête HTTP ne doit pas recharger 90 Mo de poids.
    """

    def __init__(self, model_name=None):
        self.model_name = model_name or cfg.EMBEDDING_MODEL
        self.dim = EMBEDDING_DIM

    # ------------------------------------------------------------------
    # Chargement (une fois par nom de modèle, protégé contre le multi-thread)
    # ------------------------------------------------------------------

    def _bundle(self):
        if self.model_name in _CACHE:
            return _CACHE[self.model_name]

        with _CACHE_LOCK:
            if self.model_name in _CACHE:      # une autre requête a chargé pendant l'attente
                return _CACHE[self.model_name]
            try:
                import torch                       # différé : voir docstring du module
                from transformers import AutoModel, AutoTokenizer
            except ImportError as error:
                raise AdamEmbeddingError(
                    f"transformers/torch absents de l'environnement ({error}). "
                    "Installe requirement.txt puis requirements_interview_adam.txt.") from error

            try:
                tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                model = AutoModel.from_pretrained(self.model_name)
            except Exception as error:  # noqa: BLE001 - réseau, cache HF, nom de modèle
                raise AdamEmbeddingError(
                    f"impossible de charger le modèle d'embeddings {self.model_name} : {error}") from error

            model.to("cpu").eval()
            for parameter in model.parameters():
                parameter.requires_grad_(False)    # inférence seule, jamais de graphe de gradients
            _CACHE[self.model_name] = (torch, tokenizer, model)
            return _CACHE[self.model_name]

    # ------------------------------------------------------------------
    # Calcul
    # ------------------------------------------------------------------

    def embed(self, texts):
        """Embed une liste de textes. Une liste vide rend un tableau `(0, dim)` sans toucher au modèle."""
        if not texts:
            import numpy as np
            return np.zeros((0, self.dim), dtype="float32")

        torch, tokenizer, model = self._bundle()
        import numpy as np

        vectors = []
        try:
            with torch.inference_mode():
                for start in range(0, len(texts), 8):
                    batch = list(texts[start:start + 8])
                    encoded = tokenizer(batch, padding=True, truncation=True,
                                        max_length=MAX_SEQ_LENGTH, return_tensors="pt")
                    # last_hidden_state : (batch, seq_len, hidden) — le [CLS] seul sous-
                    # représente les textes longs, d'où la moyenne masquée ci-dessous.
                    hidden = model(**encoded).last_hidden_state
                    mask = encoded["attention_mask"].unsqueeze(-1).float()
                    pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
                    pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
                    vectors.append(pooled.cpu().numpy().astype("float32"))
        except AdamEmbeddingError:
            raise
        except Exception as error:  # noqa: BLE001 - OOM, sequence vide, dtype surprenant
            raise AdamEmbeddingError(f"calcul d'embeddings impossible : {error}") from error

        return np.vstack(vectors)

    def embed_one(self, text):
        return self.embed([text])[0]

    def warm(self):
        """
        Pré-charge le modèle (utilisé par `python -m interview_adam.rag.ingest` pour que le
        téléchargement éventuel se fasse hors requête HTTP).
        """
        self._bundle()
        return self.model_name

    @staticmethod
    def cached_models():
        return sorted(_CACHE)
