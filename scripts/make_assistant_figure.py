"""Crop the assistant screenshot used in the README -> docs/figures/assistant_answer.png.

Source: docs/work_logs/screens/assistant/desktop-2-answer-with-cards.png (guided mode, no model).
Run: python scripts/make_assistant_figure.py
"""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
src = ROOT / "docs/work_logs/screens/assistant/desktop-2-answer-with-cards.png"
Image.open(src).crop((200, 130, 1080, 555)).save(ROOT / "docs/figures/assistant_answer.png", optimize=True)
