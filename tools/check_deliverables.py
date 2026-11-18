"""Check files before delivery; structural checks do not replace visual review."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

def check_file(path: Path) -> dict:
    result = {"file": str(path), "errors": [], "warnings": [], "details": {}}
    if not path.is_file():
        result["errors"].append("File does not exist or is not a regular file")
        result["status"] = "FAIL"
        return result
    try:
        size = path.stat().st_size
        result["bytes"] = size
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        result["errors"].append(f"Cannot read file: {exc}")
        result["status"] = "FAIL"
        return result
    result["sha256"] = digest.hexdigest()
    if size == 0:
        result["errors"].append("File is empty")
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            json.loads(path.read_text(encoding="utf-8-sig"))
        elif suffix in {".zip", ".xlsx", ".docx", ".pptx"}:
            with zipfile.ZipFile(path) as archive:
                broken = archive.testzip()
                if broken:
                    result["errors"].append(f"Corrupt archive entry: {broken}")
                members = set(archive.namelist())
                required = {".xlsx": "xl/workbook.xml", ".docx": "word/document.xml", ".pptx": "ppt/presentation.xml"}.get(suffix)
                if required and (required not in members or "[Content_Types].xml" not in members):
                    result["errors"].append("Missing required Office document structure")
            if suffix == ".xlsx" and not result["errors"]:
                check_workbook(path, result)
            if suffix in {".docx", ".pptx"}:
                result["warnings"].append("Render and inspect layout, fonts and clipping before delivery")
        elif suffix == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(path)
            if reader.is_encrypted:
                result["warnings"].append("Encrypted PDF: page content was not inspected")
            else:
                result["details"]["pages"] = len(reader.pages)
                if not reader.pages:
                    result["errors"].append("PDF has no pages")
                result["warnings"].append("Render and visually inspect all pages before delivery")
        elif suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            from PIL import Image
            with Image.open(path) as image:
                result["details"]["dimensions"] = list(image.size)
                image.verify()
            result["warnings"].append("Check spelling, crop, text size and requested dimensions visually")
        elif suffix in {".mp4", ".mov", ".mkv", ".webm"}:
            check_video(path, result)
        else:
            result["warnings"].append("Only existence, size and checksum checked for this file type")
    except ImportError as exc:
        result["warnings"].append(f"Format check not run; optional dependency missing: {exc.name}")
    except Exception as exc:
        result["errors"].append(f"Format check failed: {type(exc).__name__}: {exc}")
    result["status"] = "FAIL" if result["errors"] else ("REVIEW" if result["warnings"] else "PASS")
    return result


def check_workbook(path: Path, result: dict) -> None:
    from openpyxl import load_workbook
    formulas = load_workbook(path, data_only=False, read_only=True)
    cached = load_workbook(path, data_only=True, read_only=True)
    formula_count = 0
    missing_cache = 0
    try:
        result["details"]["sheets"] = formulas.sheetnames
        if not any(sheet.sheet_state == "visible" for sheet in formulas):
            result["errors"].append("Workbook has no visible worksheet")
        for sheet in formulas:
            cached_sheet = cached[sheet.title]
            for row, cached_row in zip(sheet.iter_rows(), cached_sheet.iter_rows()):
                for cell, cached_cell in zip(row, cached_row):
                    if cell.data_type == "e":
                        result["errors"].append(f"{sheet.title}!{cell.coordinate}: {cell.value}")
                    if cell.data_type != "f":
                        continue
                    formula_count += 1
                    if "#REF!" in cell.value.upper() or cached_cell.data_type == "e":
                        result["errors"].append(f"{sheet.title}!{cell.coordinate}: formula error")
                    if cached_cell.value is None:
                        missing_cache += 1
        result["details"]["formula_cells"] = formula_count
        result["details"]["formula_cells_without_cached_values"] = missing_cache
        if missing_cache:
            result["warnings"].append("Recalculate in Excel or a supported calculation engine; formula results are unverified")
        result["warnings"].append("Check print layout, currencies, FX direction, room mix and totals against the source")
    finally:
        formulas.close()
        cached.close()


def check_video(path: Path, result: dict) -> None:
    import shutil
    probe = shutil.which("ffprobe")
    if not probe:
        result["warnings"].append("ffprobe missing: video duration and tracks not checked")
        return
    proc = subprocess.run([probe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path.resolve())],
                          capture_output=True, text=True, timeout=30)
    if proc.returncode:
        result["errors"].append("ffprobe could not decode the container")
        return
    metadata = json.loads(proc.stdout)
    streams = metadata.get("streams", [])
    kinds = [stream.get("codec_type") for stream in streams]
    result["details"] = {"duration_seconds": metadata.get("format", {}).get("duration"), "tracks": kinds}
    if "video" not in kinds:
        result["errors"].append("No video track")
    result["warnings"].append("Play beginning, middle and ending; listen to audio and inspect subtitle timing")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    results = [check_file(path) for path in args.files]
    output = json.dumps({"files": results, "note": "PASS covers automated checks only; REVIEW requires the stated manual checks."},
                        ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 1 if any(item["errors"] for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
