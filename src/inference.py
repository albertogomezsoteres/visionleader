"""
Inference module for PaliGemma models.

This module provides functions to run inference on images
using PaliGemma models.
"""

import time
import torch
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from PIL import Image
from tqdm import tqdm

from .dataset_loader import ImageSample, Question, EvaluationItem


@dataclass
class InferenceResult:
    """Represents the result of a single inference."""
    image_id: str
    question_id: str
    question_text: str
    question_type: str
    model_response: str
    expected_answer: Optional[str]
    expected_keywords: List[str]
    reference_answer: Optional[str]
    inference_time: float  # in seconds
    category: str
    dataset_source: str
    metrics_to_calculate: List[str] = field(default_factory=list)
    acceptable_answers: List[str] = field(default_factory=list)  # For semantic matching


def run_single_inference(
    model,
    processor,
    image: Image.Image,
    question: str,
    max_new_tokens: int = 100,
    device: str = "cuda"
) -> Tuple[str, float]:
    """
    Run inference on a single image with a question.
    
    Args:
        model: The PaliGemma model
        processor: The model processor
        image: PIL Image
        question: Question text
        max_new_tokens: Maximum number of tokens to generate
        device: Device to run on
    
    Returns:
        Tuple of (generated_text, inference_time_seconds)
    """
    # Prepare inputs
    inputs = processor(
        text=question,
        images=image,
        return_tensors="pt"
    )
    
    # Move to device
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    
    # Measure inference time
    start_time = time.time()
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False  # Deterministic output
        )
    
    inference_time = time.time() - start_time
    
    # Decode output
    # PaliGemma returns the full sequence including the input
    # We need to extract only the generated part
    input_len = inputs["input_ids"].shape[-1]
    generated_ids = outputs[0][input_len:]
    generated_text = processor.decode(generated_ids, skip_special_tokens=True)
    
    return generated_text.strip(), inference_time


def load_image_if_needed(sample: ImageSample) -> Image.Image:
    """
    Load image if not already loaded.
    
    Args:
        sample: ImageSample object
    
    Returns:
        PIL Image
    """
    if sample.image is not None:
        return sample.image
    return Image.open(sample.image_path).convert("RGB")


def run_inference_on_item(
    model,
    processor,
    eval_item: EvaluationItem,
    max_new_tokens: int = 100
) -> InferenceResult:
    """
    Run inference on a single evaluation item.
    
    Args:
        model: The PaliGemma model
        processor: The model processor
        eval_item: EvaluationItem containing image and question
        max_new_tokens: Maximum tokens to generate
    
    Returns:
        InferenceResult object
    """
    # Load image
    image = load_image_if_needed(eval_item.image_sample)
    
    # Run inference
    response, inference_time = run_single_inference(
        model=model,
        processor=processor,
        image=image,
        question=eval_item.question.question_text,
        max_new_tokens=max_new_tokens
    )
    
    # Create result
    result = InferenceResult(
        image_id=eval_item.image_sample.image_id,
        question_id=eval_item.question.question_id,
        question_text=eval_item.question.question_text,
        question_type=eval_item.question.question_type,
        model_response=response,
        expected_answer=eval_item.question.expected_answer,
        expected_keywords=eval_item.question.expected_keywords,
        reference_answer=eval_item.question.reference_answer,
        inference_time=inference_time,
        category=eval_item.image_sample.category,
        dataset_source=eval_item.image_sample.dataset_source,
        metrics_to_calculate=eval_item.question.metrics,
        acceptable_answers=eval_item.question.acceptable_answers or []
    )
    
    return result


