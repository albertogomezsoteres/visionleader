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


def extract_first_token(text: str) -> str:
    """
    Extract the first significant token from text.
    Useful for short answers like "yes", "no", "open", "closed", "up", "down".
    
    Args:
        text: Input text
    
    Returns:
        First token (word) from normalized text, or empty string if no tokens
    """
    normalized = normalize_text(text)
    tokens = normalized.split()
    return tokens[0] if tokens else ""


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
    For short answers (yes/no/open/closed/up/down), extracts the first token.
    For longer responses, checks if expected answer is contained.
    
    Args:
        prediction: Model prediction
        expected: Expected answer (e.g., "yes", "no", "open", "closed")
        acceptable_answers: List of acceptable alternative answers
    
    Returns:
        1.0 if match (exact or semantic), 0.0 otherwise
    """
    pred_normalized = normalize_text(prediction)
    expected_normalized = normalize_text(expected)
    
    # For short expected answers (1-2 words), extract first token from prediction
    # This handles cases like "no ." or "yes." or "open" vs "open."
    expected_tokens = expected_normalized.split()
    if len(expected_tokens) <= 2:
        # Short answer - extract first token from prediction
        pred_first_token = extract_first_token(prediction)
        if pred_first_token == expected_normalized:
            return 1.0
    
    # First, try strict exact match (expected contained in prediction)
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
    elif expected_normalized in ["open", "closed", "up", "down"]:
        # For open/closed/up/down, check if first token matches
        pred_first_token = extract_first_token(prediction)
        if pred_first_token == expected_normalized:
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
            "recall_primary": 0.0,
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
        "matched_keywords": matched,
        "matched_primary": matched_primary,
        "expected_keywords": expected_keywords,
        "num_matched": true_positives,
        "num_expected": len(expected_keywords),
        "num_matched_primary": len(matched_primary),
        "num_expected_primary": len(expected_keywords_primary) if expected_keywords_primary else 0
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
        Dictionary with average metrics including recall_primary
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
    
    # Calculate averages, including recall_primary if available
    avg_recall_primary = None
    
    # Only calculate if at least one item has primary keywords
    primary_metrics = [m["recall_primary"] for m in all_metrics if m.get("num_expected_primary", 0) > 0]
    if primary_metrics:
        avg_recall_primary = np.mean(primary_metrics)
    
    result = {
        "avg_precision": np.mean([m["precision"] for m in all_metrics]),
        "avg_recall": np.mean([m["recall"] for m in all_metrics]),
        "avg_f1": np.mean([m["f1"] for m in all_metrics]),
        "individual_metrics": all_metrics
    }
    
    if avg_recall_primary is not None:
        result["avg_recall_primary"] = avg_recall_primary
    
    return result


# ============================================================
# OUTPUT LENGTH / VERBOSITY
# ============================================================

def calculate_output_length(text: str) -> int:
    """
    Calculate the number of words in a text.
    
    Args:
        text: Input text
    
    Returns:
        Number of words (tokens)
    """
    if not text:
        return 0
    normalized = normalize_text(text)
    words = normalized.split()
    return len(words)


def calculate_output_length_batch(
    texts: List[str]
) -> Dict[str, float]:
    """
    Calculate output length statistics for a batch of texts.
    
    Args:
        texts: List of texts (model responses)
    
    Returns:
        Dictionary with avg_output_length, max_output_length, and individual_lengths
    """
    if not texts:
        return {
            "avg_output_length": 0.0,
            "max_output_length": 0.0,
            "individual_lengths": []
        }
    
    lengths = [calculate_output_length(text) for text in texts]
    
    return {
        "avg_output_length": float(np.mean(lengths)),
        "max_output_length": float(max(lengths)) if lengths else 0.0,
        "individual_lengths": lengths
    }


# ============================================================
# BERTSCORE
# ============================================================

def calculate_bertscore(
    prediction: str,
    reference: str,
    lang: str = "en"
) -> Dict[str, float]:
    """
    Calculate BERTScore for a single prediction-reference pair.
    
    BERTScore evaluates the semantic similarity between prediction and reference
    using contextualized embeddings.
    
    Args:
        prediction: Model prediction text
        reference: Reference text
        lang: Language code (default: "en")
    
    Returns:
        Dictionary with precision, recall, and F1 scores
    """
    try:
        from bert_score import score
    except ImportError:
        print("Warning: bert_score not installed. Install with: pip install bert-score")
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0
        }
    
    if not prediction or not reference:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0
        }
    
    try:
        # BERTScore returns tensors, convert to Python floats
        # rescale_with_baseline=True normalizes scores using a baseline, making them more sensitive to semantic differences
        P, R, F1 = score([prediction], [reference], lang=lang, verbose=False, rescale_with_baseline=True)
        return {
            "precision": float(P.item()),
            "recall": float(R.item()),
            "f1": float(F1.item())
        }
    except Exception as e:
        print(f"Warning: BERTScore calculation failed: {e}")
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0
        }


def calculate_bertscore_batch(
    predictions: List[str],
    references: List[str],
    lang: str = "en"
) -> Dict[str, float]:
    """
    Calculate BERTScore for a batch of predictions and references.
    
    Args:
        predictions: List of model predictions
        references: List of reference texts
        lang: Language code (default: "en")
    
    Returns:
        Dictionary with average precision, recall, F1, and individual scores
    """
    try:
        from bert_score import score
    except ImportError:
        print("Warning: bert_score not installed. Install with: pip install bert-score")
        return {
            "avg_precision": 0.0,
            "avg_recall": 0.0,
            "avg_f1": 0.0,
            "individual_scores": []
        }
    
    if not predictions or not references:
        return {
            "avg_precision": 0.0,
            "avg_recall": 0.0,
            "avg_f1": 0.0,
            "individual_scores": []
        }
    
    if len(predictions) != len(references):
        print(f"Warning: Mismatch in batch sizes: {len(predictions)} predictions vs {len(references)} references")
        return {
            "avg_precision": 0.0,
            "avg_recall": 0.0,
            "avg_f1": 0.0,
            "individual_scores": []
        }
    
    try:
        # Filter out empty pairs
        valid_pairs = [(p, r) for p, r in zip(predictions, references) if p and r]
        if not valid_pairs:
            return {
                "avg_precision": 0.0,
                "avg_recall": 0.0,
                "avg_f1": 0.0,
                "individual_scores": []
            }
        
        valid_preds, valid_refs = zip(*valid_pairs)
        
        # Calculate BERTScore for all valid pairs at once (more efficient)
        # rescale_with_baseline=True normalizes scores using a baseline, making them more sensitive to semantic differences
        P, R, F1 = score(list(valid_preds), list(valid_refs), lang=lang, verbose=False, rescale_with_baseline=True)
        
        # Convert tensors to Python floats
        precisions = [float(p.item()) for p in P]
        recalls = [float(r.item()) for r in R]
        f1s = [float(f.item()) for f in F1]
        
        # Create individual scores dict
        individual_scores = [
            {"precision": p, "recall": r, "f1": f}
            for p, r, f in zip(precisions, recalls, f1s)
        ]
        
        return {
            "avg_precision": float(np.mean(precisions)),
            "avg_recall": float(np.mean(recalls)),
            "avg_f1": float(np.mean(f1s)),
            "individual_scores": individual_scores
        }
    except Exception as e:
        print(f"Warning: BERTScore batch calculation failed: {e}")
        return {
            "avg_precision": 0.0,
            "avg_recall": 0.0,
            "avg_f1": 0.0,
            "individual_scores": []
        }


# ============================================================
# MAIN METRICS CALCULATOR
# ============================================================

def calculate_all_metrics(
    results: List[Dict],
    vram_usage: Optional[Dict] = None
) -> Dict[str, Dict]:
    """
    Calculate all metrics for a set of inference results.
    
    Only calculates Exact Match (for closed questions) and Keyword Recall (for element questions).
    
    Args:
        results: List of inference result dictionaries
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
    caption_results = [r for r in results if r.get("question_type") == "caption"]
    open_results = [r for r in results if r.get("question_type") != "closed" and r.get("question_type") != "caption"]
    
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
    # BERTSCORE (for caption questions)
    # ==========================================
    if caption_results:
        caption_predictions = [r["model_response"] for r in caption_results]
        caption_references = [r.get("reference_answer", "") for r in caption_results]
        
        # Filter out pairs where reference is missing
        valid_caption_pairs = [
            (pred, ref) for pred, ref in zip(caption_predictions, caption_references)
            if ref  # Only include if reference_answer exists
        ]
        
        if valid_caption_pairs:
            valid_preds, valid_refs = zip(*valid_caption_pairs)
            bertscore_results = calculate_bertscore_batch(list(valid_preds), list(valid_refs))
            
            # BERTScore: Recall is the primary metric, F1 is secondary
            metrics["overall"]["bertscore_recall"] = bertscore_results["avg_recall"]  # Primary metric
            metrics["overall"]["bertscore_f1"] = bertscore_results["avg_f1"]  # Secondary metric
            metrics["overall"]["bertscore_precision"] = bertscore_results["avg_precision"]  # Lower priority
            
            metrics["by_question_type"]["caption"] = {
                "bertscore_recall": bertscore_results["avg_recall"],  # Primary metric
                "bertscore_f1": bertscore_results["avg_f1"],  # Secondary metric
                "bertscore_precision": bertscore_results["avg_precision"],  # Lower priority
                "count": len(caption_results),
                "valid_count": len(valid_caption_pairs)
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
    # This measures the model's ability to identify the main navigation signal.
    if "avg_recall_primary" in keyword_results:
        metrics["overall"]["keyword_recall"] = keyword_results["avg_recall_primary"]
    else:
        # Fallback to traditional recall if no primary keywords defined
        metrics["overall"]["keyword_recall"] = keyword_results["avg_recall"]
    
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
            metrics["by_category"][category] = {
                "keyword_recall": signal_recall,
                "count": len(cat_results)
            }
        else:
            # Fallback if no primary keywords
            metrics["by_category"][category] = {
                "keyword_recall": cat_keyword_results["avg_recall"],
                "count": len(cat_results)
            }
        
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
        
        # BERTScore for caption questions in this category
        cat_caption = [r for r in cat_results if r.get("question_type") == "caption"]
        if cat_caption:
            cat_caption_preds = [r["model_response"] for r in cat_caption]
            cat_caption_refs = [r.get("reference_answer", "") for r in cat_caption]
            
            # Filter out pairs where reference is missing
            valid_cat_caption_pairs = [
                (pred, ref) for pred, ref in zip(cat_caption_preds, cat_caption_refs)
                if ref
            ]
            
            if valid_cat_caption_pairs:
                valid_preds, valid_refs = zip(*valid_cat_caption_pairs)
                cat_bertscore_results = calculate_bertscore_batch(list(valid_preds), list(valid_refs))
                
                if category not in metrics["by_category"]:
                    metrics["by_category"][category] = {}
                # BERTScore: Recall is primary, F1 is secondary
                metrics["by_category"][category]["bertscore_recall"] = cat_bertscore_results["avg_recall"]  # Primary
                metrics["by_category"][category]["bertscore_f1"] = cat_bertscore_results["avg_f1"]  # Secondary
                metrics["by_category"][category]["bertscore_precision"] = cat_bertscore_results["avg_precision"]
    
    # ==========================================
    # OUTPUT LENGTH / VERBOSITY (for element_list and caption)
    # ==========================================
    verbosity_results = [r for r in results if r.get("question_type") in ["element_list", "caption"]]
    if verbosity_results:
        verbosity_texts = [r["model_response"] for r in verbosity_results]
        verbosity_stats = calculate_output_length_batch(verbosity_texts)
        
        metrics["overall"]["avg_output_length"] = verbosity_stats["avg_output_length"]
        metrics["overall"]["max_output_length"] = verbosity_stats["max_output_length"]
        
        # By question type
        element_list_results = [r for r in verbosity_results if r.get("question_type") == "element_list"]
        caption_results_verb = [r for r in verbosity_results if r.get("question_type") == "caption"]
        
        if element_list_results:
            element_list_texts = [r["model_response"] for r in element_list_results]
            element_list_stats = calculate_output_length_batch(element_list_texts)
            if "element_list" not in metrics["by_question_type"]:
                metrics["by_question_type"]["element_list"] = {}
            metrics["by_question_type"]["element_list"]["avg_output_length"] = element_list_stats["avg_output_length"]
            metrics["by_question_type"]["element_list"]["max_output_length"] = element_list_stats["max_output_length"]
        
        if caption_results_verb:
            caption_texts = [r["model_response"] for r in caption_results_verb]
            caption_stats = calculate_output_length_batch(caption_texts)
            if "caption" not in metrics["by_question_type"]:
                metrics["by_question_type"]["caption"] = {}
            metrics["by_question_type"]["caption"]["avg_output_length"] = caption_stats["avg_output_length"]
            metrics["by_question_type"]["caption"]["max_output_length"] = caption_stats["max_output_length"]
    
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
    
    print(f"  Keyword Recall:                 {overall.get('keyword_recall', 0):.4f}  # Measures main navigation signal detection")
    
    if "bertscore_recall" in overall:
        print(f"  BERTScore Recall:               {overall.get('bertscore_recall', 0):.4f}  # Primary metric (semantic similarity for captions)")
        print(f"  BERTScore F1:                   {overall.get('bertscore_f1', 0):.4f}  # Secondary metric")
        print(f"  BERTScore Precision:           {overall.get('bertscore_precision', 0):.4f}")
    
    if "avg_output_length" in overall:
        print(f"\n📏 OUTPUT LENGTH (Verbosity):")
        print(f"  Avg Output Length:              {overall.get('avg_output_length', 0):.1f} words")
        print(f"  Max Output Length:              {overall.get('max_output_length', 0):.1f} words")
    
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
        print(f"    Keyword Recall: {cat_metrics.get('keyword_recall', 0):.4f}")
        if "exact_match" in cat_metrics:
            print(f"    Exact Match: {cat_metrics['exact_match']:.4f}")
        if "bertscore_recall" in cat_metrics:
            print(f"    BERTScore Recall: {cat_metrics.get('bertscore_recall', 0):.4f}  # Primary")
            print(f"    BERTScore F1: {cat_metrics.get('bertscore_f1', 0):.4f}  # Secondary")
            print(f"    BERTScore Precision: {cat_metrics.get('bertscore_precision', 0):.4f}")
        if "avg_output_length" in cat_metrics:
            print(f"    Avg Output Length: {cat_metrics.get('avg_output_length', 0):.1f} words")
    
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
