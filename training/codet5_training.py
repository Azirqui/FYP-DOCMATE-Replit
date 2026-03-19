"""
CodeT5-Small Fine-Tuning for Python Code Summarization
=======================================================
Google Colab Training Script

HOW TO USE:
1. Open Google Colab (colab.research.google.com)
2. Go to Runtime > Change runtime type > Select GPU (T4)
3. Create a new notebook
4. Copy this entire script into a single cell (or split by sections)
5. Run it — training takes ~1-2 hours on free T4 GPU

WHAT THIS DOES:
- Fine-tunes CodeT5-small (60M params) on CodeSearchNet Python dataset
- Teaches the model to generate docstrings/summaries from Python code
- Saves the trained model to HuggingFace Hub for use in your backend
"""

# ============================================================
# SECTION 1: Install Dependencies
# ============================================================
# Run this cell first. It installs all required packages.

import subprocess
import sys

def install_packages():
    packages = [
        "transformers==4.44.2",
        "datasets==3.0.1",
        "accelerate==0.34.2",
        "evaluate==0.4.3",
        "rouge_score",
        "nltk",
        "sentencepiece",
        "huggingface_hub",
    ]
    for pkg in packages:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])
    print("All packages installed successfully!")

install_packages()

# ============================================================
# SECTION 2: Configuration
# ============================================================
# Change these settings before running.

CONFIG = {
    "model_name": "Salesforce/codet5-small",
    "dataset_name": "code_search_net",
    "dataset_language": "python",

    "max_input_length": 256,
    "max_target_length": 64,

    "train_samples": 50000,
    "val_samples": 5000,
    "test_samples": 2000,

    "num_epochs": 3,
    "batch_size": 8,
    "learning_rate": 5e-5,
    "weight_decay": 0.01,
    "warmup_steps": 500,
    "fp16": True,

    "output_dir": "./codet5-python-summarizer",
    "hub_model_id": None,
    "hub_token": None,
}

print("=" * 60)
print("CONFIGURATION")
print("=" * 60)
for k, v in CONFIG.items():
    if k not in ("hub_token",):
        print(f"  {k}: {v}")
print()

# ============================================================
# SECTION 3: Set Up HuggingFace Hub (Optional but Recommended)
# ============================================================
# This lets you push the trained model to HuggingFace so your
# backend can load it. If you skip this, the model saves locally.

# INSTRUCTIONS:
# 1. Create a free account at huggingface.co
# 2. Go to Settings > Access Tokens > Create new token (write access)
# 3. Paste your token below

# Uncomment and fill these to push to HuggingFace Hub:
# CONFIG["hub_model_id"] = "YOUR_HF_USERNAME/codet5-python-summarizer"
# CONFIG["hub_token"] = "hf_YOUR_TOKEN_HERE"

if CONFIG["hub_token"]:
    from huggingface_hub import login
    login(token=CONFIG["hub_token"])
    print(f"Logged in to HuggingFace Hub. Model will be pushed to: {CONFIG['hub_model_id']}")
else:
    print("HuggingFace Hub login skipped. Model will be saved locally only.")
    print("To push to Hub later, set hub_model_id and hub_token in CONFIG above.")
print()

# ============================================================
# SECTION 4: Load and Explore the Dataset
# ============================================================

from datasets import load_dataset
import random

print("Loading CodeSearchNet Python dataset...")
print("(This may take a few minutes on first run)")
print()

dataset = load_dataset(CONFIG["dataset_name"], CONFIG["dataset_language"])

print(f"Dataset loaded!")
print(f"  Train:      {len(dataset['train']):,} samples")
print(f"  Validation: {len(dataset['validation']):,} samples")
print(f"  Test:       {len(dataset['test']):,} samples")
print()

print("Sample data point:")
sample = dataset["train"][random.randint(0, len(dataset["train"]) - 1)]
print(f"  Code (first 200 chars): {sample['whole_func_string'][:200]}...")
print(f"  Docstring: {sample['func_documentation_string'][:150]}...")
print()

