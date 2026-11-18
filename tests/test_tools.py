from __future__ import annotations

import copy
import json
import importlib.util
import subprocess
import sys
import tempfile
import unittest
import zipfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from tools.quote import calculate
from tools.check_deliverables import check_file

ROOT = Path(__file__).resolve().parents[1]


class QuoteTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "examples/quote.json").read_text(encoding="utf-8"))

    def test_mixed_rooms_fx_and_margin(self):
        result = calculate(self.data)
        self.assertEqual(result["rooms"], {"twin": 1, "single": 2})
        self.assertEqual(result["nonhotel_cost_twd"], "25400.00")
        self.assertEqual(result["hotel_cost_twd"], "24000.00")
        self.assertEqual(result["total_cost_twd"], "49400.00")
        self.assertEqual(result["twin_quote_per_person_twd"], "13000.00")
        self.assertEqual(result["single_quote_per_person_twd"], "18000.00")
        self.assertEqual(result["single_room_supplement_twd"], "5000.00")
        self.assertEqual(result["total_revenue_twd"], "62000.00")
        self.assertEqual(result["gross_profit_twd"], "12600.00")
        self.assertGreaterEqual(Decimal(result["achieved_margin_percent"]), 20)

    def test_rate_direction(self):
        self.data["vnd_per_1000_twd"] = "1000000"
        self.assertEqual(calculate(self.data)["total_cost_twd"], "41600.00")

    def test_no_single_rooms(self):
        self.data["single_travelers"] = 0
        result = calculate(self.data)
        self.assertEqual(result["rooms"], {"twin": 2, "single": 0})
        self.assertEqual(result["total_cost_twd"], "41400.00")

    def test_all_single_rooms(self):
        self.data["single_travelers"] = 4
        result = calculate(self.data)
        self.assertEqual(result["hotel_cost_twd"], "32000.00")
        self.assertEqual(result["total_revenue_twd"], "72000.00")

    def test_different_single_room_rate(self):
        self.data["hotel"]["single_room_per_night"] = "1200000"
        self.assertEqual(calculate(self.data)["single_room_supplement_twd"], "2500.00")

    def test_zero_nights_and_zero_cost(self):
        self.data["nights"] = 0
        self.data["cost_lines"] = []
        result = calculate(self.data)
        self.assertEqual(result["total_cost_twd"], "0.00")
        self.assertEqual(result["achieved_margin_percent"], "0.00")

    def test_invalid_inputs(self):
        changes = [("travelers", 0), ("travelers", True), ("single_travelers", 1),
                   ("single_travelers", 6), ("margin_percent", "100"),
                   ("margin_percent", "-1"), ("vnd_per_1000_twd", "0"),
                   ("vnd_per_1000_twd", "NaN"), ("twd_per_usd", "Infinity"),
                   ("quote_round_to_twd", "0"), ("nights", 1.5)]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                invalid = copy.deepcopy(self.data)
                invalid[key] = value
                with self.assertRaises(ValueError):
                    calculate(invalid)

    def test_invalid_cost_currency_or_quantity(self):
        for key, value in [("currency", "EUR"), ("amount", "-1"), ("quantity", "0")]:
            with self.subTest(key=key):
                self.data["cost_lines"][0][key] = value
                with self.assertRaises(ValueError):
                    calculate(self.data)
                self.setUp()

    def test_quote_cli(self):
        proc = subprocess.run([sys.executable, str(ROOT / "tools/quote.py"), str(ROOT / "examples/quote.json")],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["total_cost_twd"], "49400.00")


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_missing_and_empty(self):
        self.assertEqual(check_file(self.root / "missing.json")["status"], "FAIL")
        path = self.root / "empty.json"
        path.touch()
        self.assertEqual(check_file(path)["status"], "FAIL")

    def test_json_validation_and_hash(self):
        path = self.root / "valid.json"
        path.write_text('{"price": 123}', encoding="utf-8")
        result = check_file(path)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(len(result["sha256"]), 64)
        path.write_text("not json", encoding="utf-8")
        self.assertEqual(check_file(path)["status"], "FAIL")

    def test_corrupt_zip_and_office_structure(self):
        path = self.root / "corrupt.zip"
        path.write_text("bad zip", encoding="utf-8")
        self.assertEqual(check_file(path)["status"], "FAIL")
        path = self.root / "fake.xlsx"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("hello.txt", "not an xlsx")
        self.assertEqual(check_file(path)["status"], "FAIL")

    def test_unknown_type_is_review(self):
        path = self.root / "note.txt"
        path.write_text("text", encoding="utf-8")
        self.assertEqual(check_file(path)["status"], "REVIEW")

    def test_video_missing_probe_is_review(self):
        path = self.root / "clip.mp4"
        path.write_bytes(b"uninspected container")
        with patch("shutil.which", return_value=None):
            result = check_file(path)
        self.assertEqual(result["status"], "REVIEW")
        self.assertIn("ffprobe missing", result["warnings"][0])

    def test_cli_failure_exit_code(self):
        proc = subprocess.run([sys.executable, str(ROOT / "tools/check_deliverables.py"), str(self.root / "missing.pdf")],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(json.loads(proc.stdout)["files"][0]["status"], "FAIL")

    @unittest.skipUnless(importlib.util.find_spec("openpyxl"), "optional openpyxl not installed")
    def test_xlsx_formula_cache_and_error(self):
        from openpyxl import Workbook
        path = self.root / "costs.xlsx"
        workbook = Workbook()
        workbook.active["A1"] = 800000
        workbook.active["B1"] = "=A1/1000"
        workbook.save(path)
        workbook.close()
        result = check_file(path)
        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(result["details"]["formula_cells_without_cached_values"], 1)
        workbook = Workbook()
        workbook.active["A1"] = "#DIV/0!"
        workbook.save(path)
        workbook.close()
        self.assertEqual(check_file(path)["status"], "FAIL")

    @unittest.skipUnless(importlib.util.find_spec("pypdf"), "optional pypdf not installed")
    def test_pdf_page_count(self):
        from pypdf import PdfWriter
        path = self.root / "one-page.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        with path.open("wb") as handle:
            writer.write(handle)
        result = check_file(path)
        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(result["details"]["pages"], 1)

    @unittest.skipUnless(importlib.util.find_spec("PIL"), "optional Pillow not installed")
    def test_image_dimensions_and_corruption(self):
        from PIL import Image
        path = self.root / "test.png"
        with Image.new("RGB", (1080, 1920), "white") as image:
            image.save(path)
        result = check_file(path)
        self.assertEqual(result["details"]["dimensions"], [1080, 1920])
        self.assertEqual(result["status"], "REVIEW")
        path.write_bytes(b"bad image")
        self.assertEqual(check_file(path)["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
