"""
Utility functions for loading and processing experiment data
"""
import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import config

def load_csv_expanded() -> pd.DataFrame:
    """Load the expanded CSV with all metrics"""
    csv_files = list(config.CSV_EXPANDED_PATH.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {config.CSV_EXPANDED_PATH}")
    
    df = pd.read_csv(csv_files[0])
    return df

def load_csv_reduced() -> pd.DataFrame:
    """Load the reduced CSV with essential metrics"""
    csv_files = list(config.CSV_REDUCED_PATH.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {config.CSV_REDUCED_PATH}")
    
    df = pd.read_csv(csv_files[0])
    return df

def load_environment_info() -> Dict:
    """Load experiment environment information"""
    json_files = list(config.ENVIRONMENT_DIR.glob("*.json"))
    if not json_files:
        return {}
    
    with open(json_files[0], 'r') as f:
        return json.load(f)

def load_model_metrics(model_name: str) -> Optional[Dict]:
    """Load metrics JSON for a specific model"""
    model_dir = config.METRICS_DIR / model_name
    json_files = list(model_dir.glob("*.json"))
    
    if not json_files:
        return None
    
    with open(json_files[0], 'r') as f:
        return json.load(f)

def load_model_results(model_name: str) -> Optional[List[Dict]]:
    """Load results JSON for a specific model"""
    model_dir = config.RESULTS_DIR_MODELS / model_name
    json_files = list(model_dir.glob("*.json"))
    
    if not json_files:
        return None
    
    with open(json_files[0], 'r') as f:
        return json.load(f)

def get_available_models() -> List[str]:
    """Get list of all available model names"""
    model_dirs = [d.name for d in config.METRICS_DIR.iterdir() if d.is_dir()]
    return sorted(model_dirs)

def get_confusion_matrix_path(model_name: str, cm_type: str) -> Optional[Path]:
    """Get path to a confusion matrix image"""
    model_dir = config.CONFUSION_MATRICES_DIR / model_name
    if not model_dir.exists():
        return None
    
    # Try different possible filenames
    possible_names = [
        f"{model_name}_{cm_type}.png",
        f"{model_name}_{cm_type.replace('_', '-')}.png",
    ]
    
    for name in possible_names:
        file_path = model_dir / name
        if file_path.exists():
            return file_path
    
    return None

def get_all_confusion_matrices(model_name: str) -> List[str]:
    """Get list of all available confusion matrices for a model"""
    model_dir = config.CONFUSION_MATRICES_DIR / model_name
    if not model_dir.exists():
        return []
    
    png_files = list(model_dir.glob("*.png"))
    # Extract CM type from filename (remove model_name prefix and .png)
    cm_types = []
    for png_file in png_files:
        name = png_file.stem  # filename without extension
        if name.startswith(model_name):
            cm_type = name[len(model_name)+1:]  # Remove model_name_ prefix
            cm_types.append(cm_type)
    
    return sorted(cm_types)

def filter_models(df: pd.DataFrame, 
                  version: Optional[str] = None,
                  size: Optional[str] = None,
                  model_type: Optional[str] = None,
                  resolution: Optional[int] = None,
                  search_text: Optional[str] = None) -> pd.DataFrame:
    """Filter models dataframe based on criteria"""
    filtered_df = df.copy()
    
    if version and version != "All":
        filtered_df = filtered_df[filtered_df["Version"] == version]
    
    if size and size != "All":
        filtered_df = filtered_df[filtered_df["Size"] == size]
    
    if model_type and model_type != "All":
        filtered_df = filtered_df[filtered_df["Type"] == model_type]
    
    if resolution and resolution != "All":
        filtered_df = filtered_df[filtered_df["Resolution"] == resolution]
    
    if search_text:
        search_lower = search_text.lower()
        filtered_df = filtered_df[
            filtered_df["Model ID"].str.lower().str.contains(search_lower) |
            filtered_df["Description"].str.lower().str.contains(search_lower)
        ]
    
    return filtered_df

def extract_model_name(model_id: str) -> str:
    """Extract model name from model_id (e.g., 'google/paligemma-3b-pt-224' -> 'paligemma-3b-pt-224')"""
    return model_id.split("/")[-1] if "/" in model_id else model_id

def format_metric_value(value: float, metric_name: str) -> str:
    """Format metric value for display"""
    if pd.isna(value):
        return "N/A"
    
    if "Accuracy" in metric_name or "Recall" in metric_name or "Precision" in metric_name or "F1" in metric_name or "Match" in metric_name:
        return f"{value:.4f}"
    elif "Time" in metric_name:
        return f"{value:.3f}"
    elif "Throughput" in metric_name:
        return f"{value:.2f}"
    elif "VRAM" in metric_name or "GB" in metric_name:
        return f"{value:.2f}"
    else:
        return f"{value:.2f}"
