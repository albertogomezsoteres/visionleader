"""
Metrics module for evaluating PaliGemma model outputs.

This module provides functions to calculate various metrics:
- Exact Match: For closed questions (yes/no)
- Keyword F1/Recall/Precision: For element detection
- BERTScore: For semantic similarity
- VRAM Usage: GPU memory tracking
"""

import re
from typing import List, Dict, Tuple, Optional
from collections import Counter
import numpy as np


def normalize_text(text: str) -> str:
    """
    Normalize text for comparison.
    
    Args:
        text: Input text
    
    Returns:
        Normalized lowercase text with extra whitespace removed
    """
    if text is None:
        return ""
    # Convert to lowercase
    text = text.lower()
    # Remove punctuation except apostrophes
    text = re.sub(r"[^\w\s']", " ", text)
    # Remove extra whitespace
    text = " ".join(text.split())
    return text


def tokenize(text: str) -> List[str]:
    """
    Simple tokenization by whitespace.
    
    Args:
        text: Input text
    
    Returns:
        List of tokens
    """
    return normalize_text(text).split()


# ============================================================
# VRAM USAGE TRACKING
# ============================================================

def get_gpu_memory_usage() -> Dict[str, float]:
    """
    Get current GPU memory usage.
    
    Returns:
        Dictionary with allocated and reserved memory in GB
    """
    try:
        import torch
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated() / (1024 ** 3)  # GB
            reserved = torch.cuda.memory_reserved() / (1024 ** 3)  # GB
            max_allocated = torch.cuda.max_memory_allocated() / (1024 ** 3)  # GB
            return {
                "allocated_gb": round(allocated, 2),
                "reserved_gb": round(reserved, 2),
                "max_allocated_gb": round(max_allocated, 2),
                "available": True
            }
    except Exception as e:
        pass
    
    return {
        "allocated_gb": 0.0,
        "reserved_gb": 0.0,
        "max_allocated_gb": 0.0,
        "available": False
    }


def reset_gpu_memory_stats() -> None:
    """Reset GPU memory statistics for fresh tracking."""
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
    except Exception:
        pass


# ============================================================
# EXACT MATCH
# ============================================================

def calculate_exact_match(prediction: str, expected: str) -> float:
    """
    Calculate exact match score (strict).
    
    Args:
        prediction: Model prediction
        expected: Expected answer
    
    Returns:
        1.0 if match, 0.0 otherwise
    """
    pred_normalized = normalize_text(prediction)
    expected_normalized = normalize_text(expected)
    
    # Check if expected answer is contained in prediction
    if expected_normalized in pred_normalized:
        return 1.0
    
    # Also check for common variations
    if expected_normalized == "yes":
        if any(word in pred_normalized for word in ["yes", "there is", "there are", "i can see"]):
            return 1.0
    elif expected_normalized == "no":
        if any(word in pred_normalized for word in ["no", "there is no", "there are no", "i cannot see", "i don't see"]):
            return 1.0
    
    return 0.0


def calculate_semantic_exact_match(
    prediction: str, 
    expected: str, 
    acceptable_answers: Optional[List[str]] = None
) -> float:
    """
    Calculate semantic exact match score.
    
    This is a more flexible version that accepts semantically equivalent answers.
    For example, if asking "Is there a corridor?", responses like "hallway" or 
    "corridor" are accepted as equivalent to "yes".
    
    Args:
        prediction: Model prediction
        expected: Expected answer (e.g., "yes")
        acceptable_answers: List of acceptable alternative answers
    
    Returns:
        1.0 if match (exact or semantic), 0.0 otherwise
    """
    pred_normalized = normalize_text(prediction)
    expected_normalized = normalize_text(expected)
    
    # First, try strict exact match
    if expected_normalized in pred_normalized:
        return 1.0
    
    # Check common yes/no variations
    if expected_normalized == "yes":
        yes_indicators = ["yes", "there is", "there are", "i can see", "it is", "this is"]
        if any(indicator in pred_normalized for indicator in yes_indicators):
            return 1.0
    elif expected_normalized == "no":
        no_indicators = ["no", "there is no", "there are no", "i cannot see", "i don't see", "not a", "isn't", "aren't"]
        if any(indicator in pred_normalized for indicator in no_indicators):
            return 1.0
    
    # Check acceptable alternatives (semantic equivalents)
    if acceptable_answers:
        for acceptable in acceptable_answers:
            acceptable_normalized = normalize_text(acceptable)
            if acceptable_normalized in pred_normalized:
                return 1.0
            # Also check if any token from acceptable answer is in prediction
            acceptable_tokens = acceptable_normalized.split()
            pred_tokens = pred_normalized.split()
            if any(token in pred_tokens for token in acceptable_tokens if len(token) > 2):
                return 1.0
    
    return 0.0


