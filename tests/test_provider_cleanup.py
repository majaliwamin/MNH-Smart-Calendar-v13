from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_retired_ai_vendor_references_remain_in_working_tree():
    # Construct the retired vendor marker from fragments so this audit does not
    # introduce the very string it is checking for.
    retired = "".join(("open", "ai"))
    model_marker = "".join(("gpt", "-4o"))
    endpoint_marker = "api." + retired + ".com"
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path.suffix.lower() not in {".py", ".js", ".css", ".html", ".json", ".yml", ".yaml", ".toml", ".md", ".txt", ".dart"}:
            continue
        try:
            content = path.read_text(encoding="utf-8").lower()
        except (UnicodeDecodeError, OSError):
            continue
        assert retired not in content, f"Retired vendor reference remains in {path.relative_to(ROOT)}"
        assert model_marker not in content, f"Retired model reference remains in {path.relative_to(ROOT)}"
        assert endpoint_marker not in content, f"Retired endpoint remains in {path.relative_to(ROOT)}"
