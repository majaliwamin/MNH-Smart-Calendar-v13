"""Execute the STAT 8100 notebook and regenerate the companion with real outputs."""

from __future__ import annotations

import json
import math
import os
import re
import sys
import tempfile
from pathlib import Path

import nbformat
from nbclient import NotebookClient

from build_stat8100_practical import (
    NOTEBOOK_PATH,
    RESULTS_PATH,
    ROOT,
    _atomic_write_text,
    build_html,
    build_notebook,
)

MARKER = "MNH_VERIFIED_RESULTS_JSON:"
SAMPLES = ROOT / "frontend" / "resources" / "samples"
KERNEL_NAME = "mnh-stat8100-verification"


def _reject_constant(value):
    raise ValueError(f"Non-finite JSON value: {value}")


def _strict_load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_constant)


def _same_value(left, right) -> bool:
    """Compare verified results with tolerances only for genuine floats."""
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if isinstance(left, int) and isinstance(right, int):
            return left == right
        return math.isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-9)
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            _same_value(left[key], right[key]) for key in left
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _same_value(a, b) for a, b in zip(left, right)
        )
    return left == right


def _install_temporary_kernel(temp_dir: str) -> None:
    """Pin the notebook kernel to the interpreter running this script."""
    spec_dir = Path(temp_dir) / "kernels" / KERNEL_NAME
    spec_dir.mkdir(parents=True, exist_ok=True)
    spec = {
        "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
        "display_name": "MNH STAT 8100 verification",
        "language": "python",
    }
    (spec_dir / "kernel.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    previous = os.environ.get("JUPYTER_PATH")
    os.environ["JUPYTER_PATH"] = (
        temp_dir + (os.pathsep + previous if previous else "")
    )


def _output_text(output: dict) -> str:
    kind = output.get("output_type")
    if kind == "stream":
        return output.get("text", "")
    if kind in ("execute_result", "display_data"):
        return output.get("data", {}).get("text/plain", "")
    return ""


def main():
    # The builder uses the last verified results for the worked examples.
    # Confirm those examples still match a fresh execution before writing.
    seed_results = _strict_load(RESULTS_PATH) if RESULTS_PATH.is_file() else {}
    original_notebook = NOTEBOOK_PATH.read_bytes() if NOTEBOOK_PATH.is_file() else None

    original_data_dir = os.environ.get("MNH_DATA_DIR")
    os.environ["MNH_DATA_DIR"] = str(SAMPLES)
    temp = tempfile.TemporaryDirectory(prefix="mnh-stat8100-kernel-")
    try:
        _install_temporary_kernel(temp.name)
        build_notebook()
        notebook = nbformat.read(NOTEBOOK_PATH, as_version=4)
        client = NotebookClient(
            notebook,
            timeout=900,
            kernel_name=KERNEL_NAME,
            resources={"metadata": {"path": str(ROOT)}},
            allow_errors=True,
        )
        client.execute()

        errors = [
            output.get("ename", "Error")
            for cell in notebook.cells
            for output in cell.get("outputs", [])
            if output.get("output_type") == "error"
        ]
        if errors:
            raise RuntimeError(f"Notebook execution produced errors: {errors}")

        code_cells = [cell for cell in notebook.cells if cell.get("cell_type") == "code"]
        marker_cells = []
        stream_text = []
        results = None
        for cell in notebook.cells:
            for output in cell.get("outputs", []):
                text = _output_text(output)
                if output.get("output_type") == "stream":
                    stream_text.append(text)
                if MARKER in text:
                    marker_cells.append((cell, text))

        if len(marker_cells) != 1:
            raise RuntimeError(
                f"Expected exactly one {MARKER} output, found {len(marker_cells)}."
            )
        marker_cell, marker_text = marker_cells[0]
        if not code_cells or marker_cell is not code_cells[-1]:
            raise RuntimeError("The verified-results marker must be the final code cell.")
        payload = marker_text.split(MARKER, 1)[1].strip()
        results = json.loads(payload, parse_constant=_reject_constant)

        if not isinstance(results, dict) or not results:
            raise RuntimeError("Could not extract the verified results record from the notebook.")
        if seed_results and not _same_value(results, seed_results):
            raise RuntimeError(
                "Executed results differ from the values used in the worked examples. "
                "Review the statistical changes, then regenerate the examples."
            )

        progress = [
            int(match.group(1))
            for match in re.finditer(
                r"Progress:.*?\b(\d+)/10 questions covered", "\n".join(stream_text)
            )
        ]
        # The reusable setup prints the initial 0/10 state; each question then
        # advances the shared progress counter through 10/10.
        if progress != list(range(0, 11)):
            raise RuntimeError(f"Unexpected progress sequence: {progress}")

        # Only write the executed notebook and companion after every check passes.
        _atomic_write_text(NOTEBOOK_PATH, nbformat.writes(notebook))
        build_html(results)
    except Exception:
        if original_notebook is not None:
            NOTEBOOK_PATH.write_bytes(original_notebook)
        raise
    finally:
        if original_data_dir is None:
            os.environ.pop("MNH_DATA_DIR", None)
        else:
            os.environ["MNH_DATA_DIR"] = original_data_dir
        previous = os.environ.get("JUPYTER_PATH", "")
        parts = [part for part in previous.split(os.pathsep) if part and "mnh-stat8100-kernel-" not in part]
        os.environ["JUPYTER_PATH"] = os.pathsep.join(parts)
        temp.cleanup()

    print(f"Executed notebook: {NOTEBOOK_PATH}")
    print(f"Verified results:  {RESULTS_PATH}")
    print(f"Recorded result groups: {len(results)}")


if __name__ == "__main__":
    sys.exit(main())
