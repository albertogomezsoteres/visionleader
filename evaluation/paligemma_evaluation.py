"""
PaliGemma Model Evaluation for Indoor Navigation
=================================================
This script evaluates different PaliGemma models on indoor navigation images.
Designed to run in Google Colab with GPU.

Models to evaluate:
- google/paligemma-3b-pt-224
- google/paligemma-3b-pt-448
- google/paligemma-3b-mix-224
- google/paligemma-3b-mix-448

Metrics:
- BLEU score
- METEOR score
- BERTScore
"""

import os
import json
import torch
from PIL import Image
from transformers import AutoProcessor, PaliGemmaForConditionalGeneration
from datasets import load_metric
import pandas as pd
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# ============================================
# CONFIGURATION
# ============================================

# Models to evaluate
MODELS = [
    "google/paligemma-3b-pt-224",
    "google/paligemma-3b-pt-448",
    "google/paligemma-3b-mix-224",
    "google/paligemma-3b-mix-448",
]

# Paths (update these for your Colab environment)
DATA_DIR = "data"
DATASET_FILE = "data/dataset.json"
RESULTS_DIR = "results"

# ============================================
# LOAD DATASET
# ============================================

def load_dataset_json(dataset_path):
    """Load the dataset metadata."""
    with open(dataset_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def prepare_evaluation_samples(dataset):
    """Prepare samples for evaluation."""
    samples = []
    for img_data in dataset['images']:
        # Use first suggested question and expected answer
        if img_data.get('suggested_questions') and img_data.get('expected_answer'):
            samples.append({
                'id': img_data['id'],
                'image_path': img_data['filename'],
                'category': img_data['category'],
                'question': img_data['suggested_questions'][0],
                'expected_answer': img_data['expected_answer'],
                'description': img_data['description']
            })
    return samples

# ============================================
# MODEL LOADING
# ============================================

def load_model(model_id, device="cuda"):
    """Load PaliGemma model and processor."""
    print(f"Loading model: {model_id}")
    
    processor = AutoProcessor.from_pretrained(model_id)
    model = PaliGemmaForConditionalGeneration.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
        device_map=device
    )
    model.eval()
    
    return model, processor

# ============================================
# INFERENCE
# ============================================

def run_inference(model, processor, image_path, question, device="cuda"):
    """Run inference on a single image."""
    # Load image
    image = Image.open(image_path).convert("RGB")
    
    # Prepare prompt
    prompt = f"<image>\n{question}"
    
    # Process inputs
    inputs = processor(
        text=prompt,
        images=image,
        return_tensors="pt"
    ).to(device, torch.bfloat16)
    
    # Generate
    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=100,
            do_sample=False
        )
    
    # Decode
    generated_text = processor.decode(output[0], skip_special_tokens=True)
    
    # Extract answer (remove the prompt part)
    answer = generated_text.split(question)[-1].strip()
    
    return answer

# ============================================
# METRICS
# ============================================

def compute_metrics(predictions, references):
    """Compute BLEU, METEOR, and BERTScore."""
    results = {}
    
    # BLEU Score
    try:
        from sacrebleu.metrics import BLEU
        bleu = BLEU()
        # BLEU expects list of references for each prediction
        refs = [[ref] for ref in references]
        bleu_score = bleu.corpus_score(predictions, refs)
        results['bleu'] = bleu_score.score
    except Exception as e:
        print(f"BLEU calculation error: {e}")
        results['bleu'] = None
    
    # METEOR Score
    try:
        import nltk
        nltk.download('wordnet', quiet=True)
        nltk.download('punkt', quiet=True)
        nltk.download('omw-1.4', quiet=True)
        from nltk.translate.meteor_score import meteor_score
        from nltk.tokenize import word_tokenize
        
        meteor_scores = []
        for pred, ref in zip(predictions, references):
            score = meteor_score([word_tokenize(ref)], word_tokenize(pred))
            meteor_scores.append(score)
        results['meteor'] = sum(meteor_scores) / len(meteor_scores)
    except Exception as e:
        print(f"METEOR calculation error: {e}")
        results['meteor'] = None
    
    # BERTScore
    try:
        from bert_score import score as bert_score
        P, R, F1 = bert_score(predictions, references, lang="en", verbose=False)
        results['bertscore_precision'] = P.mean().item()
        results['bertscore_recall'] = R.mean().item()
        results['bertscore_f1'] = F1.mean().item()
    except Exception as e:
        print(f"BERTScore calculation error: {e}")
        results['bertscore_f1'] = None
    
    return results