def calculate_exact_match_batch(
    predictions: List[str],
    expected_answers: List[str],
    acceptable_answers_list: Optional[List[List[str]]] = None,
    use_semantic: bool = True
) -> Dict[str, float]:
    """
    Calculate exact match for a batch of predictions.
    
    Args:
        predictions: List of model predictions
        expected_answers: List of expected answers
        acceptable_answers_list: Optional list of acceptable answer lists for semantic matching
        use_semantic: Whether to use semantic matching (default True)
    
    Returns:
        Dictionary with accuracy and individual scores
    """
    if use_semantic and acceptable_answers_list:
        scores = [
            calculate_semantic_exact_match(pred, exp, acc)
            for pred, exp, acc in zip(predictions, expected_answers, acceptable_answers_list)
        ]
    elif use_semantic:
        scores = [
            calculate_semantic_exact_match(pred, exp, None)
            for pred, exp in zip(predictions, expected_answers)
        ]
    else:
        scores = [
            calculate_exact_match(pred, exp)
            for pred, exp in zip(predictions, expected_answers)
        ]
    
    return {
        "accuracy": np.mean(scores),
        "correct": sum(scores),
        "total": len(scores),
        "individual_scores": scores
    }


# ============================================================
# KEYWORD F1 / RECALL / PRECISION
# ============================================================

