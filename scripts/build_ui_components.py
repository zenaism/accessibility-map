"""Build the generated components test page (build/ui_components/components.html). Not shipped to users."""

from atlas.ui_components_page import ROOT, build

if __name__ == "__main__":
    p = build()
    print(f"{p.relative_to(ROOT)}  {p.stat().st_size // 1024} KB")
