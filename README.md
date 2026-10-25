# Assistant de création de CV (LaTeX)

1. **Gemini 2.5 Flash** (API, ou un modèle Ollama en local) mène la conversation : il comprend,
   répond aux questions, propose des idées et des reformulations, et décide quand générer.
2. **Qwen3-0.6B fine-tuné (LoRA)** transforme les données en CV LaTeX (`.tex`).

## Configuration

Crée un fichier `.env` à la racine du projet (il n'est pas versionné) avec ta clé Gemini
(gratuite sur https://aistudio.google.com/apikey) :

```
GEMINI_API_KEY=ta_cle
```

Pour travailler hors ligne avec Ollama : `LLM_PROVIDER=ollama` dans `.env`.

## Utilisation

```bash
python build_dataset.py      # crée dataset/cv_latex_train.jsonl et cv_latex_val.jsonl
python train.py              # fine-tuning -> output/cv-latex-lora
python evaluate.py           # mesure la qualité sur le jeu de validation
python -m app.main           # assistant en ligne de commande (--debug pour voir les données)
python -m uvicorn app.api:app --port 8000   # assistant en API (doc : http://localhost:8000/docs)
```

### Interface web (Angular)

```bash
# terminal 1 : l'API
python -m uvicorn app.api:app --port 8000

# terminal 2 : le frontend
cd frontend
npm start            # puis ouvrir http://localhost:4200
```

L'adresse de l'API se règle dans `frontend/src/app/config.ts`.

Pages : `/` (présentation), `/register` (inscription), `/login` (connexion), `/app` (espace personnel :
chat + historique des CV générés). Les comptes et l'historique sont stockés dans `data/cv_platform.db`
(SQLite), les fichiers des CV dans `data/users/<id>/`. Mots de passe hachés (PBKDF2), connexion par jeton JWT.

### API

| Méthode | Route | Rôle |
|---|---|---|
| POST | `/sessions` | crée une conversation → `session_id` + message d'accueil |
| POST | `/sessions/{id}/messages` | envoie `{"message": "..."}` → réponse, CV collecté, et `tex_url` si le CV a été généré |
| POST | `/sessions/{id}/generate` | force la génération avec les données actuelles |
| GET | `/sessions/{id}` | historique + CV collecté |
| GET | `/sessions/{id}/cv.tex` | télécharge le CV LaTeX |
| GET | `/health` | état du serveur |

Le CV est écrit dans `output/cv/cv_<prenom>_<nom>.tex`. Si `pdflatex` est installé
(MiKTeX ou TeX Live), le PDF est compilé automatiquement. Sinon, ouvre le `.tex` dans Overleaf.

## Fichiers

| Fichier | Rôle |
|---|---|
| `cv_schema.py` | Schéma unique des données du CV, champs obligatoires et recommandés |
| `llm.py` | Appel au LLM (Gemini ou Ollama) avec sortie JSON imposée |
| `agent.py` | Agent conversationnel : le LLM répond, met à jour le CV et décide de générer |
| `guards.py` | Garde-fous : retire du CV ce que l'utilisateur n'a jamais dit, normalise le format |
| `prompts.py` | Prompt du générateur, **identique** au dataset, à l'entraînement et à l'inférence |
| `latex.py` | Préambule fixe, échappement, rendu de référence, validation de la sortie du modèle |
| `dataset_pools.py` / `build_dataset.py` | Génération du dataset synthétique |
| `train.py` | Fine-tuning LoRA (loss sur la réponse uniquement, validation, meilleur checkpoint) |
| `generator.py` | Génération du `.tex` avec le modèle fine-tuné (+ secours si sortie invalide) |

## Règles importantes

- Si tu modifies `prompts.py`, `latex.py` (format de sortie) ou `cv_schema.py`,
  **régénère le dataset et réentraîne**.
- Le modèle ne génère que le corps du document. Le préambule (packages, macros) est
  ajouté par Python. On peut donc changer le style du CV dans `latex.PREAMBLE` sans réentraîner.
- Sur un GPU de 4 Go, Ollama est déchargé automatiquement avant l'entraînement et
  avant la génération.