def calculate_keyword_metrics(
    prediction: str,
    expected_keywords: List[str],
    expected_keywords_primary: Optional[List[str]] = None,
    expected_keywords_secondary: Optional[List[str]] = None
) -> Dict[str, float]:
    """
    Calculate keyword-based metrics.
    
    Args:
        prediction: Model prediction
        expected_keywords: List of expected keywords (all)
        expected_keywords_primary: Optional list of primary (essential) keywords
        expected_keywords_secondary: Optional list of secondary (detail) keywords
    
    Returns:
        Dictionary with precision, recall, F1 scores, and primary/secondary recalls
    """
    if not expected_keywords:
        return {
            "precision": 0.0, "recall": 0.0, "f1": 0.0, 
            "recall_primary": 0.0, "recall_secondary": 0.0,
            "matched_keywords": []
        }
    
    # Common stopwords to filter out for precision calculation
    STOPWORDS = {
        "the", "with", "and", "shows", "image", "a", "an", "is", "are", 
        "in", "on", "at", "to", "of", "for", "this", "that", "these", 
        "those", "can", "see", "visible", "elements", "describe", "list"
    }
    
    pred_normalized = normalize_text(prediction)
    pred_tokens = set(tokenize(prediction))
    pred_words = tokenize(prediction)  # List of all words for precision calculation
    
    # Count matched keywords (all)
    matched = []
    for keyword in expected_keywords:
        keyword_normalized = normalize_text(keyword)
        # Check if keyword or any of its tokens are in prediction
        if keyword_normalized in pred_normalized:
            matched.append(keyword)
        elif any(token in pred_tokens for token in tokenize(keyword)):
            matched.append(keyword)
    
    # Count matched primary keywords
    matched_primary = []
    if expected_keywords_primary:
        for keyword in expected_keywords_primary:
            keyword_normalized = normalize_text(keyword)
            if keyword_normalized in pred_normalized:
                matched_primary.append(keyword)
            elif any(token in pred_tokens for token in tokenize(keyword)):
                matched_primary.append(keyword)
    
    # Count matched secondary keywords
    matched_secondary = []
    if expected_keywords_secondary:
        for keyword in expected_keywords_secondary:
            keyword_normalized = normalize_text(keyword)
            if keyword_normalized in pred_normalized:
                matched_secondary.append(keyword)
            elif any(token in pred_tokens for token in tokenize(keyword)):
                matched_secondary.append(keyword)
    
    # Calculate metrics
    true_positives = len(matched)
    
    # Recall: of the expected keywords, how many did we find?
    recall = true_positives / len(expected_keywords) if expected_keywords else 0.0
    
    # Signal Recall Primary: if ANY primary keyword found, it's a success (signal detected)
    # This measures: "Did the model capture the main navigation signal?" not "Did it list all things?"
    if expected_keywords_primary and len(expected_keywords_primary) > 0:
        recall_primary = 1.0 if len(matched_primary) > 0 else 0.0
    else:
        recall_primary = 0.0
    
    # Recall Secondary: of the secondary keywords, how many did we find?
    recall_secondary = len(matched_secondary) / len(expected_keywords_secondary) if expected_keywords_secondary and len(expected_keywords_secondary) > 0 else 0.0
    
    # Precision: of the words mentioned, how many are expected keywords?
    # Filter out stopwords for more fair precision calculation
    unique_pred_words = set(
        w for w in pred_words 
        if len(w) > 2 and w not in STOPWORDS
    )
    
    if len(unique_pred_words) > 0:
        # Precision: ratio of matched keywords to total unique relevant words mentioned
        # This measures: "of all relevant words you said, how many were expected keywords?"
        precision = true_positives / len(unique_pred_words) if unique_pred_words else 0.0
    else:
        # If no relevant words mentioned, precision is 0
        precision = 0.0
    
    # F1 Score
    if precision + recall > 0:
        f1 = 2 * (precision * recall) / (precision + recall)
    else:
        f1 = 0.0
    
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "recall_primary": recall_primary,
        "recall_secondary": recall_secondary,
        "matched_keywords": matched,
        "matched_primary": matched_primary,
        "matched_secondary": matched_secondary,
        "expected_keywords": expected_keywords,
        "num_matched": true_positives,
        "num_expected": len(expected_keywords),
        "num_matched_primary": len(matched_primary),
        "num_expected_primary": len(expected_keywords_primary) if expected_keywords_primary else 0,
        "num_matched_secondary": len(matched_secondary),
        "num_expected_secondary": len(expected_keywords_secondary) if expected_keywords_secondary else 0
    }


def calculate_keyword_f1_batch(
    predictions: List[str],
    expected_keywords_list: List[List[str]],
    expected_keywords_primary_list: Optional[List[List[str]]] = None,
    expected_keywords_secondary_list: Optional[List[List[str]]] = None
) -> Dict[str, float]:
    """
    Calculate keyword F1 for a batch of predictions.
    
    Args:
        predictions: List of model predictions
        expected_keywords_list: List of expected keyword lists
        expected_keywords_primary_list: Optional list of primary keyword lists
        expected_keywords_secondary_list: Optional list of secondary keyword lists
    
    Returns:
        Dictionary with average metrics including recall_primary and recall_secondary
    """
    # Prepare primary and secondary lists (default to None if not provided)
    if expected_keywords_primary_list is None:
        expected_keywords_primary_list = [None] * len(predictions)
    if expected_keywords_secondary_list is None:
        expected_keywords_secondary_list = [None] * len(predictions)
    
    all_metrics = [
        calculate_keyword_metrics(
            pred, 
            keywords,
            primary,
            secondary
        )
        for pred, keywords, primary, secondary in zip(
            predictions, 
            expected_keywords_list,
            expected_keywords_primary_list,
            expected_keywords_secondary_list
        )
    ]
    
    # Calculate averages, including recall_primary and recall_secondary if available
    avg_recall_primary = None
    avg_recall_secondary = None
    
    # Only calculate if at least one item has primary keywords
    primary_metrics = [m["recall_primary"] for m in all_metrics if m.get("num_expected_primary", 0) > 0]
    if primary_metrics:
        avg_recall_primary = np.mean(primary_metrics)
    
    # Only calculate if at least one item has secondary keywords
    secondary_metrics = [m["recall_secondary"] for m in all_metrics if m.get("num_expected_secondary", 0) > 0]
    if secondary_metrics:
        avg_recall_secondary = np.mean(secondary_metrics)
    
    result = {
        "avg_precision": np.mean([m["precision"] for m in all_metrics]),
        "avg_recall": np.mean([m["recall"] for m in all_metrics]),
        "avg_f1": np.mean([m["f1"] for m in all_metrics]),
        "individual_metrics": all_metrics
    }
    
    if avg_recall_primary is not None:
        result["avg_recall_primary"] = avg_recall_primary
    if avg_recall_secondary is not None:
        result["avg_recall_secondary"] = avg_recall_secondary
    
    return result


