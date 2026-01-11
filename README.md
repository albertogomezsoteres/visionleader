# TFG Alberto Gomez

TFG (Trabajo Fin de Grado) project repository.

## Project: PaliGemma Evaluation for Indoor Navigation Assistance

This project evaluates PaliGemma vision-language models for assisting visually impaired users with indoor navigation.

## Project Structure

```
tfg/
├── data/
│   ├── corridors/      # Corridor images
│   ├── doors/          # Door images
│   ├── stairs/         # Staircase images
│   ├── obstacles/      # Obstacle images
│   ├── signs/          # Signage images
│   ├── vizwiz/         # VizWiz filtered images (generated)
│   └── dataset.json    # Dataset metadata
├── evaluation/
│   └── PaliGemma_Evaluation.ipynb   # Main evaluation notebook
├── scripts/
│   └── download_vizwiz.py           # VizWiz dataset downloader
└── docs/
    └── Project_Proposal_AlbertoGomezSoteres.pdf
```

## Scripts

### Download VizWiz Dataset

Downloads and filters the VizWiz VQA validation set for navigation-relevant images.

**Option 1: Direct Download** (no dependencies)
```bash
python scripts/download_vizwiz.py
```

**Option 2: Hugging Face** (recommended - more reliable)
```bash
pip install datasets pillow
python scripts/download_vizwiz_hf.py
```

**What it does:**
1. Downloads VizWiz VQA validation annotations
2. Filters for navigation keywords (door, stairs, corridor, exit, elevator, sign, etc.)
3. Downloads and extracts relevant images
4. Saves filtered results to `data/vizwiz/` and `data/vizwiz_filtered.json`

**Navigation keywords:** door, stairs, hallway, corridor, obstacle, exit, elevator, sign, room, floor, wall, wheelchair, accessible, ramp, entrance, bathroom, railing, etc.

## Running the Evaluation

1. Open `evaluation/PaliGemma_Evaluation.ipynb` in Google Colab
2. Add your Hugging Face token (required for PaliGemma access)
3. Add your GitHub token (for private repo access)
4. Run all cells

## Dataset

The dataset includes:
- **18 custom images** across 5 categories (corridors, doors, stairs, obstacles, signs)
- **VizWiz images** (10-12 selected from filtered validation set)

Each image has:
- Category and description
- Suggested questions for VQA
- Expected answers for evaluation