# ============================================================
# SECTION 5: Preprocess the Data
# ============================================================

from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained(CONFIG["model_name"])

def preprocess_function(examples):
    codes = []
    summaries = []

    for code, docstring in zip(examples["whole_func_string"], examples["func_documentation_string"]):
        if not code or not docstring:
            codes.append("")
            summaries.append("")
            continue

        clean_code = code.strip()
        clean_doc = docstring.strip().split("\n")[0].strip()

        if len(clean_doc) < 10 or len(clean_code) < 20:
            codes.append("")
            summaries.append("")
            continue

        codes.append(f"summarize python: {clean_code}")
        summaries.append(clean_doc)

    model_inputs = tokenizer(
        codes,
        max_length=CONFIG["max_input_length"],
        padding="max_length",
        truncation=True,
    )

    labels = tokenizer(
        summaries,
        max_length=CONFIG["max_target_length"],
        padding="max_length",
        truncation=True,
    )

    labels_ids = labels["input_ids"]
    labels_ids = [
        [(l if l != tokenizer.pad_token_id else -100) for l in label]
        for label in labels_ids
    ]

    model_inputs["labels"] = labels_ids
    return model_inputs


print("Preprocessing dataset...")
print(f"  Using {CONFIG['train_samples']} train, {CONFIG['val_samples']} val, {CONFIG['test_samples']} test samples")

train_subset = dataset["train"].select(range(min(CONFIG["train_samples"], len(dataset["train"]))))
val_subset = dataset["validation"].select(range(min(CONFIG["val_samples"], len(dataset["validation"]))))
test_subset = dataset["test"].select(range(min(CONFIG["test_samples"], len(dataset["test"]))))

tokenized_train = train_subset.map(
    preprocess_function, batched=True, remove_columns=dataset["train"].column_names,
    desc="Tokenizing train set"
)
tokenized_val = val_subset.map(
    preprocess_function, batched=True, remove_columns=dataset["validation"].column_names,
    desc="Tokenizing validation set"
)
tokenized_test = test_subset.map(
    preprocess_function, batched=True, remove_columns=dataset["test"].column_names,
    desc="Tokenizing test set"
)

tokenized_train = tokenized_train.filter(lambda x: any(l != -100 for l in x["labels"]))
tokenized_val = tokenized_val.filter(lambda x: any(l != -100 for l in x["labels"]))
tokenized_test = tokenized_test.filter(lambda x: any(l != -100 for l in x["labels"]))

print(f"After filtering empty samples:")
print(f"  Train: {len(tokenized_train):,}")
print(f"  Val:   {len(tokenized_val):,}")
print(f"  Test:  {len(tokenized_test):,}")
print()

# ============================================================
# SECTION 6: Load the Model
# ============================================================

from transformers import AutoModelForSeq2SeqLM
import torch

print(f"Loading model: {CONFIG['model_name']}")
model = AutoModelForSeq2SeqLM.from_pretrained(CONFIG["model_name"])

total_params = sum(p.numel() for p in model.parameters())
trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
print(f"  Total parameters:     {total_params:,}")
print(f"  Trainable parameters: {trainable_params:,}")
print(f"  Model size:           ~{total_params * 4 / 1024 / 1024:.0f} MB (fp32)")
print()

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Training device: {device}")
if device == "cuda":
    print(f"  GPU: {torch.cuda.get_device_name(0)}")
    print(f"  GPU Memory: {torch.cuda.get_device_properties(0).total_mem / 1024**3:.1f} GB")
else:
    print("  WARNING: No GPU detected! Training will be very slow.")
    print("  Go to Runtime > Change runtime type > GPU")
print()

# ============================================================
# SECTION 7: Set Up Training
# ============================================================

import numpy as np
import evaluate
import nltk

