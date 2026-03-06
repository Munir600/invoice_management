import os
from pathlib import Path

# All SVGs copied from your icons.tsx
ICONS = {
    "dashboard": """
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"
     viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <rect x="3" y="3" width="7" height="7"/>
  <rect x="14" y="3" width="7" height="7"/>
  <rect x="14" y="14" width="7" height="7"/>
  <rect x="3" y="14" width="7" height="7"/>
</svg>
""",
    "file": """
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"
     viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
  <polyline points="14 2 14 8 20 8"/>
</svg>
""",
    "credit": """
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"
     viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <rect x="1" y="4" width="22" height="16" rx="2" ry="2"/>
  <line x1="1" y1="10" x2="23" y2="10"/>
</svg>
""",
    "book": """
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"
     viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
</svg>
""",
    "bar": """
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"
     viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <line x1="12" y1="2" x2="12" y2="22"/>
  <path d="M17 5H9.5a1.5 1.5 0 0 0-1.5 1.5v12a1.5 1.5 0 0 0 1.5 1.5H17"/>
</svg>
""",
    "settings": """
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"
     viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <circle cx="12" cy="12" r="3"/>
  <path d="M12 1v6m0 6v6M4.22 4.22l4.24 4.24m5.08 5.08l4.24 4.24M1 12h6m6 0h6M4.22 19.78l4.24-4.24m5.08-5.08l4.24-4.24"/>
</svg>
""",
    "chevron": """
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"
     viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <polyline points="9 18 15 12 9 6"/>
</svg>
""",
    "sun": """
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"
     viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <circle cx="12" cy="12" r="5"/>
  <line x1="12" y1="1" x2="12" y2="3"/>
  <line x1="12" y1="21" x2="12" y2="23"/>
  <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
  <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
  <line x1="1" y1="12" x2="3" y2="12"/>
  <line x1="21" y1="12" x2="23" y2="12"/>
  <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
  <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
</svg>
""",
    "moon": """
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"
     viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
</svg>
""",
    "plus": """
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"
     viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <line x1="12" y1="5" x2="12" y2="19"/>
  <line x1="5" y1="12" x2="19" y2="12"/>
</svg>
""",
    "edit": """
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"
     viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>
</svg>
""",
    "trending": """
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"
     viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <polyline points="23 6 13.5 15.5 8.5 10.5 1 17"/>
  <polyline points="17 6 23 6 23 12"/>
</svg>
""",
    "search": """
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"
     viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <circle cx="11" cy="11" r="8"/>
  <path d="m21 21-4.35-4.35"/>
</svg>
""",
    "download": """
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"
     viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path d="M21 16V8a2 2 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
  <polyline points="7 10 12 15 17 10"/>
  <line x1="12" y1="15" x2="12" y2="3"/>
</svg>
""",
    "users": """
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"
     viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
  <circle cx="9" cy="7" r="4"/>
  <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
  <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
</svg>
""",
    "package": """
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"
     viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <line x1="16.5" y1="9.4" x2="7.5" y2="4.21"/>
  <path d="M21 16V8a2 2 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
  <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
  <line x1="12" y1="22.08" x2="12" y2="12"/>
</svg>
""",
    "user": """
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"
     viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
  <circle cx="12" cy="7" r="4"/>
</svg>
""",
    "logout": """
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"
     viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
  <polyline points="16 17 21 12 16 7"/>
  <line x1="21" y1="12" x2="9" y2="12"/>
</svg>
""",
    "menu": """
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"
     viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <line x1="8" y1="6" x2="21" y2="6"/>
  <line x1="8" y1="12" x2="21" y2="12"/>
  <line x1="8" y1="18" x2="21" y2="18"/>
</svg>
""",

"trash": """
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
    >
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
      <line x1="10" y1="11" x2="10" y2="17" />
      <line x1="14" y1="11" x2="14" y2="17" />
    </svg>

    """,


}


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    icons_dir = base_dir / "icons"
    icons_dir.mkdir(exist_ok=True)

    for name, svg in ICONS.items():
        path = icons_dir / f"{name}.svg"
        svg_clean = svg.strip() + "\n"
        path.write_text(svg_clean, encoding="utf-8")
        print(f"✅ wrote {path}")

    print(f"\nAll icons written to: {icons_dir}")


if __name__ == "__main__":
    main()
