"""
Download VizWiz images filtered for indoor navigation relevance.
Only downloads clear, answerable images related to navigation scenarios.
"""

import os
import json
from datasets import load_dataset
from PIL import Image

# Configuration
NUM_IMAGES = 50
OUTPUT_DIR = "data/vizwiz_filtered/images"
METADATA_FILE = "data/vizwiz_filtered/metadata.json"

# Navigation-related keywords to filter by
NAVIGATION_KEYWORDS = [
    # Structural elements
    "door", "doors", "entrance", "exit", "hallway", "corridor", "hall",
    "stairs", "staircase", "step", "steps", "stairway",
    "elevator", "lift", "escalator",
    "room", "bathroom", "restroom", "toilet", "office", "lobby",
    "floor", "ground", "ceiling", "wall",
    
    # Signs and navigation
    "sign", "arrow", "direction", "left", "right", "straight",
    "exit sign", "emergency", "fire",
    
    # Obstacles and objects
    "chair", "table", "desk", "furniture", "obstacle",
    "trash", "bin", "cart", "box", "boxes",
    "ramp", "rail", "railing", "handrail",
    
    # Spatial questions
    "where", "way", "path", "route", "go", "walk", "turn",
    "ahead", "front", "behind", "near", "close",
    
    # Building elements
    "building", "window", "glass", "handle", "button", "switch",
    "light", "lamp", "dark", "bright",
]

def is_navigation_relevant(question, answers):
    """Check if the image is relevant to indoor navigation."""
    # Combine question and answers into searchable text
    text = question.lower()
    if answers:
        text += " " + " ".join(str(a).lower() for a in answers)
    
    # Check for navigation keywords
    for keyword in NAVIGATION_KEYWORDS:
        if keyword in text:
            return True
    return False

def main():
    print("Loading VizWiz dataset in streaming mode...")
    print(f"Target: {NUM_IMAGES} navigation-relevant, clear images")
    print()
    
    # Load VizWiz VQA dataset in streaming mode
    dataset = load_dataset(
        "Multimodal-Fatima/VizWiz_train", 
        split="train", 
        streaming=True
    )
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    metadata = []
    count = 0
    scanned = 0
    
    print("Scanning for navigation-relevant images...")
    
    for sample in dataset:
        scanned += 1
        
        # Skip unanswerable images (usually blurry)
        if sample.get('answerable', 0) != 1:
            continue
        
        question = sample.get('question', '')
        answers = sample.get('answers', [])
        
        # Check if navigation-relevant
        if not is_navigation_relevant(question, answers):
            continue
        
        # Found a relevant image!
        image = sample['image']
        
        # Check image quality (skip very small images)
        if image.width < 200 or image.height < 200:
            continue
        
        # Save image
        image_filename = f"nav_{count:03d}.jpg"
        image_path = os.path.join(OUTPUT_DIR, image_filename)
        
        # Convert to RGB if necessary and save
        if image.mode != 'RGB':
            image = image.convert('RGB')
        image.save(image_path, 'JPEG', quality=95)
        
        # Determine category based on keywords
        category = "general"
        text = (question + " " + " ".join(str(a) for a in answers)).lower()
        if any(k in text for k in ["stair", "step"]):
            category = "stairs"
        elif any(k in text for k in ["door", "entrance", "exit"]):
            category = "door"
        elif any(k in text for k in ["hallway", "corridor", "hall"]):
            category = "hallway"
        elif any(k in text for k in ["elevator", "lift"]):
            category = "elevator"
        elif any(k in text for k in ["sign", "arrow", "direction"]):
            category = "sign"
        elif any(k in text for k in ["chair", "table", "furniture", "obstacle"]):
            category = "obstacle"
        elif any(k in text for k in ["room", "bathroom", "office"]):
            category = "room"
        
        # Store metadata
        metadata.append({
            "id": count,
            "filename": image_filename,
            "category": category,
            "original_question": question,
            "original_answers": answers,
            "image_size": f"{image.width}x{image.height}"
        })
        
        print(f"[{count + 1}/{NUM_IMAGES}] Found: {image_filename} ({category})")
        print(f"         Q: {question[:60]}...")
        
        count += 1
        
        if count >= NUM_IMAGES:
            break
    
    # Save metadata
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    print()
    print(f"Done! Scanned {scanned} images, found {count} navigation-relevant ones")
    print(f"Images saved to {OUTPUT_DIR}")
    print(f"Metadata saved to {METADATA_FILE}")
    
    # Summary by category
    print("\nImages by category:")
    categories = {}
    for m in metadata:
        cat = m['category']
        categories[cat] = categories.get(cat, 0) + 1
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  - {cat}: {count}")

if __name__ == "__main__":
    main()