# ============================================================
# BERTScore
# ============================================================

def calculate_bertscore(
    predictions: List[str],
    references: List[str],
    lang: str = "en",
    model_type: str = "microsoft/deberta-xlarge-mnli"
) -> Dict[str, float]:
    """
    Calculate BERTScore for semantic similarity.
    
    Args:
        predictions: List of model predictions
        references: List of reference answers
        lang: Language code
        model_type: BERT model to use
    
    Returns:
        Dictionary with precision, recall, and F1 BERTScores
    """
    try:
        from bert_score import score as bert_score
    except ImportError:
        print("Warning: bert_score not installed. Install with: pip install bert_score")
        return {
            "bertscore_precision": 0.0,
            "bertscore_recall": 0.0,
            "bertscore_f1": 0.0,
            "error": "bert_score not installed"
        }
    
    # Calculate BERTScore
    P, R, F1 = bert_score(
        predictions,
        references,
        lang=lang,
        model_type=model_type,
        verbose=False
    )
    
    return {
        "bertscore_precision": float(P.mean()),
        "bertscore_recall": float(R.mean()),
        "bertscore_f1": float(F1.mean()),
        "individual_precision": [float(p) for p in P],
        "individual_recall": [float(r) for r in R],
        "individual_f1": [float(f) for f in F1]
    }


# ============================================================
# MAIN METRICS CALCULATOR
# ============================================================

