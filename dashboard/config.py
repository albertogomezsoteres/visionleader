"""
Configuration file for the PaliGemma Evaluation Dashboard
"""
import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.parent
RESULTS_DIR = BASE_DIR / "results" / "ufv_experiment_20260113"

# Data paths
CSV_EXPANDED_PATH = RESULTS_DIR / "comparison" / "comparison_expanded"
CSV_REDUCED_PATH = RESULTS_DIR / "comparison" / "comparison_reduced"
METRICS_DIR = RESULTS_DIR / "metrics"
RESULTS_DIR_MODELS = RESULTS_DIR / "results"
CONFUSION_MATRICES_DIR = RESULTS_DIR / "confusion_matrices"
ENVIRONMENT_DIR = RESULTS_DIR / "environment"

# Column mappings for display
METRIC_DISPLAY_NAMES = {
    "Exact Match": "Exact Match",
    "Keyword Recall": "Keyword Recall",
    "BERTScore Recall": "BERTScore Recall",
    "BERTScore F1": "BERTScore F1",
    "BERTScore Precision": "BERTScore Precision",
    "Throughput (images/sec)": "Throughput (img/s)",
    "Avg Inference Time (s)": "Avg Inference Time (s)",
    "VRAM Usage (GB)": "VRAM Usage (GB)",
    "Avg Output Length (words)": "Avg Output Length (words)",
}

# Color schemes
COLOR_SCHEME = {
    "v1": "#4472C4",  # Blue
    "v2": "#70AD47",  # Green
    "3B": "#5B9BD5",  # Light blue
    "10B": "#FFC000",  # Orange
    "pt": "#7030A0",  # Purple
    "mix": "#C00000",  # Red
    "ft-docci": "#00B050",  # Green
}

# Confusion matrix types
CM_TYPES = [
    "binary_yes_no_global",
    "binary_yes_no_staircase",
    "binary_yes_no_elevator",
    "binary_yes_no_door",
    "binary_yes_no_door_sign",
    "binary_yes_no_obstacle",
    "state_open_closed_global",
    "state_up_down_global",
    "navigation_elements_global",
    "navigation_elements_staircase",
    "navigation_elements_elevator",
    "navigation_elements_door",
]