nltk.download("punkt", quiet=True)
nltk.download("punkt_tab", quiet=True)

rouge_metric = evaluate.load("rouge")

def compute_metrics(eval_pred):
    predictions, labels = eval_pred

    labels = np.where(labels != -100, labels, tokenizer.pad_token_id)

    decoded_preds = tokenizer.batch_decode(predictions, skip_special_tokens=True)
    decoded_labels = tokenizer.batch_decode(labels, skip_special_tokens=True)

    decoded_preds = [pred.strip() for pred in decoded_preds]
    decoded_labels = [label.strip() for label in decoded_labels]

    result = rouge_metric.compute(
        predictions=decoded_preds,
        references=decoded_labels,
        use_stemmer=True,
    )

    result = {k: round(v * 100, 2) for k, v in result.items()}

    avg_pred_len = np.mean([len(pred.split()) for pred in decoded_preds])
    result["avg_gen_length"] = round(avg_pred_len, 1)

    return result


from transformers import Seq2SeqTrainingArguments, Seq2SeqTrainer, DataCollatorForSeq2Seq

training_args = Seq2SeqTrainingArguments(
    output_dir=CONFIG["output_dir"],
    num_train_epochs=CONFIG["num_epochs"],
    per_device_train_batch_size=CONFIG["batch_size"],
    per_device_eval_batch_size=CONFIG["batch_size"],
    learning_rate=CONFIG["learning_rate"],
    weight_decay=CONFIG["weight_decay"],
    warmup_steps=CONFIG["warmup_steps"],
    fp16=CONFIG["fp16"] and device == "cuda",
    eval_strategy="epoch",
    save_strategy="epoch",
    logging_steps=100,
    predict_with_generate=True,
    generation_max_length=CONFIG["max_target_length"],
    load_best_model_at_end=True,
    metric_for_best_model="rouge1",
    greater_is_better=True,
    report_to="none",
    save_total_limit=2,
    push_to_hub=bool(CONFIG["hub_model_id"]),
    hub_model_id=CONFIG["hub_model_id"],
    hub_token=CONFIG["hub_token"],
)

data_collator = DataCollatorForSeq2Seq(tokenizer, model=model)

trainer = Seq2SeqTrainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_train,
    eval_dataset=tokenized_val,
    tokenizer=tokenizer,
    data_collator=data_collator,
    compute_metrics=compute_metrics,
)

print("Training configuration:")
print(f"  Epochs:         {CONFIG['num_epochs']}")
print(f"  Batch size:     {CONFIG['batch_size']}")
print(f"  Learning rate:  {CONFIG['learning_rate']}")
print(f"  FP16:           {CONFIG['fp16'] and device == 'cuda'}")
print(f"  Total steps:    ~{len(tokenized_train) // CONFIG['batch_size'] * CONFIG['num_epochs']:,}")
print()

# ============================================================
# SECTION 8: Train the Model
# ============================================================

print("=" * 60)
print("STARTING TRAINING")
print("=" * 60)
print("This will take approximately 1-2 hours on a T4 GPU.")
print()

train_result = trainer.train()

print()
print("=" * 60)
print("TRAINING COMPLETE!")
print("=" * 60)
print(f"  Training loss:    {train_result.training_loss:.4f}")
print(f"  Training time:    {train_result.metrics['train_runtime']:.0f} seconds")
print(f"  Samples/second:   {train_result.metrics['train_samples_per_second']:.1f}")
print()

# ============================================================
# SECTION 9: Evaluate on Test Set
# ============================================================

print("Evaluating on test set...")
eval_results = trainer.evaluate(tokenized_test)

print()
print("=" * 60)
print("TEST SET RESULTS")
print("=" * 60)
for key, value in eval_results.items():
    if key.startswith("eval_"):
        clean_key = key.replace("eval_", "")
        print(f"  {clean_key}: {value}")