def calculate_all_metrics(
    results: List[Dict],
    calculate_bertscore_metric: bool = True,
    vram_usage: Optional[Dict] = None
) -> Dict[str, Dict]:
    """
    Calculate all metrics for a set of inference results.
    
    Args:
        results: List of inference result dictionaries
        calculate_bertscore_metric: Whether to calculate BERTScore
        vram_usage: Optional VRAM usage dictionary to include
    
    Returns:
        Dictionary with all calculated metrics
    """
    metrics = {
        "overall": {},
        "by_question_type": {},
        "by_category": {}
    }
    
    # Separate results by question type
    closed_results = [r for r in results if r.get("question_type") == "closed"]
    open_results = [r for r in results if r.get("question_type") != "closed"]
    
    # ==========================================
    # EXACT MATCH (for closed questions) - Using semantic matching
    # ==========================================
    if closed_results:
        predictions = [r["model_response"] for r in closed_results]
        expected = [r["expected_answer"] for r in closed_results]
        # Get acceptable answers if available (for semantic matching)
        acceptable = [r.get("acceptable_answers", []) for r in closed_results]
        
        # Use semantic exact match for more fair evaluation
        exact_match_results = calculate_exact_match_batch(
            predictions, expected, acceptable, use_semantic=True
        )
        metrics["overall"]["exact_match"] = exact_match_results["accuracy"]
        metrics["by_question_type"]["closed"] = {
            "exact_match": exact_match_results["accuracy"],
            "count": len(closed_results)
        }
    
    # ==========================================
    # KEYWORD F1 (for all questions)
    # ==========================================
    predictions = [r["model_response"] for r in results]
    keywords = [r.get("expected_keywords", []) for r in results]
    keywords_primary = [r.get("expected_keywords_primary", None) for r in results]
    keywords_secondary = [r.get("expected_keywords_secondary", None) for r in results]
    
    keyword_results = calculate_keyword_f1_batch(
        predictions, 
        keywords,
        keywords_primary,
        keywords_secondary
    )
    metrics["overall"]["keyword_precision"] = keyword_results["avg_precision"]
    
    # Keyword Recall: Use signal recall (primary keywords only)
    # This measures the model's ability to identify the main navigation signal,
    # not exhaustive object listing. Secondary keywords are for qualitative analysis only.
    if "avg_recall_primary" in keyword_results:
        metrics["overall"]["keyword_recall"] = keyword_results["avg_recall_primary"]
        metrics["overall"]["keyword_recall_primary"] = keyword_results["avg_recall_primary"]
    else:
        # Fallback to traditional recall if no primary keywords defined
        metrics["overall"]["keyword_recall"] = keyword_results["avg_recall"]
    
    # F1 based on primary keywords (signal recall)
    if "avg_recall_primary" in keyword_results:
        # Recalculate F1 using signal recall
        signal_recall = keyword_results["avg_recall_primary"]
        precision = keyword_results["avg_precision"]
        if precision + signal_recall > 0:
            metrics["overall"]["keyword_f1"] = 2 * (precision * signal_recall) / (precision + signal_recall)
        else:
            metrics["overall"]["keyword_f1"] = 0.0
    else:
        metrics["overall"]["keyword_f1"] = keyword_results["avg_f1"]
    
    # Secondary keywords: for qualitative analysis only, not included in global metrics
    if "avg_recall_secondary" in keyword_results:
        metrics["overall"]["keyword_recall_secondary"] = keyword_results["avg_recall_secondary"]
    
    # ==========================================
    # BERTScore (for open questions with references)
    # ==========================================
    results_with_refs = [r for r in results if r.get("reference_answer")]
    
    if results_with_refs and calculate_bertscore_metric:
        predictions = [r["model_response"] for r in results_with_refs]
        references = [r["reference_answer"] for r in results_with_refs]
        
        bertscore_results = calculate_bertscore(predictions, references)
        metrics["overall"]["bertscore_f1"] = bertscore_results.get("bertscore_f1", 0.0)
        metrics["overall"]["bertscore_precision"] = bertscore_results.get("bertscore_precision", 0.0)
        metrics["overall"]["bertscore_recall"] = bertscore_results.get("bertscore_recall", 0.0)
    
    # ==========================================
    # METRICS BY CATEGORY
    # ==========================================
    categories = set(r.get("category", "unknown") for r in results)
    
    for category in categories:
        cat_results = [r for r in results if r.get("category") == category]
        
        if not cat_results:
            continue
        
        cat_predictions = [r["model_response"] for r in cat_results]
        cat_keywords = [r.get("expected_keywords", []) for r in cat_results]
        cat_keywords_primary = [r.get("expected_keywords_primary", None) for r in cat_results]
        cat_keywords_secondary = [r.get("expected_keywords_secondary", None) for r in cat_results]
        
        cat_keyword_results = calculate_keyword_f1_batch(
            cat_predictions, 
            cat_keywords,
            cat_keywords_primary,
            cat_keywords_secondary
        )
        
        # Use signal recall (primary) for category metrics
        if "avg_recall_primary" in cat_keyword_results:
            signal_recall = cat_keyword_results["avg_recall_primary"]
            precision = cat_keyword_results["avg_precision"]
            if precision + signal_recall > 0:
                keyword_f1 = 2 * (precision * signal_recall) / (precision + signal_recall)
            else:
                keyword_f1 = 0.0
            metrics["by_category"][category] = {
                "keyword_f1": keyword_f1,
                "keyword_recall": signal_recall,  # Signal recall (primary only)
                "keyword_recall_primary": signal_recall,
                "count": len(cat_results)
            }
        else:
            # Fallback if no primary keywords
            metrics["by_category"][category] = {
                "keyword_f1": cat_keyword_results["avg_f1"],
                "keyword_recall": cat_keyword_results["avg_recall"],
                "count": len(cat_results)
            }
        
        # Secondary recall: for qualitative analysis only
        if "avg_recall_secondary" in cat_keyword_results:
            metrics["by_category"][category]["keyword_recall_secondary"] = cat_keyword_results["avg_recall_secondary"]
        
        # Exact match for closed questions in this category (semantic)
        cat_closed = [r for r in cat_results if r.get("question_type") == "closed"]
        if cat_closed:
            cat_closed_preds = [r["model_response"] for r in cat_closed]
            cat_closed_expected = [r["expected_answer"] for r in cat_closed]
            cat_acceptable = [r.get("acceptable_answers", []) for r in cat_closed]
            cat_em_results = calculate_exact_match_batch(
                cat_closed_preds, cat_closed_expected, cat_acceptable, use_semantic=True
            )
            metrics["by_category"][category]["exact_match"] = cat_em_results["accuracy"]
    
    # ==========================================
    # INFERENCE TIME STATS
    # ==========================================
    inference_times = [r.get("inference_time", 0) for r in results if r.get("inference_time", 0) > 0]
    if inference_times:
        metrics["overall"]["avg_inference_time"] = float(np.mean(inference_times))
        metrics["overall"]["total_inference_time"] = float(sum(inference_times))
        metrics["overall"]["min_inference_time"] = float(min(inference_times))
        metrics["overall"]["max_inference_time"] = float(max(inference_times))
    
    # ==========================================
    # VRAM USAGE
    # ==========================================
    if vram_usage:
        metrics["overall"]["vram_allocated_gb"] = vram_usage.get("allocated_gb", 0.0)
        metrics["overall"]["vram_max_allocated_gb"] = vram_usage.get("max_allocated_gb", 0.0)
    
    return metrics