# ============================================
# EVALUATION LOOP
# ============================================

def evaluate_model(model_id, samples, data_dir, device="cuda"):
    """Evaluate a single model on all samples."""
    print(f"\n{'='*50}")
    print(f"Evaluating: {model_id}")
    print(f"{'='*50}")
    
    # Load model
    model, processor = load_model(model_id, device)
    
    predictions = []
    references = []
    detailed_results = []
    
    for sample in tqdm(samples, desc="Processing images"):
        image_path = os.path.join(data_dir, sample['image_path'])
        
        if not os.path.exists(image_path):
            print(f"Warning: Image not found: {image_path}")
            continue
        
        # Run inference
        try:
            prediction = run_inference(
                model, processor, 
                image_path, 
                sample['question'],
                device
            )
        except Exception as e:
            print(f"Error processing {image_path}: {e}")
            prediction = ""
        
        predictions.append(prediction)
        references.append(sample['expected_answer'])
        
        detailed_results.append({
            'id': sample['id'],
            'category': sample['category'],
            'image': sample['image_path'],
            'question': sample['question'],
            'expected': sample['expected_answer'],
            'predicted': prediction
        })
    
    # Compute metrics
    metrics = compute_metrics(predictions, references)
    
    # Clean up
    del model
    del processor
    torch.cuda.empty_cache()
    
    return {
        'model': model_id,
        'metrics': metrics,
        'detailed_results': detailed_results
    }

# ============================================
# MAIN
# ============================================

def main():
    """Main evaluation function."""
    print("PaliGemma Indoor Navigation Evaluation")
    print("="*50)
    
    # Check device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    
    if device == "cpu":
        print("WARNING: Running on CPU will be very slow!")
    
    # Create results directory
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    # Load dataset
    print("\nLoading dataset...")
    dataset = load_dataset_json(DATASET_FILE)
    samples = prepare_evaluation_samples(dataset)
    print(f"Loaded {len(samples)} samples for evaluation")
    
    # Evaluate each model
    all_results = []
    
    for model_id in MODELS:
        try:
            result = evaluate_model(model_id, samples, DATA_DIR, device)
            all_results.append(result)
            
            # Save intermediate results
            with open(f"{RESULTS_DIR}/results_{model_id.replace('/', '_')}.json", 'w') as f:
                json.dump(result, f, indent=2)
                
        except Exception as e:
            print(f"Error evaluating {model_id}: {e}")
            continue
    
    # Create comparison summary
    summary = []
    for result in all_results:
        summary.append({
            'Model': result['model'],
            'BLEU': result['metrics'].get('bleu'),
            'METEOR': result['metrics'].get('meteor'),
            'BERTScore F1': result['metrics'].get('bertscore_f1')
        })
    
    summary_df = pd.DataFrame(summary)
    print("\n" + "="*50)
    print("RESULTS SUMMARY")
    print("="*50)
    print(summary_df.to_string(index=False))
    
    # Save summary
    summary_df.to_csv(f"{RESULTS_DIR}/model_comparison.csv", index=False)
    
    # Save all results
    with open(f"{RESULTS_DIR}/all_results.json", 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\nResults saved to {RESULTS_DIR}/")
    
    return all_results

if __name__ == "__main__":
    main()
