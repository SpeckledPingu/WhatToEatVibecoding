# Getting Started with Jupyter Notebooks

## What Are Jupyter Notebooks?

Jupyter notebooks are **interactive documents** that mix:
- **Code cells** — write and run Python, see results immediately
- **Markdown cells** — add formatted text, headings, links, images
- **Output** — charts, tables, and printed text appear right below the code

Think of them as a lab notebook for code. Instead of running a whole script and seeing one big output, you run code **cell by cell**, exploring data step by step. This makes them perfect for:
- Learning new concepts (try things, see what happens)
- Exploring data (load it, look at it, ask questions)
- Creating reports (mix analysis with explanation)
- Prototyping (test ideas before putting them in scripts)

## Starting Jupyter

From the project directory, run:

```bash
uv run jupyter notebook
```

This opens Jupyter in your web browser. You'll see a file browser showing the project directory.

Navigate to the `notebooks/` folder and click on any `.ipynb` file to open it.

## The Jupyter Interface

### File Browser (Home Page)
- Shows files and folders in your project
- Click a `.ipynb` file to open it
- Use the "New" button (top right) to create a new notebook

### Notebook Editor
When you open a notebook, you'll see:

- **Menu bar** (top): File, Edit, View, Insert, Cell, Kernel, Help
- **Toolbar** (below menu): Quick buttons for common actions
- **Cells** (main area): The actual content — code or markdown blocks

## Working with Cells

### Cell Types
- **Code cells**: Have `In [ ]:` on the left. Write Python here.
- **Markdown cells**: Write formatted text (headers, lists, links, etc.)
- Change cell type: Cell menu → Cell Type, or press `Y` (code) / `M` (markdown)

### Running Cells
- **Shift + Enter**: Run the current cell AND move to the next one
- **Ctrl + Enter**: Run the current cell and stay on it
- **Cell → Run All**: Run every cell from top to bottom (good for a fresh start)

### Adding Cells
- Click the **+** button in the toolbar (adds a cell below the current one)
- Or use: Insert → Insert Cell Above / Insert Cell Below

### Deleting Cells
- Edit → Delete Cells
- Or press `D` twice in command mode (press `Esc` first to enter command mode)

## Running the Project Notebooks

The `notebooks/` directory contains four learning notebooks:

| Notebook | What You'll Learn |
|----------|------------------|
| `01_data_exploration.ipynb` | Loading data, first look, filtering, groupby |
| `02_join_operations.ipynb` | Inner, left, right, outer joins — the core of recipe matching |
| `03_visualization.ipynb` | Bar charts, pie charts, timelines with matplotlib |
| `04_data_cleaning.ipynb` | Step-by-step normalization and match rate improvement |

**Run them in order** — each builds on concepts from the previous one.

### Before running notebooks
Make sure your database is populated by running the ingestion and normalization pipelines:

```bash
uv run python -m src.ingestion.recipes
uv run python -m src.ingestion.receipts
uv run python -m src.ingestion.pantry
uv run python -m src.normalization.build_inventory
uv run python -m src.normalization.build_recipe_matching
```

## Saving Your Work

- **Ctrl + S** (or Cmd + S on Mac): Save the notebook
- Jupyter also creates **checkpoints** automatically (File → Revert to Checkpoint to undo)
- Notebooks save their **output** along with the code — so charts and printed results are preserved

## Tips for Using Claude Code with Notebooks

You can use Claude Code to help you write analysis cells:

1. Ask Claude to help you write a pandas query: *"How do I group my inventory by category and count items?"*
2. Ask Claude to explain code in the notebook: *"What does `.explode()` do on line 5?"*
3. Ask Claude to create a visualization: *"Create a bar chart of spending by store"*
4. Ask Claude to debug errors: paste the error message and ask what went wrong

## Common Issues and Solutions

### "ModuleNotFoundError: No module named 'src'"
Make sure you start Jupyter from the project root directory:
```bash
cd /path/to/WhatToEatVibecoding
uv run jupyter notebook
```

### "No data found" or empty DataFrames
Run the ingestion scripts first (see "Before running notebooks" above).

### Kernel dies or becomes unresponsive
- Kernel → Restart: Restarts Python (clears all variables — re-run cells from the top)
- Kernel → Restart & Run All: Fresh start, runs everything

### Charts don't display
Make sure you have `%matplotlib inline` at the top of your notebook (it's already included in the project notebooks).

### Changes to source code aren't reflected
If you modify files in `src/`, restart the kernel (Kernel → Restart) to pick up the changes. Python caches imported modules.

## Keyboard Shortcuts

Jupyter has two modes:
- **Edit mode** (green border): You're typing in a cell
- **Command mode** (blue border): You're navigating between cells (press `Esc` to enter)

### Command Mode Shortcuts
| Key | Action |
|-----|--------|
| `Enter` | Enter edit mode |
| `Shift + Enter` | Run cell, move to next |
| `A` | Insert cell above |
| `B` | Insert cell below |
| `D, D` | Delete cell |
| `M` | Change to markdown |
| `Y` | Change to code |
| `Z` | Undo cell deletion |

### Edit Mode Shortcuts
| Key | Action |
|-----|--------|
| `Esc` | Enter command mode |
| `Shift + Enter` | Run cell |
| `Tab` | Code completion |
| `Shift + Tab` | Show function documentation |
| `Ctrl + /` | Toggle comment |
