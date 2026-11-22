"""Execute the STAT 8100 notebook and regenerate the companion with real outputs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

from build_stat8100_practical import (
    NOTEBOOK_PATH,
    RESULTS_PATH,
    build_html,
    build_notebook,
    ROOT,
)

MARKER = "MNH_VERIFIED_RESULTS_JSON:"


def main():
    # The builder uses the last verified results for the worked examples.
    # Confirm that those examples still match a fresh execution before writing.
    seed_results = {}
    if RESULTS_PATH.is_file():
        seed_results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    build_notebook()
    notebook = nbformat.read(NOTEBOOK_PATH, as_version=4)
    client = NotebookClient(
        notebook,
        timeout=900,
        kernel_name="python3",
        resources={"metadata": {"path": str(ROOT)}},
        allow_errors=False,
    )
    client.execute()
    nbformat.write(notebook, NOTEBOOK_PATH)

    results = None
    errors = []
    for cell in notebook.cells:
        for output in cell.get("outputs", []):
            if output.get("output_type") == "error":
                errors.append(output.get("ename", "Error"))
            text = ""
            if output.get("output_type") == "stream":
                text = output.get("text", "")
            elif output.get("output_type") in ("execute_result", "display_data"):
                text = output.get("data", {}).get("text/plain", "")
            if MARKER in text:
                payload = text.split(MARKER, 1)[1]
                results = json.loads(payload.strip())

    if errors:
        raise RuntimeError(f"Notebook execution produced errors: {errors}")
    if not isinstance(results, dict) or not results:
        raise RuntimeError("Could not extract the verified results record from the notebook.")
    if seed_results and results != seed_results:
        raise RuntimeError(
            "Executed results differ from the values used in the worked examples. "
            "Re-run the build with fresh verified results."
        )

    build_html(results)
    print(f"Executed notebook: {NOTEBOOK_PATH}")
    print(f"Verified results:  {RESULTS_PATH}")
    print(f"Recorded result groups: {len(results)}")


if __name__ == "__main__":
    sys.exit(main())
