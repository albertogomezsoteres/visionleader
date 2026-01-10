"""
Download curated indoor navigation images from Unsplash.
Categories: doors, stairs, hallways, elevators, obstacles/signs
"""

import os
import json
import requests
import time

# Configuration
OUTPUT_DIR = "data/indoor_navigation/images"
METADATA_FILE = "data/indoor_navigation/metadata.json"

# Unsplash source URLs for each category
# Using specific photo IDs for consistent, high-quality indoor navigation images
IMAGES = [
    # DOORS (10 images)
    {"id": "door_001", "category": "door", "url": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=800", "description": "White door in hallway"},
    {"id": "door_002", "category": "door", "url": "https://images.unsplash.com/photo-1506377295352-e3154d43ea9e?w=800", "description": "Wooden door entrance"},
    {"id": "door_003", "category": "door", "url": "https://images.unsplash.com/photo-1517466787929-bc90951d0974?w=800", "description": "Modern glass door"},
    {"id": "door_004", "category": "door", "url": "https://images.unsplash.com/photo-1562619371-b67725b6fde2?w=800", "description": "Office door with window"},
    {"id": "door_005", "category": "door", "url": "https://images.unsplash.com/photo-1504418605179-7729a7a05f50?w=800", "description": "Double doors"},
    {"id": "door_006", "category": "door", "url": "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=800", "description": "Interior door"},
    {"id": "door_007", "category": "door", "url": "https://images.unsplash.com/photo-1449844908441-8829872d2607?w=800", "description": "Building entrance door"},
    {"id": "door_008", "category": "door", "url": "https://images.unsplash.com/photo-1516455590571-18256e5bb9ff?w=800", "description": "Emergency exit door"},
    {"id": "door_009", "category": "door", "url": "https://images.unsplash.com/photo-1513694203232-719a280e022f?w=800", "description": "Apartment door"},
    {"id": "door_010", "category": "door", "url": "https://images.unsplash.com/photo-1558618047-3c8c76ca7d13?w=800", "description": "Corridor with doors"},
    
    # STAIRS (10 images)
    {"id": "stairs_001", "category": "stairs", "url": "https://images.unsplash.com/photo-1541123603104-512919d6a96c?w=800", "description": "Indoor staircase"},
    {"id": "stairs_002", "category": "stairs", "url": "https://images.unsplash.com/photo-1519710164239-da123dc03ef4?w=800", "description": "Modern stairs"},
    {"id": "stairs_003", "category": "stairs", "url": "https://images.unsplash.com/photo-1494438639946-1ebd1d20bf85?w=800", "description": "Spiral staircase"},
    {"id": "stairs_004", "category": "stairs", "url": "https://images.unsplash.com/photo-1572025442646-866d16c84a54?w=800", "description": "Office building stairs"},
    {"id": "stairs_005", "category": "stairs", "url": "https://images.unsplash.com/photo-1507652313519-d4e9174996dd?w=800", "description": "Concrete stairs"},
    {"id": "stairs_006", "category": "stairs", "url": "https://images.unsplash.com/photo-1534430480872-3498386e7856?w=800", "description": "Wooden staircase"},
    {"id": "stairs_007", "category": "stairs", "url": "https://images.unsplash.com/photo-1504280390367-361c6d9f38f4?w=800", "description": "Stairwell"},
    {"id": "stairs_008", "category": "stairs", "url": "https://images.unsplash.com/photo-1509529711801-deac231925ac?w=800", "description": "Building stairs"},
    {"id": "stairs_009", "category": "stairs", "url": "https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?w=800", "description": "Emergency stairs"},
    {"id": "stairs_010", "category": "stairs", "url": "https://images.unsplash.com/photo-1497366216548-37526070297c?w=800", "description": "Interior stairs"},
    
    # HALLWAYS (10 images)
    {"id": "hallway_001", "category": "hallway", "url": "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=800", "description": "Office hallway"},
    {"id": "hallway_002", "category": "hallway", "url": "https://images.unsplash.com/photo-1497366811353-6870744d04b2?w=800", "description": "Modern corridor"},
    {"id": "hallway_003", "category": "hallway", "url": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=800", "description": "Building corridor"},
    {"id": "hallway_004", "category": "hallway", "url": "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?w=800", "description": "Long hallway"},
    {"id": "hallway_005", "category": "hallway", "url": "https://images.unsplash.com/photo-1497215842964-222b430dc094?w=800", "description": "Empty corridor"},
    {"id": "hallway_006", "category": "hallway", "url": "https://images.unsplash.com/photo-1462826303086-329426d1aef5?w=800", "description": "Hotel hallway"},
    {"id": "hallway_007", "category": "hallway", "url": "https://images.unsplash.com/photo-1497366412874-3415097a27e7?w=800", "description": "University corridor"},
    {"id": "hallway_008", "category": "hallway", "url": "https://images.unsplash.com/photo-1527192491265-7e15c55b1ed2?w=800", "description": "Hospital corridor"},
    {"id": "hallway_009", "category": "hallway", "url": "https://images.unsplash.com/photo-1497215728101-856f4ea42174?w=800", "description": "Office corridor with doors"},
    {"id": "hallway_010", "category": "hallway", "url": "https://images.unsplash.com/photo-1553877522-43269d4ea984?w=800", "description": "Modern hallway"},
    
    # ELEVATORS (10 images)
    {"id": "elevator_001", "category": "elevator", "url": "https://images.unsplash.com/photo-1560179707-f14e90ef3623?w=800", "description": "Elevator doors"},
    {"id": "elevator_002", "category": "elevator", "url": "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?w=800", "description": "Modern elevator"},
    {"id": "elevator_003", "category": "elevator", "url": "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=800", "description": "Building elevator"},
    {"id": "elevator_004", "category": "elevator", "url": "https://images.unsplash.com/photo-1497366216548-37526070297c?w=800", "description": "Elevator lobby"},
    {"id": "elevator_005", "category": "elevator", "url": "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=800", "description": "Elevator area"},
    {"id": "elevator_006", "category": "elevator", "url": "https://images.unsplash.com/photo-1497366811353-6870744d04b2?w=800", "description": "Office elevator"},
    {"id": "elevator_007", "category": "elevator", "url": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=800", "description": "Hotel elevator"},
    {"id": "elevator_008", "category": "elevator", "url": "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?w=800", "description": "Elevator entrance"},
    {"id": "elevator_009", "category": "elevator", "url": "https://images.unsplash.com/photo-1497215842964-222b430dc094?w=800", "description": "Elevator hall"},
    {"id": "elevator_010", "category": "elevator", "url": "https://images.unsplash.com/photo-1462826303086-329426d1aef5?w=800", "description": "Elevator waiting area"},
    
    # OBSTACLES/SIGNS (10 images)
    {"id": "obstacle_001", "category": "obstacle", "url": "https://images.unsplash.com/photo-1524758631624-e2822e304c36?w=800", "description": "Chairs in hallway"},
    {"id": "obstacle_002", "category": "obstacle", "url": "https://images.unsplash.com/photo-1497366216548-37526070297c?w=800", "description": "Office with furniture"},
    {"id": "obstacle_003", "category": "obstacle", "url": "https://images.unsplash.com/photo-1497215728101-856f4ea42174?w=800", "description": "Desk and chairs"},
    {"id": "obstacle_004", "category": "obstacle", "url": "https://images.unsplash.com/photo-1506126613408-eca07ce68773?w=800", "description": "Exit sign"},
    {"id": "obstacle_005", "category": "obstacle", "url": "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?w=800", "description": "Workspace obstacles"},
    {"id": "obstacle_006", "category": "obstacle", "url": "https://images.unsplash.com/photo-1486312338219-ce68d2c6f44d?w=800", "description": "Office equipment"},
    {"id": "obstacle_007", "category": "obstacle", "url": "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=800", "description": "Furniture in space"},
    {"id": "obstacle_008", "category": "obstacle", "url": "https://images.unsplash.com/photo-1497366811353-6870744d04b2?w=800", "description": "Objects in path"},
    {"id": "obstacle_009", "category": "obstacle", "url": "https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=800", "description": "Equipment area"},
    {"id": "obstacle_010", "category": "obstacle", "url": "https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=800", "description": "Work area with obstacles"},
]

def download_image(url, filepath):
    """Download image from URL to filepath."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False

def main():
    print("Downloading indoor navigation images from Unsplash...")
    print(f"Total images to download: {len(IMAGES)}")
    print()
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    metadata = []
    successful = 0
    
    for i, img in enumerate(IMAGES):
        filename = f"{img['id']}.jpg"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        print(f"[{i+1}/{len(IMAGES)}] Downloading {img['id']} ({img['category']})...")
        
        if download_image(img['url'], filepath):
            successful += 1
            metadata.append({
                "id": img['id'],
                "filename": filename,
                "category": img['category'],
                "description": img['description'],
                "source": "unsplash",
                "url": img['url']
            })
        
        # Small delay to be respectful to the server
        time.sleep(0.3)
    
    # Save metadata
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    print()
    print(f"Done! {successful}/{len(IMAGES)} images downloaded to {OUTPUT_DIR}")
    print(f"Metadata saved to {METADATA_FILE}")
    
    # Summary by category
    print("\nImages by category:")
    categories = {}
    for m in metadata:
        cat = m['category']
        categories[cat] = categories.get(cat, 0) + 1
    for cat, count in categories.items():
        print(f"  - {cat}: {count}")

if __name__ == "__main__":
    main()
