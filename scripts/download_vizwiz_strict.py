"""
Download VizWiz images with STRICT filtering for indoor navigation.
Only downloads images where the ANSWER (not just question) contains navigation elements.
"""

import os
import json
from datasets import load_dataset
from PIL import Image

# Configuration
NUM_IMAGES = 50
OUTPUT_DIR = "data/vizwiz_navigation/images"
METADATA_FILE = "data/vizwiz_navigation/metadata.json"

# STRICT navigation keywords - must appear in ANSWERS
# These are physical navigation elements, not products
NAVIGATION_ANSWERS = {
    "stairs": ["stairs", "staircase", "stairway", "stairwell", "steps"],
    "door": ["door", "doors", "doorway", "entrance", "exit", "gate"],
    "hallway": ["hallway", "corridor", "hall", "passageway", "aisle"],
    "elevator": ["elevator", "lift", "escalator"],
    "room": ["room", "lobby", "bathroom", "restroom", "office", "kitchen", "bedroom", "living room"],
    "furniture": ["chair", "chairs", "table", "desk", "couch", "sofa", "bench", "furniture"],
    "floor": ["floor", "ground", "carpet", "tile", "wood floor"],
    "wall": ["wall", "walls"],
    "window": ["window", "windows"],
    "sign": ["sign", "exit sign", "restroom sign", "arrow"],
}

# Words that indicate it's a PRODUCT, not navigation (EXCLUDE these)
PRODUCT_KEYWORDS = [
    "can", "bottle", "box", "package", "food", "drink", "soda", "juice",
    "medicine", "pill", "vitamin", "soap", "shampoo", "lotion",
    "shirt", "pants", "clothes", "shoe", "hat",
    "phone", "remote", "tv", "computer", "laptop", "tablet",
    "book", "magazine", "card", "money", "coin",
    "pet", "dog", "cat", "animal",
    "toy", "game", "dvd", "cd", "movie",
    "charger", "cable", "battery",
]

def get_navigation_category(answers):
    """Check if answers indicate a navigation-relevant image. Returns category or None."""
    if not answers:
        return None
    
    # Combine all answers
    answer_text = " ".join(str(a).lower() for a in answers)
    
    # First, check if it's a product (EXCLUDE)
    for product in PRODUCT_KEYWORDS:
        if product in answer_text:
            return None
    
    # Check for navigation categories
    for category, keywords in NAVIGATION_ANSWERS.items():
        for keyword in keywords:
            # Require word boundary match (not partial)
            if f" {keyword} " in f" {answer_text} " or answer_text.startswith(keyword) or answer_text.endswith(keyword):
                return category
    
    return None

def main():
    print("Loading VizWiz dataset with STRICT navigation filtering...")
    print(f"Target: {NUM_IMAGES} clear navigation-relevant images")
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
    
    # Track categories found
    category_counts = {cat: 0 for cat in NAVIGATION_ANSWERS.keys()}
    
    print("Scanning for STRICT navigation-relevant images...")
    print("(This may take a while as we're being very selective)")
    print()
    
    for sample in dataset:
        scanned += 1
        
        # Progress indicator
        if scanned % 1000 == 0:
            print(f"  Scanned {scanned} images, found {count} so far...")
        
        # Skip unanswerable images
        if sample.get('answerable', 0) != 1:
            continue
        
        question = sample.get('question', '')
        answers = sample.get('answers', [])
        
        # STRICT: Check if answers indicate navigation content
        category = get_navigation_category(answers)
        if category is None:
            continue
        
        # Check if we have enough of this category (balance the dataset)
        max_per_category = (NUM_IMAGES // len(NAVIGATION_ANSWERS)) + 5
        if category_counts[category] >= max_per_category:
            continue
        
        # Found a relevant image!
        image = sample['image']
        
        # Check image quality
        if image.width < 300 or image.height < 300:
            continue
        
        # Save image
        image_filename = f"{category}_{category_counts[category]:03d}.jpg"
        image_path = os.path.join(OUTPUT_DIR, image_filename)
        
        # Convert to RGB if necessary and save
        if image.mode != 'RGB':
            image = image.convert('RGB')
        image.save(image_path, 'JPEG', quality=95)
        
        # Get the most common answer
        answer_counts = {}
        for a in answers:
            a_str = str(a).lower()
            answer_counts[a_str] = answer_counts.get(a_str, 0) + 1
        top_answer = max(answer_counts.keys(), key=lambda x: answer_counts[x])
        
        # Store metadata
        metadata.append({
            "id": count,
            "filename": image_filename,
            "category": category,
            "question": question,
            "top_answer": top_answer,
            "all_answers": list(set(str(a) for a in answers)),
            "image_size": f"{image.width}x{image.height}"
        })
        
        category_counts[category] += 1
        count += 1
        
        print(f"[{count}/{NUM_IMAGES}] {category}: \"{top_answer}\"")
        print(f"         Q: {question[:50]}...")
        
        if count >= NUM_IMAGES:
            break
        
        # Safety limit - don't scan forever
        if scanned > 30000:
            print("\nReached scan limit. Saving what we have...")
            break
    
    # Save metadata
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    print()
    print(f"Done! Scanned {scanned} images, found {count} navigation-relevant ones")
    print(f"Images saved to {OUTPUT_DIR}")
    print(f"Metadata saved to {METADATA_FILE}")
    
    print("\nImages by category:")
    for cat, cnt in sorted(category_counts.items(), key=lambda x: -x[1]):
        if cnt > 0:
            print(f"  - {cat}: {cnt}")

if __name__ == "__main__":
    main()
