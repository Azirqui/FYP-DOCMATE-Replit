# Fine-Tuning CodeT5 for Python Code Summarization

This guide walks you through fine-tuning the CodeT5-small model on the CodeSearchNet dataset using Google Colab (free GPU).

## What You'll Get

A custom-trained model that generates summaries/docstrings for Python code. This model:
- Is based on CodeT5-small (60M parameters) by Salesforce
- Is trained on ~50,000 Python code-docstring pairs from CodeSearchNet
- Can generate one-line summaries for Python functions and classes
- Runs alongside the LLM (Groq/Gemini) in your backend

## Prerequisites

- A Google account (for Colab)
- A HuggingFace account (free, for hosting the model) — https://huggingface.co/join

## Step-by-Step Instructions

### Step 1: Create a HuggingFace Account and Token

1. Go to https://huggingface.co/join and create a free account
2. Go to Settings > Access Tokens > New Token
3. Name it anything (e.g., "colab-training")
4. Select **Write** access
5. Copy the token (starts with `hf_`)
6. Save it somewhere — you'll need it in Step 4

### Step 2: Open Google Colab

1. Go to https://colab.research.google.com
2. Click **New Notebook**
3. Go to **Runtime > Change runtime type**
4. Select **T4 GPU** (free tier)
5. Click **Save**

### Step 3: Copy the Training Script

1. Open the file `training/codet5_training.py` from this project
2. Select all the code (Ctrl+A) and copy it (Ctrl+C)
3. In your Colab notebook, paste it into a single cell (Ctrl+V)

### Step 4: Configure Your Settings

Before running, find these two lines near the top of the script (in SECTION 3) and uncomment/edit them:

```python
CONFIG["hub_model_id"] = "YOUR_HF_USERNAME/codet5-python-summarizer"
CONFIG["hub_token"] = "hf_YOUR_TOKEN_HERE"
```

Replace:
- `YOUR_HF_USERNAME` with your HuggingFace username
- `hf_YOUR_TOKEN_HERE` with the token from Step 1

### Step 5: Run the Training

1. Click the **Play** button on the cell (or press Shift+Enter)
2. Wait for it to complete (~1-2 hours)
3. You'll see progress logs with loss values decreasing
4. At the end, you'll see:
   - ROUGE scores (quality metrics)
   - Test examples with generated summaries
   - Confirmation that the model was pushed to HuggingFace

### Step 6: Verify Your Model

1. Go to https://huggingface.co/YOUR_USERNAME/codet5-python-summarizer
2. You should see your trained model with files
3. Try the "Inference API" widget on the page to test it

### Step 7: Connect to Your Backend

1. In your Replit project, add these environment variables (Secrets):
   - `HUGGINGFACE_MODEL_ID` = `YOUR_USERNAME/codet5-python-summarizer`
   - `HUGGINGFACE_API_TOKEN` = `hf_YOUR_TOKEN`
2. Restart the API Server
3. The backend will now use your fine-tuned model for code summarization

## Understanding the Results

After training, you'll see ROUGE scores:

| Metric | What it measures | Good score |
|--------|-----------------|------------|
| ROUGE-1 | Word overlap | 30+ |
| ROUGE-2 | Word pair overlap | 15+ |
| ROUGE-L | Longest common sequence | 25+ |

These measure how similar the model's generated summaries are to human-written docstrings.

## Training Configuration

You can adjust these settings in the CONFIG section:

| Setting | Default | Description |
|---------|---------|-------------|
| `train_samples` | 50,000 | More = better quality but slower training |
| `num_epochs` | 3 | More passes over data (3 is usually enough) |
| `batch_size` | 8 | Increase if you have more GPU memory |
| `learning_rate` | 5e-5 | Standard for fine-tuning transformers |
| `max_input_length` | 256 | Max tokens for input code |
| `max_target_length` | 64 | Max tokens for generated summary |

## Troubleshooting

**"CUDA out of memory"**: Reduce `batch_size` to 4 or `train_samples` to 30000.

**"No GPU detected"**: Go to Runtime > Change runtime type > Select T4 GPU.

**Training is very slow**: Make sure you selected GPU runtime, not CPU.

**Model not appearing on HuggingFace**: Check that your token has Write access and the model ID format is correct (`username/model-name`).

## Architecture

After integration, the documentation pipeline works like this:

```
User uploads Python code
        |
        v
   AST Parser (code_doc_ai/core)
   Extracts classes, functions, structure
        |
        v
   CodeT5 Model (your fine-tuned model)
   Generates per-function/class summaries
        |
        v
   LLM (Groq/Gemini)
   Uses summaries + structure to write full docs
        |
        v
   Complete Documentation
   Project overview, module docs, UML diagrams
```

This hybrid approach is your key differentiator: a custom-trained model handles granular code understanding, while the LLM handles natural language composition.