def run_inference_on_dataset(
    model,
    processor,
    eval_items: List[EvaluationItem],
    max_new_tokens: int = 100,
    show_progress: bool = True
) -> List[InferenceResult]:
    """
    Run inference on all evaluation items.
    
    Args:
        model: The PaliGemma model
        processor: The model processor
        eval_items: List of EvaluationItem objects
        max_new_tokens: Maximum tokens to generate
        show_progress: Whether to show progress bar
    
    Returns:
        List of InferenceResult objects
    """
    results = []
    
    iterator = tqdm(eval_items, desc="Running inference") if show_progress else eval_items
    
    for eval_item in iterator:
        try:
            result = run_inference_on_item(
                model=model,
                processor=processor,
                eval_item=eval_item,
                max_new_tokens=max_new_tokens
            )
            results.append(result)
            
            if show_progress:
                iterator.set_postfix({
                    "img": result.image_id[:20],
                    "time": f"{result.inference_time:.2f}s"
                })
                
        except Exception as e:
            print(f"Error processing {eval_item.image_sample.image_id}: {e}")
            # Create an error result
            error_result = InferenceResult(
                image_id=eval_item.image_sample.image_id,
                question_id=eval_item.question.question_id,
                question_text=eval_item.question.question_text,
                question_type=eval_item.question.question_type,
                model_response=f"ERROR: {str(e)}",
                expected_answer=eval_item.question.expected_answer,
                expected_keywords=eval_item.question.expected_keywords,
                reference_answer=eval_item.question.reference_answer,
                inference_time=0.0,
                category=eval_item.image_sample.category,
                dataset_source=eval_item.image_sample.dataset_source,
                metrics_to_calculate=[]
            )
            results.append(error_result)
    
    return results


def get_inference_statistics(results: List[InferenceResult]) -> Dict:
    """
    Calculate statistics about inference results.
    
    Args:
        results: List of InferenceResult objects
    
    Returns:
        Dictionary with statistics
    """
    valid_times = [r.inference_time for r in results if r.inference_time > 0]
    
    stats = {
        "total_inferences": len(results),
        "successful_inferences": len(valid_times),
        "failed_inferences": len(results) - len(valid_times),
        "total_time": sum(valid_times),
        "avg_time_per_inference": sum(valid_times) / len(valid_times) if valid_times else 0,
        "min_time": min(valid_times) if valid_times else 0,
        "max_time": max(valid_times) if valid_times else 0,
        "by_category": {},
        "by_question_type": {}
    }
    
    # Stats by category
    for result in results:
        if result.category not in stats["by_category"]:
            stats["by_category"][result.category] = {"count": 0, "total_time": 0}
        stats["by_category"][result.category]["count"] += 1
        stats["by_category"][result.category]["total_time"] += result.inference_time
    
    # Stats by question type
    for result in results:
        if result.question_type not in stats["by_question_type"]:
            stats["by_question_type"][result.question_type] = {"count": 0}
        stats["by_question_type"][result.question_type]["count"] += 1
    
    return stats


def print_inference_summary(results: List[InferenceResult]) -> None:
    """Print a summary of inference results."""
    stats = get_inference_statistics(results)
    
    print("\n" + "=" * 50)
    print("INFERENCE SUMMARY")
    print("=" * 50)
    print(f"Total inferences: {stats['total_inferences']}")
    print(f"Successful: {stats['successful_inferences']}")
    print(f"Failed: {stats['failed_inferences']}")
    print(f"Total time: {stats['total_time']:.2f}s")
    print(f"Average time per inference: {stats['avg_time_per_inference']:.2f}s")
    print(f"Min time: {stats['min_time']:.2f}s")
    print(f"Max time: {stats['max_time']:.2f}s")
    
    print("\nBy Category:")
    for category, data in sorted(stats["by_category"].items()):
        avg_time = data["total_time"] / data["count"] if data["count"] > 0 else 0
        print(f"  {category}: {data['count']} items, {avg_time:.2f}s avg")
    
    print("\nBy Question Type:")
    for qtype, data in sorted(stats["by_question_type"].items()):
        print(f"  {qtype}: {data['count']} items")
    print("=" * 50 + "\n")


def results_to_dict(results: List[InferenceResult]) -> List[Dict]:
    """
    Convert inference results to a list of dictionaries for export.
    
    Args:
        results: List of InferenceResult objects
    
    Returns:
        List of dictionaries
    """
    return [
        {
            "image_id": r.image_id,
            "question_id": r.question_id,
            "question_text": r.question_text,
            "question_type": r.question_type,
            "model_response": r.model_response,
            "expected_answer": r.expected_answer,
            "expected_keywords": r.expected_keywords,
            "reference_answer": r.reference_answer,
            "inference_time": r.inference_time,
            "category": r.category,
            "dataset_source": r.dataset_source,
            "metrics_to_calculate": r.metrics_to_calculate,
            "acceptable_answers": r.acceptable_answers
        }
        for r in results
    ]
