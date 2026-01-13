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
    expected_keywords_primary: Optional[List[str]] = None  # Primary (essential) keywords
    expected_keywords_secondary: Optional[List[str]] = None  # Secondary (detail) keywords


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
    # Prepare question with <image> token at the beginning (required by PaliGemma)
    formatted_question = f"<image>{question}" if not question.startswith("<image>") else question
    
    # Prepare inputs with improved processing (based on working example)
    inputs = processor(
        text=formatted_question,
        images=image,
        padding="longest",
        do_convert_rgb=True,
        return_tensors="pt"
    ).to(model.device)
    
    # Ensure inputs match model dtype (important for numerical precision)
    inputs = inputs.to(dtype=model.dtype)
    
    # Measure inference time
    start_time = time.time()
    
    with torch.no_grad():
        # Use max_new_tokens for simpler, more direct control
        # This is more reliable than max_length calculation
        generation_kwargs = {
            "max_new_tokens": max_new_tokens,
            "do_sample": False,  # Deterministic output (greedy decoding)
            "num_beams": 1,  # Greedy search (faster, more deterministic)
            # Note: repetition_penalty doesn't work well with do_sample=False
            # It can cause premature stopping, so we remove it
            "pad_token_id": processor.tokenizer.pad_token_id or processor.tokenizer.eos_token_id,
            "eos_token_id": processor.tokenizer.eos_token_id,
        }
        
        outputs = model.generate(
            **inputs,
            **generation_kwargs
        )
    
    inference_time = time.time() - start_time
    
    # Decode output
    # PaliGemma returns the full sequence including the input
    # We need to extract only the newly generated tokens
    
    # Get the length of input tokens
    input_len = inputs["input_ids"].shape[-1]
    
    # Extract only the generated tokens (after input)
    generated_ids = outputs[0][input_len:]
    
    # Decode only the generated part
    # Use skip_special_tokens=True to remove special tokens like <pad>, <eos>
    generated_text = processor.decode(generated_ids, skip_special_tokens=True)
    
    # Clean up the text: remove any remaining prompt artifacts
    generated_text = generated_text.strip()
    
    # Remove the question text if it somehow appears in the output
    # (this can happen if the model repeats the input)
    if question.lower() in generated_text.lower():
        # Try to remove the question from the beginning
        question_lower = question.lower().strip()
        generated_lower = generated_text.lower()
        if generated_lower.startswith(question_lower):
            generated_text = generated_text[len(question):].strip()
    
    # Handle edge case: if generated text is empty or just whitespace/punctuation
    # This can happen if the model generates only special tokens
    if not generated_text or generated_text in ["None", "none", ".", ",", "?", "!"]:
        # Try decoding without skip_special_tokens to see what was actually generated
        generated_text_fallback = processor.decode(generated_ids, skip_special_tokens=False)
        # Remove special tokens manually
        generated_text_fallback = generated_text_fallback.replace("<pad>", "").replace("<eos>", "").strip()
        if generated_text_fallback and generated_text_fallback != generated_text:
            generated_text = generated_text_fallback
    
    return generated_text, inference_time


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
        max_new_tokens: Maximum tokens to generate (base value, adjusted by question type)
    
    Returns:
        InferenceResult object
    """
    # Adjust max_new_tokens based on question type
    # Captions need longer responses
    if eval_item.question.question_type == "caption":
        adjusted_max_tokens = max(max_new_tokens, 300)  # At least 300 for captions
    elif eval_item.question.question_type == "element_list":
        adjusted_max_tokens = max(max_new_tokens, 50)  # At least 50 for element lists
    else:
        adjusted_max_tokens = max_new_tokens  # Use provided value for closed questions
    
    # Load image
    image = load_image_if_needed(eval_item.image_sample)
    
    # Run inference
    response, inference_time = run_single_inference(
        model=model,
        processor=processor,
        image=image,
        question=eval_item.question.question_text,
        max_new_tokens=adjusted_max_tokens
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
        acceptable_answers=eval_item.question.acceptable_answers or [],
        expected_keywords_primary=eval_item.question.expected_keywords_primary,
        expected_keywords_secondary=eval_item.question.expected_keywords_secondary
    )
    
    return result


def run_inference_on_dataset(
    model,
    processor,
    eval_items: List[EvaluationItem],
    max_new_tokens: int = 100,
    show_progress: bool = True,
    verbose: bool = False
) -> List[InferenceResult]:
    """
    Run inference on all evaluation items.
    
    Args:
        model: The PaliGemma model
        processor: The model processor
        eval_items: List of EvaluationItem objects
        max_new_tokens: Maximum tokens to generate
        show_progress: Whether to show progress bar
        verbose: Whether to print question, model response, and expected answer for each item
    
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
            
            # Print details if verbose mode is enabled
            if verbose:
                print(f"\n{'='*80}")
                print(f"📷 Image: {result.image_id}")
                print(f"📁 Category: {result.category}")
                print(f"❓ Question: {result.question_text}")
                print(f"🤖 Model Response: {result.model_response}")
                
                # Show expected answer based on question type
                if result.question_type == "closed":
                    if result.expected_answer:
                        print(f"✅ Expected Answer: {result.expected_answer}")
                    else:
                        print(f"⚠️  Expected Answer: (not specified)")
                elif result.question_type == "element_list":
                    if result.expected_keywords_primary:
                        print(f"✅ Expected Keywords (primary): {result.expected_keywords_primary}")
                    elif result.expected_keywords:
                        print(f"✅ Expected Keywords: {result.expected_keywords}")
                    else:
                        print(f"⚠️  Expected Keywords: (not specified)")
                elif result.question_type == "caption":
                    # For caption questions, show both model response and reference clearly
                    print(f"\n📝 CAPTION QUESTION:")
                    print(f"   Model Response: {result.model_response}")
                    if result.reference_answer:
                        print(f"   Reference Answer: {result.reference_answer}")
                    else:
                        print(f"   ⚠️  Reference Answer: (not specified)")
                
                print(f"⏱️  Inference Time: {result.inference_time:.2f}s")
                print(f"{'='*80}")
            
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
                metrics_to_calculate=[],
                expected_keywords_primary=eval_item.question.expected_keywords_primary,
                expected_keywords_secondary=eval_item.question.expected_keywords_secondary
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
    Only includes relevant fields based on question type.
    
    Args:
        results: List of InferenceResult objects
    
    Returns:
        List of dictionaries with only relevant fields
    """
    output = []
    for r in results:
        result_dict = {
            "image_id": r.image_id,
            "question_id": r.question_id,
            "question_text": r.question_text,
            "question_type": r.question_type,
            "model_response": r.model_response,
            "inference_time": r.inference_time,
            "category": r.category,
            "dataset_source": r.dataset_source,
            "metrics_to_calculate": r.metrics_to_calculate
        }
        
        # Add fields based on question type
        if r.question_type == "closed":
            # For closed questions: expected_answer and acceptable_answers
            if r.expected_answer is not None:
                result_dict["expected_answer"] = r.expected_answer
            if r.acceptable_answers:
                result_dict["acceptable_answers"] = r.acceptable_answers
        elif r.question_type == "element_list":
            # For element_list questions: expected_keywords and expected_keywords_primary
            if r.expected_keywords:
                result_dict["expected_keywords"] = r.expected_keywords
            if r.expected_keywords_primary:
                result_dict["expected_keywords_primary"] = r.expected_keywords_primary
        elif r.question_type == "caption":
            # For caption questions: reference_answer for BERTScore
            if r.reference_answer is not None:
                result_dict["reference_answer"] = r.reference_answer
        
        output.append(result_dict)
    
    return output
