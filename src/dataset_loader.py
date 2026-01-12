"""
Dataset Loader for image evaluation.

This module provides functions to load images and questions
for evaluating PaliGemma models on navigation assistance tasks.
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from PIL import Image


@dataclass
class ImageSample:
    """Represents a single image sample with its metadata."""
    image_id: str
    image_path: str
    category: str
    dataset_source: str
    image: Optional[Image.Image] = None


@dataclass
class Question:
    """Represents a question for evaluation."""
    question_id: str
    question_type: str  # "closed", "element_list", "ocr"
    question_text: str
    expected_answer: Optional[str]
    expected_keywords: List[str]
    reference_answer: Optional[str]
    metrics: List[str]
    acceptable_answers: Optional[List[str]] = None  # For semantic matching
    expected_keywords_primary: Optional[List[str]] = None  # Primary (essential) keywords
    expected_keywords_secondary: Optional[List[str]] = None  # Secondary (detail) keywords


@dataclass
class EvaluationItem:
    """Represents a complete evaluation item (image + question pair)."""
    image_sample: ImageSample
    question: Question


def load_questions_config(config_path: str) -> Dict:
    """
    Load questions configuration from JSON file.
    
    Args:
        config_path: Path to questions.json
    
    Returns:
        Dictionary with questions configuration
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_models_config(config_path: str) -> Dict:
    """
    Load models configuration from JSON file.
    
    Args:
        config_path: Path to models.json
    
    Returns:
        Dictionary with models configuration
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_per_image_answers(config_path: str) -> Dict[str, Dict[str, str]]:
    """
    Load expected answers per image from JSON file.
    
    The JSON file should have the structure:
    {
        "image_filename.jpg": {
            "question_id": "expected_answer",
            ...
        },
        ...
    }
    
    Args:
        config_path: Path to the per-image answers JSON file
    
    Returns:
        Dictionary mapping image filenames to question_id -> expected_answer mappings
        Returns empty dict if file doesn't exist
    """
    if not os.path.exists(config_path):
        return {}
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Filter out comment/instruction keys
            return {k: v for k, v in data.items() if not k.startswith('_')}
    except Exception as e:
        print(f"Warning: Could not load per-image answers from {config_path}: {e}")
        return {}


def get_category_from_folder(folder_name: str, folder_mapping: Dict) -> str:
    """
    Get the category name from folder name using mapping.
    
    Args:
        folder_name: Name of the folder
        folder_mapping: Dictionary mapping folder names to categories
    
    Returns:
        Category name
    """
    folder_lower = folder_name.lower()
    
    # First try exact match in mapping
    if folder_lower in folder_mapping:
        return folder_mapping[folder_lower]
    if folder_name in folder_mapping:
        return folder_mapping[folder_name]
    
    # Try replacing spaces/underscores
    folder_clean = folder_lower.replace("_", " ")
    if folder_clean in folder_mapping:
        return folder_mapping[folder_clean]
    
    # Return original if no mapping found
    return folder_name


def extract_category_from_filename(filename: str) -> str:
    """
    Extract category from filename for datasets like VizWiz 
    where images are directly in the folder.
    
    Args:
        filename: Image filename (e.g., "VizWiz_staircase_01.jpg")
    
    Returns:
        Detected category
    """
    filename_lower = filename.lower()
    
    # Priority order for detection
    if "staircase" in filename_lower or "stairs" in filename_lower:
        return "staircase"
    elif "elevator" in filename_lower or "lift" in filename_lower:
        return "elevator"
    elif "corridor" in filename_lower or "hallway" in filename_lower:
        return "corridor"
    elif "bathroomsign" in filename_lower:
        return "sign"
    elif "doorsign" in filename_lower:
        return "door_sign"
    elif "bathroom" in filename_lower or "restroom" in filename_lower:
        return "door_sign"
    elif "door" in filename_lower:
        return "door"
    elif "sign" in filename_lower:
        return "sign"
    elif "obstacle" in filename_lower:
        return "obstacle"
    elif "crossing" in filename_lower or "zebra" in filename_lower:
        return "zebra_crossing"
    else:
        return "door"  # Default fallback


def get_dataset_source(path: str) -> str:
    """
    Determine the dataset source from the image path.
    
    Args:
        path: Full path to the image
    
    Returns:
        Dataset source name
    """
    path_lower = path.lower()
    if "mit indoor" in path_lower or "mit_indoor" in path_lower:
        return "MIT Indoor Scenes"
    elif "places" in path_lower:
        return "Places-2 MIT"
    elif "vizwiz" in path_lower:
        return "VizWiz"
    elif "ufv" in path_lower:
        return "UFV Campus"
    else:
        return "Unknown"


def discover_images(data_path: str, valid_extensions: Tuple[str, ...] = ('.jpg', '.jpeg', '.png', '.gif', '.webp')) -> List[Dict]:
    """
    Recursively discover all images in the data directory.
    
    Args:
        data_path: Root path to data directory
        valid_extensions: Tuple of valid image extensions
    
    Returns:
        List of dictionaries with image information
    """
    images = []
    data_path = Path(data_path)
    
    if not data_path.exists():
        raise FileNotFoundError(f"Data path does not exist: {data_path}")
    
    # Datasets where images are directly in the folder (no subfolders)
    # and category should be extracted from filename
    filename_based_datasets = ["vizwiz"]
    
    # Walk through all subdirectories
    for dataset_dir in data_path.iterdir():
        if not dataset_dir.is_dir():
            continue
        
        dataset_name = dataset_dir.name
        is_filename_based = dataset_name.lower() in filename_based_datasets
        
        # Check for nested category folders or direct images
        for item in dataset_dir.iterdir():
            if item.is_dir():
                # Category folder (normal structure)
                category_folder = item.name
                for img_file in item.iterdir():
                    if img_file.is_file() and img_file.suffix.lower() in valid_extensions:
                        images.append({
                            "image_id": img_file.name,
                            "image_path": str(img_file),
                            "folder_name": category_folder,
                            "dataset_source": dataset_name
                        })
            elif item.is_file() and item.suffix.lower() in valid_extensions:
                # Direct image in dataset folder
                if is_filename_based:
                    # Extract category from filename (e.g., VizWiz)
                    category = extract_category_from_filename(item.name)
                else:
                    # Use folder name as category
                    category = dataset_name
                
                images.append({
                    "image_id": item.name,
                    "image_path": str(item),
                    "folder_name": category,
                    "dataset_source": dataset_name
                })
    
    return images


def load_dataset(
    data_path: str,
    questions_config: Dict,
    load_images: bool = False,
    dataset_filter: Optional[str] = "UFV Campus"
) -> List[ImageSample]:
    """
    Load all images from the dataset directory.
    
    Args:
        data_path: Path to the data directory
        questions_config: Questions configuration dictionary
        load_images: Whether to load images into memory (False for lazy loading)
        dataset_filter: Optional dataset source to filter by (default: "UFV Campus")
                        Set to None to load all datasets
    
    Returns:
        List of ImageSample objects
    """
    folder_mapping = questions_config.get("folder_to_category_mapping", {})
    excluded_categories = questions_config.get("excluded_categories", [])
    
    # Discover all images
    raw_images = discover_images(data_path)
    
    samples = []
    excluded_count = 0
    filtered_count = 0
    
    for img_info in raw_images:
        category = get_category_from_folder(img_info["folder_name"], folder_mapping)
        
        # Skip excluded categories
        if category in excluded_categories:
            excluded_count += 1
            continue
        
        dataset_source = get_dataset_source(img_info["image_path"])
        
        # Filter by dataset source if specified
        if dataset_filter is not None and dataset_source != dataset_filter:
            filtered_count += 1
            continue
        
        sample = ImageSample(
            image_id=img_info["image_id"],
            image_path=img_info["image_path"],
            category=category,
            dataset_source=dataset_source,
            image=None
        )
        
        if load_images:
            try:
                sample.image = Image.open(img_info["image_path"]).convert("RGB")
            except Exception as e:
                print(f"Warning: Could not load image {img_info['image_path']}: {e}")
        
        samples.append(sample)
    
    print(f"Loaded {len(samples)} images from {data_path}")
    if dataset_filter:
        print(f"  (Filtered to dataset: {dataset_filter})")
    if filtered_count > 0:
        print(f"  (Excluded {filtered_count} images from other datasets)")
    if excluded_count > 0:
        print(f"  (Excluded {excluded_count} images from categories: {excluded_categories})")
    return samples


def get_questions_for_category(category: str, questions_config: Dict) -> List[Question]:
    """
    Get all questions for a specific category.
    
    Args:
        category: Category name
        questions_config: Questions configuration dictionary
    
    Returns:
        List of Question objects
    """
    categories = questions_config.get("categories", {})
    
    if category not in categories:
        print(f"Warning: Category '{category}' not found in questions config")
        return []
    
    category_data = categories[category]
    questions = []
    
    for q_data in category_data.get("questions", []):
        question = Question(
            question_id=q_data.get("id", ""),
            question_type=q_data.get("type", ""),
            question_text=q_data.get("question", ""),
            expected_answer=q_data.get("expected_answer"),
            expected_keywords=q_data.get("expected_keywords", []),
            reference_answer=q_data.get("reference_answer"),
            metrics=q_data.get("metrics", []),
            acceptable_answers=q_data.get("acceptable_answers", []),
            expected_keywords_primary=q_data.get("expected_keywords_primary"),
            expected_keywords_secondary=q_data.get("expected_keywords_secondary")
        )
        questions.append(question)
    
    return questions


def generate_acceptable_answers(expected_answer: str, question_id: str) -> List[str]:
    """
    Generate acceptable answers (synonyms) based on expected answer and question context.
    
    Args:
        expected_answer: The expected answer for this image-question pair
        question_id: The question ID to determine context-specific synonyms
    
    Returns:
        List of acceptable answers (synonyms)
    """
    expected_lower = expected_answer.lower()
    
    # Base synonyms for common answers
    synonyms_map = {
        "yes": ["yes", "there is", "there are", "i can see", "it is", "this is"],
        "no": ["no", "there is no", "there are no", "i cannot see", "i don't see", "not a", "isn't", "aren't"],
        "up": ["up", "upward", "ascending", "going up"],
        "down": ["down", "downward", "descending", "going down"],
        "open": ["open", "opened", "ajar"],
        "closed": ["closed", "shut", "sealed"],
        "blocking": ["blocking", "blocking me", "blocked", "obstructed", "path blocked", "cannot walk"],
        "clear": ["clear", "straight ahead", "free", "can walk"],
    }
    
    # Question-specific synonyms
    question_synonyms = {
        "staircase_detection": {
            "yes": ["staircase", "stairs", "steps", "stairway"]
        },
        "elevator_detection": {
            "yes": ["elevator", "lift"]
        },
        "door_detection": {
            "yes": ["door", "doors", "entrance", "exit"]
        },
        "doorsign_bathroom": {
            "yes": ["bathroom", "restroom", "toilet", "wc"]
        },
        "doorsign_exit": {
            "yes": ["exit", "entrance", "way out"]
        },
        "corridor_detection": {
            "yes": ["corridor", "hallway", "hall", "passage"]
        },
        "crossing_detection": {
            "yes": ["crossing", "crosswalk", "zebra", "pedestrian crossing"]
        },
        "obstacle_detection": {
            "yes": ["object", "obstacle", "blocking"]
        },
        "staircase_handrails": {
            "yes": ["handrail", "handrails", "railing", "railings"],
            "no": ["none", "no handrails"]
        },
        "corridor_clear": {
            "yes": ["clear", "free"],
            "no": ["blocked", "obstructed"]
        },
        "corridor_doors": {
            "yes": ["door", "doors", "visible"],
            "no": ["no doors", "none"]
        }
    }
    
    # Start with base synonyms
    acceptable = synonyms_map.get(expected_lower, [expected_answer])
    
    # Add question-specific synonyms if available
    if question_id in question_synonyms:
        question_syns = question_synonyms[question_id]
        if expected_lower in question_syns:
            acceptable.extend(question_syns[expected_lower])
    
    # Always include the expected answer itself
    if expected_answer not in acceptable:
        acceptable.insert(0, expected_answer)
    
    # Remove duplicates while preserving order
    seen = set()
    result = []
    for item in acceptable:
        item_lower = item.lower()
        if item_lower not in seen:
            seen.add(item_lower)
            result.append(item)
    
    return result


def create_evaluation_items(
    samples: List[ImageSample],
    questions_config: Dict,
    per_image_answers: Optional[Dict[str, Dict[str, str]]] = None
) -> List[EvaluationItem]:
    """
    Create evaluation items by pairing images with their questions.
    
    Args:
        samples: List of ImageSample objects
        questions_config: Questions configuration dictionary
        per_image_answers: Optional dictionary mapping image filenames to 
                          question_id -> expected_answer mappings.
                          If provided, will override default expected_answer
                          from questions_config for specific image-question pairs.
    
    Returns:
        List of EvaluationItem objects
    """
    eval_items = []
    
    if per_image_answers is None:
        per_image_answers = {}
    
    for sample in samples:
        questions = get_questions_for_category(sample.category, questions_config)
        
        for question in questions:
            # Get per-image data
            image_answers = per_image_answers.get(sample.image_id, {})
            per_image_answer = image_answers.get(question.question_id)
            # For caption questions, look for "caption_reference", otherwise use question_id_reference
            if question.question_type == "caption":
                per_image_reference = image_answers.get("caption_reference")
            else:
                per_image_reference = image_answers.get(f"{question.question_id}_reference")
            per_image_keywords = image_answers.get(f"{question.question_id}_keywords")
            per_image_keywords_primary = image_answers.get(f"{question.question_id}_keywords_primary")
            per_image_keywords_secondary = image_answers.get(f"{question.question_id}_keywords_secondary")
            
            # Determine expected_answer (per-image takes priority, then default from questions.json)
            final_expected_answer = per_image_answer if per_image_answer is not None else question.expected_answer
            
            # For closed questions without expected_answer, try to infer from question context
            # This handles cases where images are missing from ufv_expected_answers.json
            if final_expected_answer is None and question.question_type == "closed":
                if question.question_id.endswith("_detection"):
                    # Detection questions: if image is in this category, object should be present
                    final_expected_answer = "yes"
                elif question.question_id.endswith("_blocking"):
                    # Blocking questions: if image is in obstacle category, likely blocking
                    if sample.category == "obstacle":
                        final_expected_answer = "blocking me"
                # For other closed questions, we can't infer safely, so leave as None
                # (this will be logged but won't break the evaluation)
            
            # Determine keywords (per-image takes priority, then default from questions.json)
            final_keywords = per_image_keywords if per_image_keywords is not None else question.expected_keywords
            final_keywords_primary = per_image_keywords_primary if per_image_keywords_primary is not None else question.expected_keywords_primary
            final_keywords_secondary = per_image_keywords_secondary if per_image_keywords_secondary is not None else question.expected_keywords_secondary
            
            # Generate acceptable_answers automatically based on expected_answer
            # Only for closed questions and if we have an expected_answer
            if final_expected_answer is not None and question.question_type == "closed":
                generated_acceptable = generate_acceptable_answers(final_expected_answer, question.question_id)
            else:
                # For non-closed questions or if no expected_answer, use default or empty
                generated_acceptable = question.acceptable_answers if question.acceptable_answers else []
            
            # Check if we need to create a modified question copy
            # (if we have per-image data, modified expected_answer, or generated acceptable_answers)
            needs_copy = (
                per_image_answer is not None or 
                per_image_reference is not None or 
                per_image_keywords is not None or 
                per_image_keywords_primary is not None or 
                per_image_keywords_secondary is not None or
                final_expected_answer != question.expected_answer or  # expected_answer was modified (e.g., detection default)
                (generated_acceptable and question.question_type == "closed" and generated_acceptable != question.acceptable_answers)
            )
            
            if needs_copy:
                question_copy = Question(
                    question_id=question.question_id,
                    question_type=question.question_type,
                    question_text=question.question_text,
                    expected_answer=final_expected_answer,
                    expected_keywords=final_keywords,
                    reference_answer=per_image_reference if per_image_reference is not None else question.reference_answer,
                    metrics=question.metrics,
                    acceptable_answers=generated_acceptable,
                    expected_keywords_primary=final_keywords_primary,
                    expected_keywords_secondary=final_keywords_secondary
                )
            else:
                # Use default question as-is
                question_copy = question
            
            eval_item = EvaluationItem(
                image_sample=sample,
                question=question_copy
            )
            eval_items.append(eval_item)
    
    print(f"Created {len(eval_items)} evaluation items")
    return eval_items


def get_dataset_statistics(samples: List[ImageSample]) -> Dict:
    """
    Calculate statistics about the dataset.
    
    Args:
        samples: List of ImageSample objects
    
    Returns:
        Dictionary with dataset statistics
    """
    stats = {
        "total_images": len(samples),
        "by_category": {},
        "by_source": {}
    }
    
    for sample in samples:
        # Count by category
        if sample.category not in stats["by_category"]:
            stats["by_category"][sample.category] = 0
        stats["by_category"][sample.category] += 1
        
        # Count by source
        if sample.dataset_source not in stats["by_source"]:
            stats["by_source"][sample.dataset_source] = 0
        stats["by_source"][sample.dataset_source] += 1
    
    return stats


def limit_dataset_by_category(
    samples: List[ImageSample],
    images_per_category: int = 5
) -> List[ImageSample]:
    """
    Limit the dataset to a specified number of images per category.
    
    Useful for quick testing before running on the full dataset.
    
    Args:
        samples: List of ImageSample objects
        images_per_category: Maximum number of images per category
    
    Returns:
        Filtered list of ImageSample objects
    """
    # Group samples by category
    by_category = {}
    for sample in samples:
        if sample.category not in by_category:
            by_category[sample.category] = []
        by_category[sample.category].append(sample)
    
    # Take limited samples from each category
    limited_samples = []
    for category, cat_samples in by_category.items():
        limited_samples.extend(cat_samples[:images_per_category])
    
    print(f"⚡ Quick test mode: {len(limited_samples)} images ({images_per_category} per category)")
    return limited_samples


def print_dataset_summary(samples: List[ImageSample]) -> None:
    """Print a summary of the dataset."""
    stats = get_dataset_statistics(samples)
    
    print("\n" + "=" * 50)
    print("DATASET SUMMARY")
    print("=" * 50)
    print(f"Total images: {stats['total_images']}")
    
    print("\nBy Category:")
    for category, count in sorted(stats["by_category"].items()):
        print(f"  {category}: {count}")
    
    print("\nBy Source:")
    for source, count in sorted(stats["by_source"].items()):
        print(f"  {source}: {count}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    # Test the dataset loader
    print("Testing dataset loader...")
    
    # This is just for local testing
    config_path = "../config/questions.json"
    if os.path.exists(config_path):
        config = load_questions_config(config_path)
        print(f"Loaded {len(config['categories'])} categories")