def print_metrics_summary(metrics: Dict) -> None:
    """Print a formatted summary of metrics."""
    print("\n" + "=" * 60)
    print("EVALUATION METRICS SUMMARY")
    print("=" * 60)
    
    print("\n📊 OVERALL METRICS:")
    print("-" * 40)
    overall = metrics.get("overall", {})
    
    if "exact_match" in overall:
        print(f"  Exact Match (closed questions): {overall['exact_match']:.4f}")
    
    print(f"  Keyword F1:                     {overall.get('keyword_f1', 0):.4f}")
    print(f"  Signal Recall (Primary):         {overall.get('keyword_recall', 0):.4f}  # Measures main navigation signal detection")
    print(f"  Keyword Precision:              {overall.get('keyword_precision', 0):.4f}")
    
    if "keyword_recall_secondary" in overall:
        print(f"  Recall Secondary (qualitative):   {overall.get('keyword_recall_secondary', 0):.4f}  # For analysis only, not in ranking")
    
    if "bertscore_f1" in overall:
        print(f"  BERTScore F1:                   {overall['bertscore_f1']:.4f}")
    
    if "avg_inference_time" in overall:
        print(f"\n⏱️  Avg Inference Time:            {overall['avg_inference_time']:.2f}s")
        print(f"  Total Inference Time:           {overall['total_inference_time']:.2f}s")
    
    if "vram_max_allocated_gb" in overall:
        print(f"\n💾 VRAM Max Allocated:            {overall['vram_max_allocated_gb']:.2f} GB")
    
    print("\n📁 METRICS BY CATEGORY:")
    print("-" * 40)
    by_category = metrics.get("by_category", {})
    for category, cat_metrics in sorted(by_category.items()):
        print(f"\n  {category}:")
        print(f"    Count: {cat_metrics.get('count', 0)}")
        print(f"    Keyword F1: {cat_metrics.get('keyword_f1', 0):.4f}")
        if "exact_match" in cat_metrics:
            print(f"    Exact Match: {cat_metrics['exact_match']:.4f}")
    
    print("\n" + "=" * 60)


def metrics_to_dataframe(metrics: Dict) -> "pd.DataFrame":
    """
    Convert metrics to a pandas DataFrame for easy export.
    
    Args:
        metrics: Metrics dictionary
    
    Returns:
        pandas DataFrame
    """
    try:
        import pandas as pd
    except ImportError:
        print("Warning: pandas not installed")
        return None
    
    rows = []
    
    # Overall metrics
    overall = metrics.get("overall", {})
    for metric_name, value in overall.items():
        rows.append({
            "category": "overall",
            "metric": metric_name,
            "value": value
        })
    
    # By category metrics
    by_category = metrics.get("by_category", {})
    for category, cat_metrics in by_category.items():
        for metric_name, value in cat_metrics.items():
            rows.append({
                "category": category,
                "metric": metric_name,
                "value": value
            })
    
    return pd.DataFrame(rows)
