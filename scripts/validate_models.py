"""
Quick validation script to test if all models can be loaded successfully.
Run this before executing the full evaluation notebook.

Usage:
    python scripts/validate_models.py
"""

import json
import sys
from pathlib import Path
from PIL import Image
import torch
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env")
sys.path.insert(0, str(project_root))

from src.evaluation.model_loader import load_paligemma, unload_model


def validate_models():
    """Test loading all models from models.json"""
    models_path = project_root / "config" / "models.json"
    
    if not models_path.exists():
        print(f"❌ Error: {models_path} not found")
        return False
    
    with open(models_path, 'r') as f:
        config = json.load(f)
    
    models = config["models"]
    print(f"🔍 Validating {len(models)} models...\n")
    
    results = []
    
    # Create a dummy image for testing inference
    dummy_image = Image.new('RGB', (224, 224), color='black')
    test_question = "What is in this image?"
    
    for model_info in models:
        model_id = model_info["model_id"]
        model_desc = model_info["description"]
        
        print(f"Testing: {model_desc}")
        print(f"  Model ID: {model_id}")
        
        try:
            # Load model
            model, processor = load_paligemma(model_id)
            print(f"  ✅ Model loaded successfully")
            
            # Test inference
            try:
                inputs = processor(
                    text=test_question,
                    images=dummy_image,
                    return_tensors="pt"
                ).to(model.device)
                
                with torch.no_grad():
                    outputs = model.generate(
                        **inputs,
                        max_new_tokens=10,
                        do_sample=False
                    )
                
                # Decode output
                generated_text = processor.decode(outputs[0], skip_special_tokens=True)
                print(f"  ✅ Inference test successful (output: {generated_text[:50]}...)")
                
                results.append({
                    "model": model_desc,
                    "model_id": model_id,
                    "status": "✅ SUCCESS",
                    "error": None
                })
                
            except Exception as inf_error:
                print(f"  ⚠️  Model loaded but inference failed: {str(inf_error)}")
                results.append({
                    "model": model_desc,
                    "model_id": model_id,
                    "status": "⚠️  LOADED BUT INFERENCE FAILED",
                    "error": str(inf_error)
                })
            
            # Clean up
            unload_model(model, processor)
            print()
            
        except Exception as e:
            print(f"  ❌ FAILED - {str(e)}")
            results.append({
                "model": model_desc,
                "model_id": model_id,
                "status": "❌ FAILED",
                "error": str(e)
            })
            print()
    
    # Summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    successful = sum(1 for r in results if "✅" in r["status"])
    failed = len(results) - successful
    
    print(f"✅ Successful: {successful}/{len(results)}")
    print(f"❌ Failed: {failed}/{len(results)}")
    
    if failed > 0:
        print("\nFailed models:")
        for r in results:
            if "❌" in r["status"] or "⚠️" in r["status"]:
                print(f"  - {r['model']}")
                print(f"    Status: {r['status']}")
                if r['error']:
                    print(f"    Error: {r['error']}")
    
    return successful == len(results)


if __name__ == "__main__":
    success = validate_models()
    sys.exit(0 if success else 1)
