# Terminal Basics for Vibecoding

## What is a Terminal?

A terminal (also called command line, console, or shell) is a text-based interface for interacting with your computer. Instead of clicking buttons and icons, you type commands. While this might feel unfamiliar at first, it's the primary way developers and AI coding assistants like Claude Code work.

Don't worry about memorizing everything here — you can always come back to this guide, and Claude Code can help you with any command you're unsure about.

## Opening a Terminal

- **macOS**: Press `Cmd + Space`, type "Terminal", and press Enter. Or use iTerm2 if you have it installed.
- **Windows**: Install and open [Windows Terminal](https://aka.ms/terminal) with WSL (Windows Subsystem for Linux).
- **Linux**: Press `Ctrl + Alt + T` or find "Terminal" in your applications menu.

## Essential Commands

### Where Am I? (Navigation)

| Command | What It Does | Example |
|---------|-------------|---------|
| `pwd` | **P**rint **W**orking **D**irectory — shows your current location | `pwd` → `/Users/you/WhatToEatVibecoding` |
| `ls` | **L**i**s**t files and folders here | `ls` |
| `ls -la` | List ALL files (including hidden ones) with details | `ls -la` |
| `cd folder` | **C**hange **D**irectory — move into a folder | `cd data` |
| `cd ..` | Go up one level | `cd ..` |
| `cd ~` | Go to your home directory | `cd ~` |

**Think of it like a file explorer**, but instead of clicking folders, you type where you want to go.

### Looking at Files

| Command | What It Does | Example |
|---------|-------------|---------|
| `cat file` | Display the entire contents of a file | `cat README.md` |
| `head file` | Show just the first 10 lines | `head data/receipts/my_receipt.csv` |
| `wc -l file` | Count the number of lines in a file | `wc -l data/receipts/my_receipt.csv` |

### Managing Files

| Command | What It Does | Example |
|---------|-------------|---------|
| `mkdir name` | Make a new directory (folder) | `mkdir my_data` |
| `cp source dest` | Copy a file | `cp recipe.json data/recipes/json/` |
| `mv source dest` | Move or rename a file | `mv old.csv data/receipts/` |

### Project Commands (What You'll Use Most)

| Command | What It Does |
|---------|-------------|
| `uv run python script.py` | Run a Python script with all project dependencies available |
| `uv add package_name` | Add a new Python package to the project |
| `uv run uvicorn src.api.simple.main:app --reload --port 8000` | Start the simple API server |
| `uv run uvicorn src.api.authenticated.main:app --reload --port 8001` | Start the authenticated API server |
| `uv run streamlit run src/app/main.py` | Start the Streamlit web app |
| `uv run jupyter notebook` | Start Jupyter for interactive notebooks |
| `claude` | Start Claude Code in the current directory |

## Keyboard Shortcuts That Save Time

| Shortcut | What It Does |
|----------|-------------|
| `Tab` | Auto-complete file and folder names (press twice to see options) |
| `Up Arrow` | Recall the previous command (press multiple times to go further back) |
| `Ctrl + C` | **Stop** a running process (use this to stop servers) |
| `Ctrl + L` | Clear the terminal screen |
| `Ctrl + A` | Jump to the beginning of the line |
| `Ctrl + E` | Jump to the end of the line |

## Running Multiple Things at Once

For this project, you'll often need several things running simultaneously:

1. **Terminal 1**: The API server (`uv run uvicorn ...`)
2. **Terminal 2**: The Streamlit app (`uv run streamlit run ...`)
3. **Terminal 3**: Claude Code or running scripts

### How to Open New Terminals

- **macOS Terminal**: `Cmd + T` for a new tab, `Cmd + N` for a new window
- **iTerm2**: `Cmd + T` for a new tab, `Cmd + D` for a split pane
- **Windows Terminal**: `Ctrl + Shift + T` for a new tab
- **VS Code**: Click the `+` icon in the terminal panel

> **Important**: Each terminal starts in your home directory. You'll need to `cd` into the project folder in each new terminal:
> ```bash
> cd ~/path/to/WhatToEatVibecoding
> ```

## Understanding Command Output

When you run a command, the terminal shows its output. Here's what to look for:

- **No output usually means success**. Commands like `cp`, `mv`, and `mkdir` are silent when they work.
- **Error messages appear in red** (usually) and tell you what went wrong. Read them carefully!
- **A `$` or `%` prompt** means the terminal is ready for your next command.
- **No prompt visible** means something is still running (like a server). Use `Ctrl + C` to stop it.

## Common Mistakes and Fixes

**"command not found"** — The program isn't installed, or isn't in your PATH. For `uv`, restart your terminal after installation.

**"No such file or directory"** — You're trying to access something that doesn't exist at that path. Use `pwd` to check where you are, then `ls` to see what's actually there.

**"Permission denied"** — You don't have permission to access that file. On macOS/Linux, try adding `sudo` before the command (it will ask for your password).

**The terminal seems "stuck"** — A program is probably running. Try `Ctrl + C` to stop it. If that doesn't work, try `Ctrl + D` or close and reopen the terminal.

## Tips for Working with Claude Code

- **Start Claude Code** by typing `claude` in your terminal while in the project directory
- **Paste workstream prompts** directly into the Claude Code interface
- **Ask for help** with any terminal command — Claude Code can explain what commands do
- **Review generated files** by asking Claude Code to show you what it created, or by opening them in your text editor
- When Claude Code suggests a command, it will explain what it does before running it — read the explanation!

## Practice Exercise

Try these commands to get comfortable:

```bash
# 1. Navigate to the project
cd ~/path/to/WhatToEatVibecoding

# 2. See where you are
pwd

# 3. List everything in the project
ls

# 4. Look inside the data directory
ls data/

# 5. Look deeper into recipes
ls data/recipes/

# 6. Check the README
cat README.md

# 7. Go back to the project root
cd ~/path/to/WhatToEatVibecoding
```

If all of these work, you're ready to start the workstream!
