"""
Model Loader for PaliGemma models.

This module provides functions to load PaliGemma models from HuggingFace
with proper configuration for GPU inference.
"""

import torch
import gc
from typing import Tuple, Optional
from transformers import AutoProcessor, PaliGemmaForConditionalGeneration


def get_device() -> str:
    """Get the available device (CUDA, MPS, or CPU)."""
    if torch.cuda.is_available():
        return "cuda"
    elif torch.backends.mps.is_available():
        return "mps"
    else:
        return "cpu"


def get_torch_dtype(device: str) -> torch.dtype:
    """Get the appropriate dtype for the device."""
    if device == "cuda":
        return torch.bfloat16
    elif device == "mps":
        return torch.float16
    else:
        return torch.float32


def load_paligemma(
    model_id: str,
    device: Optional[str] = None,
    use_flash_attention: bool = False,  # Disabled by default - requires flash_attn package
    max_memory: Optional[dict] = None,
    token: Optional[str] = None
) -> Tuple[PaliGemmaForConditionalGeneration, AutoProcessor]:
    """
    Load a PaliGemma model and processor from HuggingFace.
    
    Args:
        model_id: HuggingFace model ID (e.g., "google/paligemma2-3b-pt-448")
        device: Device to load model on ("cuda", "mps", "cpu", or None for auto)
        use_flash_attention: Whether to use Flash Attention 2 (CUDA only, requires flash_attn)
        max_memory: Optional memory constraints for model loading
    
    Returns:
        Tuple of (model, processor)
    
    Example:
        >>> model, processor = load_paligemma("google/paligemma2-3b-pt-448")
    """
    if device is None:
        device = get_device()
    
    torch_dtype = get_torch_dtype(device)
    
    print(f"Loading model: {model_id}")
    print(f"Device: {device}, dtype: {torch_dtype}")
    
    # Load processor
    processor = AutoProcessor.from_pretrained(model_id, token=token)
    
    # Configure model loading arguments
    model_kwargs = {
        "torch_dtype": torch_dtype,
        "low_cpu_mem_usage": True,
    }
    
    # Device mapping
    if device == "cuda":
        model_kwargs["device_map"] = "auto"
        
        # Try to use Flash Attention 2 if requested
        if use_flash_attention:
            try:
                import flash_attn  # Check if flash_attn is installed
                model_kwargs["attn_implementation"] = "flash_attention_2"
                print("✅ Using Flash Attention 2")
            except ImportError:
                print("⚠️ flash_attn not installed, using default attention")
                print("   To enable: pip install flash-attn --no-build-isolation")
        else:
            print("Using default attention (sdpa)")
    else:
        model_kwargs["device_map"] = device
    
    # Add memory constraints if provided
    if max_memory is not None:
        model_kwargs["max_memory"] = max_memory
    
    # Load model
    model = PaliGemmaForConditionalGeneration.from_pretrained(
        model_id,
        token=token,
        **model_kwargs
    )
    
    # Set to evaluation mode
    model.eval()
    
    print(f"✅ Model loaded successfully on {device}")
    print_gpu_memory()
    
    return model, processor


def unload_model(model, processor) -> None:
    """
    Unload a model and free GPU memory.
    
    Args:
        model: The model to unload
        processor: The processor to unload
    """
    del model
    del processor
    gc.collect()
    
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
    
    print("Model unloaded and memory cleared")


def print_gpu_memory() -> None:
    """Print current GPU memory usage."""
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / 1024**3
        reserved = torch.cuda.memory_reserved() / 1024**3
        print(f"GPU Memory: {allocated:.2f}GB allocated, {reserved:.2f}GB reserved")
    else:
        print("No CUDA GPU available")


def get_model_info(model_id: str) -> dict:
    """
    Extract model information from model_id.
    
    Args:
        model_id: HuggingFace model ID
    
    Returns:
        Dictionary with model version, size, type, and resolution
    """
    info = {
        "model_id": model_id,
        "version": "v2" if "paligemma2" in model_id else "v1",
        "size": "10B" if "10b" in model_id.lower() else "3B",
        "type": "unknown",
        "resolution": 0
    }
    
    # Determine type
    if "docci" in model_id.lower():
        info["type"] = "docci"
    elif "mix" in model_id.lower():
        info["type"] = "mix"
    elif "pt" in model_id.lower():
        info["type"] = "pt"
    
    # Extract resolution
    for res in [224, 448, 896]:
        if str(res) in model_id:
            info["resolution"] = res
            break
    
    return info


if __name__ == "__main__":
    # Test loading a model
    print("Testing model loader...")
    
    # This will only work if running on a machine with GPU
    device = get_device()
    print(f"Detected device: {device}")
    
    if device == "cuda":
        print_gpu_memory()