print()
print("WHAT THESE SCORES MEAN:")
print("  rouge1:  Overlap of individual words (higher = better, 30+ is good)")
print("  rouge2:  Overlap of word pairs (higher = better, 15+ is good)")
print("  rougeL:  Longest common subsequence (higher = better, 25+ is good)")
print()

# ============================================================
# SECTION 10: Save the Model
# ============================================================

print("Saving model...")

trainer.save_model(CONFIG["output_dir"])
tokenizer.save_pretrained(CONFIG["output_dir"])

if CONFIG["hub_model_id"] and CONFIG["hub_token"]:
    print(f"Pushing to HuggingFace Hub: {CONFIG['hub_model_id']}")
    trainer.push_to_hub(commit_message="Fine-tuned CodeT5-small for Python code summarization")
    print(f"Model available at: https://huggingface.co/{CONFIG['hub_model_id']}")
else:
    print(f"Model saved locally to: {CONFIG['output_dir']}")
    print()
    print("TO PUSH TO HUGGINGFACE HUB LATER:")
    print("  1. Set CONFIG['hub_model_id'] = 'YOUR_USERNAME/codet5-python-summarizer'")
    print("  2. Set CONFIG['hub_token'] = 'hf_YOUR_TOKEN'")
    print("  3. Run:")
    print("     from huggingface_hub import HfApi")
    print("     api = HfApi()")
    print(f"     api.upload_folder(folder_path='{CONFIG['output_dir']}', repo_id='YOUR_USERNAME/codet5-python-summarizer')")
print()

# ============================================================
# SECTION 11: Test the Trained Model
# ============================================================

print("=" * 60)
print("TESTING THE TRAINED MODEL")
print("=" * 60)
print()

test_functions = [
    '''def calculate_total(items, tax_rate=0.1):
    subtotal = sum(item.price for item in items)
    return subtotal * (1 + tax_rate)''',

    '''def find_user_by_email(email, users):
    for user in users:
        if user.email == email:
            return user
    return None''',

    '''class DatabaseConnection:
    def __init__(self, host, port, database):
        self.host = host
        self.port = port
        self.database = database
        self.connection = None

    def connect(self):
        self.connection = psycopg2.connect(
            host=self.host, port=self.port, dbname=self.database
        )

    def disconnect(self):
        if self.connection:
            self.connection.close()
            self.connection = None''',

    '''def validate_password(password):
    if len(password) < 8:
        return False
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    return has_upper and has_lower and has_digit''',

    '''async def fetch_json(url, headers=None, timeout=30):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, timeout=timeout) as response:
            response.raise_for_status()
            return await response.json()''',
]

model.eval()
model.to(device)

for i, code in enumerate(test_functions, 1):
    input_text = f"summarize python: {code}"
    input_ids = tokenizer(
        input_text,
        max_length=CONFIG["max_input_length"],
        padding="max_length",
        truncation=True,
        return_tensors="pt",
    ).input_ids.to(device)

    with torch.no_grad():
        outputs = model.generate(
            input_ids,
            max_length=CONFIG["max_target_length"],
            num_beams=4,
            early_stopping=True,
        )

    summary = tokenizer.decode(outputs[0], skip_special_tokens=True)

    print(f"Test {i}:")
    print(f"  Code:    {code.split(chr(10))[0].strip()}")
    print(f"  Summary: {summary}")
    print()

print("=" * 60)
print("ALL DONE!")
print("=" * 60)
print()
print("NEXT STEPS:")
print("1. Note your HuggingFace model ID (or download the model files)")
print("2. In your backend project, set these environment variables:")
print("   HUGGINGFACE_MODEL_ID=YOUR_USERNAME/codet5-python-summarizer")
print("   HUGGINGFACE_API_TOKEN=hf_YOUR_TOKEN")
print("3. The backend will automatically use your fine-tuned model for code summarization")
print("4. The LLM (Groq/Gemini) will continue handling project-level documentation")
