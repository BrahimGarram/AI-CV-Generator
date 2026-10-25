"""
Fine-tuning LoRA de Qwen3-0.6B : données du CV -> corps LaTeX.

    python build_dataset.py      # (une fois) crée dataset/cv_latex_*.jsonl
    python train.py

Choix importants :
- Le prompt est construit avec la même fonction qu'à l'inférence (prompts.py).
- La loss est calculée UNIQUEMENT sur la réponse (le LaTeX), pas sur le
  system prompt ni sur les données d'entrée.
- Aucun exemple n'est tronqué : les exemples trop longs sont écartés.
- Le modèle ne calcule les logits que sur la partie réponse
  (logits_to_keep), ce qui permet de tenir dans 4 Go de VRAM.
- Un jeu de validation sert à garder le meilleur checkpoint.
"""

import json

import requests
import torch
import torch.nn.functional as F
from datasets import Dataset
from peft import LoraConfig, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
)

from config import ADAPTER_PATH, BASE_MODEL, EXTRACTION_MODEL, OLLAMA_BASE, TRAIN_FILE, VAL_FILE

# ==========================================
# Hyperparamètres
# ==========================================

MAX_LENGTH = 1700          # tokens (prompt + réponse) ; les exemples plus longs sont écartés
EPOCHS = 2
LEARNING_RATE = 2e-4
GRAD_ACCUMULATION = 8      # batch effectif = 8 exemples
LORA_R = 16
LORA_ALPHA = 32
EVAL_EVERY = 50            # pas d'optimisation


def unload_ollama():
    """Libère la VRAM occupée par Ollama avant l'entraînement."""
    try:
        requests.post(
            f"{OLLAMA_BASE}/api/generate",
            json={"model": EXTRACTION_MODEL, "keep_alive": 0},
            timeout=10,
        )
        print("Modèle Ollama déchargé de la VRAM.")
    except requests.RequestException:
        pass


def load_jsonl(path):
    if not path.exists():
        raise FileNotFoundError(f"{path} introuvable. Lance d'abord : python build_dataset.py")
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def tokenize_example(record, tokenizer):
    messages = record["messages"]
    if messages[-1]["role"] != "assistant":
        raise ValueError("Chaque exemple doit se terminer par la réponse assistant.")

    # Exactement le même prompt qu'à l'inférence (voir generator.py).
    prompt_ids = tokenizer.apply_chat_template(
        messages[:-1],
        tokenize=True,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    completion_ids = tokenizer(messages[-1]["content"], add_special_tokens=False)["input_ids"]
    completion_ids.append(tokenizer.convert_tokens_to_ids("<|im_end|>"))

    return {
        "input_ids": prompt_ids + completion_ids,
        "prompt_len": len(prompt_ids),
    }


def prepare_dataset(path, tokenizer):
    records = load_jsonl(path)
    examples = [tokenize_example(r, tokenizer) for r in records]
    kept = [e for e in examples if len(e["input_ids"]) <= MAX_LENGTH]
    if len(kept) < len(examples):
        print(f"  {len(examples) - len(kept)} exemple(s) écarté(s) car > {MAX_LENGTH} tokens")
    lengths = [len(e["input_ids"]) for e in kept]
    print(f"  {path.name} : {len(kept)} exemples, longueur moyenne {sum(lengths) // len(lengths)} tokens")
    return Dataset.from_list(kept)


def collate(batch):
    # batch_size = 1 : pas de padding, donc pas de décalage de positions.
    assert len(batch) == 1, "Ce script utilise per_device_train_batch_size=1"
    ids = torch.tensor([batch[0]["input_ids"]], dtype=torch.long)
    return {
        "input_ids": ids,
        "attention_mask": torch.ones_like(ids),
        "labels": ids,  # utilisé seulement pour signaler au Trainer qu'il y a une loss
        "prompt_len": torch.tensor([batch[0]["prompt_len"]]),
    }


class CompletionOnlyTrainer(Trainer):
    """Loss uniquement sur la réponse, logits calculés seulement sur cette partie."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # La loss est déjà moyennée par exemple : le Trainer divise par
        # le nombre de pas d'accumulation.
        self.model_accepts_loss_kwargs = False

    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        input_ids = inputs["input_ids"]
        prompt_len = int(inputs["prompt_len"][0])
        keep = input_ids.shape[1] - prompt_len + 1

        outputs = model(
            input_ids=input_ids,
            attention_mask=inputs["attention_mask"],
            logits_to_keep=keep,
        )
        # Logit à la position t -> prédit le token t+1.
        logits = outputs.logits[:, :-1, :].float()
        targets = input_ids[:, prompt_len:]
        loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), targets.reshape(-1))
        return (loss, {}) if return_outputs else loss


def main():
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA n'est pas disponible. Vérifie ton installation PyTorch.")

    unload_ollama()
    use_bf16 = torch.cuda.is_bf16_supported()

    print("=" * 50)
    print("FINE-TUNING QWEN3-0.6B : DONNÉES -> CV LATEX")
    print("=" * 50)
    print("GPU :", torch.cuda.get_device_name(0))

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print("\nPréparation des données...")
    train_ds = prepare_dataset(TRAIN_FILE, tokenizer)
    val_ds = prepare_dataset(VAL_FILE, tokenizer)

    print("\nChargement du modèle...")
    # Pas de quantification 4 bits : le 0.6B tient en bf16 et la
    # quantification dégrade fortement un aussi petit modèle.
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        dtype=torch.bfloat16 if use_bf16 else torch.float32,
        device_map={"": 0},
    )
    model.config.use_cache = False

    lora_config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    args = TrainingArguments(
        output_dir=str(ADAPTER_PATH / "checkpoints"),
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=GRAD_ACCUMULATION,
        learning_rate=LEARNING_RATE,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        weight_decay=0.0,
        max_grad_norm=1.0,
        bf16=use_bf16,
        fp16=not use_bf16,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=EVAL_EVERY,
        save_strategy="steps",
        save_steps=EVAL_EVERY,
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        prediction_loss_only=True,
        label_names=["labels"],
        remove_unused_columns=False,
        dataloader_num_workers=0,
        report_to="none",
        seed=42,
    )

    trainer = CompletionOnlyTrainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=collate,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],
    )

    print("\nDébut de l'entraînement...")
    result = trainer.train()
    metrics = trainer.evaluate()

    print("\nLoss d'entraînement :", round(result.training_loss, 4))
    print("Loss de validation (meilleur checkpoint) :", round(metrics["eval_loss"], 4))

    trainer.model.save_pretrained(str(ADAPTER_PATH))
    tokenizer.save_pretrained(str(ADAPTER_PATH))
    print("\nAdaptateur sauvegardé dans :", ADAPTER_PATH)
    print("Évalue la qualité avec : python evaluate.py")


if __name__ == "__main__":
    main()
