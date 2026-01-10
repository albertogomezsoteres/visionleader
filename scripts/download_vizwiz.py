"""
Download 50 images from VizWiz dataset for PaliGemma evaluation.
VizWiz contains images taken by blind users with questions about them.
Uses streaming mode to avoid downloading the entire dataset.
"""

import os
import json
from datasets import load_dataset
from PIL import Image

# Configuration
NUM_IMAGES = 50
OUTPUT_DIR = "data/vizwiz/images"
METADATA_FILE = "data/vizwiz/metadata.json"

def main():
    print("Loading VizWiz dataset in streaming mode...")
    
    # Load VizWiz VQA dataset in streaming mode (no full download)
    dataset = load_dataset(
        "Multimodal-Fatima/VizWiz_train", 
        split="train", 
        streaming=True
    )
    
    print(f"Selecting {NUM_IMAGES} images...")
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    metadata = []
    count = 0
    
    # Take first NUM_IMAGES samples (streaming)
    for sample in dataset:
        if count >= NUM_IMAGES:
            break
            
        # Get image
        image = sample['image']
        
        # Save image
        image_filename = f"vizwiz_{count:03d}.jpg"
        image_path = os.path.join(OUTPUT_DIR, image_filename)
        
        # Convert to RGB if necessary and save
        if image.mode != 'RGB':
            image = image.convert('RGB')
        image.save(image_path, 'JPEG', quality=95)
        
        # Store metadata
        metadata.append({
            "id": count,
            "filename": image_filename,
            "original_question": sample.get('question', ''),
            "original_answers": sample.get('answers', []),
            "answerable": sample.get('answerable', None)
        })
        
        print(f"Downloaded {count + 1}/{NUM_IMAGES}: {image_filename}")
        count += 1
    
    # Save metadata
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    print(f"\nDone! {count} images saved to {OUTPUT_DIR}")
    print(f"Metadata saved to {METADATA_FILE}")

if __name__ == "__main__":
    main()
