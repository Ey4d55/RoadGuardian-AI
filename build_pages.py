"""Export the tested simulation into GitHub Pages /docs; no dist directory."""
from pathlib import Path
from traffic_simulation import component_html

LABELS = {"CHILD_CROSSING":"حماية المشاة", "CONGESTION":"ازدحام مروري", "TRUCK_OVERHEIGHT":"حماية الجسور", "NORMAL":"حركة طبيعية", "AMBULANCE":"أولوية الإسعاف", "CLOUD_OFFLINE":"انقطاع السحابة"}

def main():
    root = Path(__file__).resolve().parent
    target = root / "docs" / "scenes"
    target.mkdir(parents=True, exist_ok=True)
    for key in LABELS:
        (target / (key.lower()+".html")).write_text(component_html(key), encoding="utf-8")
    (root / "docs" / ".nojekyll").touch()
    print("Exported 6 scenarios to docs/scenes; dist is not used.")

if __name__ == "__main__":
    main()
