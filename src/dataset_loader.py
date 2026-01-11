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
    elif "bathroom" in filename_lower or "restroom" in filename_lower:
        return "door_bathroom"
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
    load_images: bool = False
) -> List[ImageSample]:
    """
    Load all images from the dataset directory.
    
    Args:
        data_path: Path to the data directory
        questions_config: Questions configuration dictionary
        load_images: Whether to load images into memory (False for lazy loading)
    
    Returns:
        List of ImageSample objects
    """
    folder_mapping = questions_config.get("folder_to_category_mapping", {})
    
    # Discover all images
    raw_images = discover_images(data_path)
    
    samples = []
    for img_info in raw_images:
        category = get_category_from_folder(img_info["folder_name"], folder_mapping)
        
        sample = ImageSample(
            image_id=img_info["image_id"],
            image_path=img_info["image_path"],
            category=category,
            dataset_source=get_dataset_source(img_info["image_path"]),
            image=None
        )
        
        if load_images:
            try:
                sample.image = Image.open(img_info["image_path"]).convert("RGB")
            except Exception as e:
                print(f"Warning: Could not load image {img_info['image_path']}: {e}")
        
        samples.append(sample)
    
    print(f"Loaded {len(samples)} images from {data_path}")
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
            acceptable_answers=q_data.get("acceptable_answers", [])
        )
        questions.append(question)
    
    return questions


def create_evaluation_items(
    samples: List[ImageSample],
    questions_config: Dict
) -> List[EvaluationItem]:
    """
    Create evaluation items by pairing images with their questions.
    
    Args:
        samples: List of ImageSample objects
        questions_config: Questions configuration dictionary
    
    Returns:
        List of EvaluationItem objects
    """
    eval_items = []
    
    for sample in samples:
        questions = get_questions_for_category(sample.category, questions_config)
        
        for question in questions:
            eval_item = EvaluationItem(
                image_sample=sample,
                question=question
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
