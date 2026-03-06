import os
import re
from pathlib import Path

# Path to your icons folder (adjust if needed)
ICON_DIR = Path(__file__).parent / "icons"

# Regex patterns for "white" in SVGs
WHITE_PATTERNS = [
    r"#fff\b",
    r"#ffffff\b",
    r"rgb\(\s*255\s*,\s*255\s*,\s*255\s*\)",
    r"\bwhite\b",
]

def to_black(svg_text: str) -> str:
    """Replace common 'white' color values with black in SVG text."""
    for pattern in WHITE_PATTERNS:
        svg_text = re.sub(pattern, "#000000", svg_text, flags=re.IGNORECASE)
    return svg_text

def main():
    if not ICON_DIR.exists():
        print(f"Icons folder not found: {ICON_DIR}")
        return

    for svg_path in ICON_DIR.glob("*.svg"):
        # Skip already-generated black variants
        if svg_path.stem.endswith("-black"):
            continue

        with svg_path.open("r", encoding="utf-8") as f:
            content = f.read()

        black_content = to_black(content)

        new_name = f"{svg_path.stem}-black.svg"
        new_path = svg_path.with_name(new_name)

        # Don't overwrite if it already exists
        if new_path.exists():
            print(f"Skipping existing file: {new_path.name}")
            continue

        with new_path.open("w", encoding="utf-8") as f:
            f.write(black_content)

        print(f"Created: {new_path.name}")

    print("Done.")

if __name__ == "__main__":
    main()
