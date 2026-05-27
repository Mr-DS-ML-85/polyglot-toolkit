"""
Deep feature extraction for polyglot/malicious file detection.

Extracts ~310 features from raw bytes:
  - 256-dim normalized byte histogram
  - Shannon entropy (global + 16 per-chunk)
  - 25 magic-byte / structural signatures
  - 8 polyglot cross-type markers
  - 6 string-level statistics
  - 6 structural markers (zero-runs, entropy ratios)
  - PE / ELF / PDF header fields (6+6+6 = 18)
  - 2 meta features (size, header hash)

All features are deterministic, fast, and require no external parsers.
"""

import math, struct, hashlib
from typing import Dict, List, Optional
import numpy as np

# ── Magic-byte signatures ─────────────────────────────────────────────────────
MAGIC_SIGNATURES = {
    "pe":       [b"MZ"],
    "elf":      [b"\x7fELF"],
    "pdf":      [b"%PDF"],
    "zip":      [b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"],
    "rar":      [b"Rar!\x1a\x07"],
    "gz":       [b"\x1f\x8b"],
    "bz2":      [b"BZ"],
    "xz":       [b"\xfd7zXZ"],
    "7z":       [b"7z\xbc\xaf\x27\x1c"],
    "gif":      [b"GIF87a", b"GIF89a"],
    "png":      [b"\x89PNG"],
    "jpeg":     [b"\xff\xd8\xff"],
    "bmp":      [b"BM"],
    "ico":      [b"\x00\x00\x01\x00"],
    "rtf":      [b"{\\rtf"],
    "html":     [b"<html", b"<!DOCTYPE", b"<!doctype", b"<HTML"],
    "script":   [b"#!/", b"<?php", b"<%", b"<script"],
    "sqlite":   [b"SQLite format 3"],
    "macho":    [b"\xfe\xed\xfa", b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe"],
    "dex":      [b"dex\n"],
    "java_cls": [b"\xca\xfe\xba\xbe"],
    "ps":       [b"%!PS"],
    "svg":      [b"<svg"],
    "xml":      [b"<?xml"],
    "wasm":     [b"\x00asm"],
}

POLYGLOT_INDICATORS = {
    "pe_in_pdf":    (b"%PDF", b"MZ"),
    "pdf_in_pe":    (b"MZ", b"%PDF"),
    "elf_in_zip":   (b"PK\x03\x04", b"\x7fELF"),
    "pe_in_zip":    (b"PK\x03\x04", b"MZ"),
    "pe_in_html":   (b"<html", b"MZ"),
    "pdf_in_html":  (b"<html", b"%PDF"),
    "elf_in_pdf":   (b"%PDF", b"\x7fELF"),
    "script_in_pe": (b"MZ", b"<script"),
    # Cross-platform indicators
    "bash_in_media":     (b"\xff\xd8", b"#!/bin/bash"),
    "bash_in_png":       (b"\x89PNG", b"#!/bin/bash"),
    "sh_in_media":       (b"\xff\xd8", b"#!/bin/sh"),
    "python_in_media":   (b"\xff\xd8", b"#!/usr/bin/env python"),
    "applescript_in_media": (b"\xff\xd8", b"osascript"),
    "macho_in_media":    (b"\xff\xd8", b"\xfe\xed\xfa"),
    "macho_in_png":      (b"\x89PNG", b"\xfe\xed\xfa"),
    "macho_in_pdf":      (b"%PDF", b"\xfe\xed\xfa"),
    "dex_in_media":      (b"\xff\xd8", b"dex\n"),
    "javaclass_in_media": (b"\xff\xd8", b"\xca\xfe\xba\xbe"),
    "pe_in_gif":         (b"GIF8", b"MZ"),
    "elf_in_gif":        (b"GIF8", b"\x7fELF"),
    "vbs_in_media":      (b"\xff\xd8", b"CreateObject"),
    "ps1_in_media":      (b"\xff\xd8", b"powershell"),
    "hta_in_media":      (b"\xff\xd8", b"<hta:"),
    # lnk_in_media REMOVED — \x4c\x00\x00\x00 is too common in binaries
}

FEATURE_NAMES_CACHE: Optional[List[str]] = None


# ── Low-level helpers ─────────────────────────────────────────────────────────

def _shannon(data: bytes) -> float:
    if not data:
        return 0.0
    a = np.frombuffer(data, dtype=np.uint8)
    c = np.bincount(a, minlength=256).astype(np.float64)
    p = c / c.sum()
    p = p[p > 0]
    return float(-np.sum(p * np.log2(p)))


def _chunk_entropies(data: bytes, n: int) -> List[float]:
    if not data:
        return [0.0] * n
    sz = max(1, len(data) // n)
    return [_shannon(data[i * sz: (i + 1) * sz if i < n - 1 else len(data)])
            for i in range(n)]


def _byte_hist(data: bytes) -> np.ndarray:
    a = np.frombuffer(data, dtype=np.uint8)
    h = np.bincount(a, minlength=256).astype(np.float64)
    s = h.sum()
    return h / s if s > 0 else h


def _detect_types(data: bytes) -> Dict[str, bool]:
    return {ft: any(data.find(sig) != -1 for sig in sigs)
            for ft, sigs in MAGIC_SIGNATURES.items()}


def _detect_polyglots(data: bytes) -> Dict[str, bool]:
    out = {}
    for name, (primary, secondary) in POLYGLOT_INDICATORS.items():
        p = data.find(primary)
        out[name] = p != -1 and data.find(secondary, p + len(primary)) != -1
    return out


def _string_stats(data: bytes) -> Dict[str, float]:
    if not data:
        return dict.fromkeys(
            ["printable_ratio", "null_ratio", "high_byte_ratio",
             "avg_string_len", "max_string_len", "string_count"], 0.0)
    a = np.frombuffer(data, dtype=np.uint8)
    pr = float((((a >= 0x20) & (a <= 0x7e)) | (a == 9) | (a == 10) | (a == 13)).mean())
    nr = float((a == 0).mean())
    hr = float((a > 0x7f).mean())

    strings, cur = [], 0
    for b in data:
        if 0x20 <= b <= 0x7e:
            cur += 1
        else:
            if cur >= 4:
                strings.append(cur)
            cur = 0
    if cur >= 4:
        strings.append(cur)
    return {
        "printable_ratio": pr, "null_ratio": nr, "high_byte_ratio": hr,
        "avg_string_len": float(np.mean(strings)) if strings else 0.0,
        "max_string_len": float(max(strings)) if strings else 0.0,
        "string_count": float(len(strings)),
    }


def _structural(data: bytes) -> Dict[str, float]:
    if not data:
        return dict.fromkeys(
            ["max_zero_run", "max_ff_run", "header_entropy",
             "body_entropy", "header_body_ratio", "zero_run_ratio"], 0.0)
    a = np.frombuffer(data, dtype=np.uint8)
    mz = mf = cz = cf = zt = 0
    for b in a:
        cz = cz + 1 if b == 0 else 0
        cf = cf + 1 if b == 0xff else 0
        mz, mf = max(mz, cz), max(mf, cf)
        if b == 0:
            zt += 1
    he = _shannon(data[:1024])
    be = _shannon(data[1024:]) if len(data) > 1024 else 0.0
    return {
        "max_zero_run": float(mz), "max_ff_run": float(mf),
        "header_entropy": he, "body_entropy": be,
        "header_body_ratio": he / max(be, 1e-10),
        "zero_run_ratio": float(zt) / max(len(data), 1),
    }


def _pe_feats(data: bytes) -> Dict[str, float]:
    z = {"pe_valid_dos": 0, "pe_has_pe_sig": 0, "pe_machine": 0,
         "pe_sections": 0, "pe_optional_hdr_size": 0, "pe_characteristics": 0}
    try:
        if len(data) < 64 or data[:2] != b"MZ":
            return z
        z["pe_valid_dos"] = 1.0
        off = struct.unpack_from("<I", data, 60)[0]
        if off + 24 > len(data) or data[off:off + 4] != b"PE\x00\x00":
            return z
        z["pe_has_pe_sig"] = 1.0
        c = off + 4
        z["pe_machine"] = float(struct.unpack_from("<H", data, c)[0])
        z["pe_sections"] = float(struct.unpack_from("<H", data, c + 2)[0])
        z["pe_optional_hdr_size"] = float(struct.unpack_from("<H", data, c + 16)[0])
        z["pe_characteristics"] = float(struct.unpack_from("<H", data, c + 18)[0])
    except Exception:
        pass
    return z


def _elf_feats(data: bytes) -> Dict[str, float]:
    z = {"elf_class": 0, "elf_data": 0, "elf_type": 0,
         "elf_machine": 0, "elf_phoff": 0, "elf_shoff": 0}
    try:
        if len(data) < 16 or data[:4] != b"\x7fELF":
            return z
        cls_ = data[4]
        z["elf_class"] = float(cls_)
        z["elf_data"] = float(data[5])
        if cls_ == 1 and len(data) >= 36:
            z["elf_type"] = float(struct.unpack_from("<H", data, 16)[0])
            z["elf_machine"] = float(struct.unpack_from("<H", data, 18)[0])
            z["elf_phoff"] = float(min(struct.unpack_from("<I", data, 28)[0], 0xFFFF))
            z["elf_shoff"] = float(min(struct.unpack_from("<I", data, 32)[0], 0xFFFF))
        elif cls_ == 2 and len(data) >= 48:
            z["elf_type"] = float(struct.unpack_from("<H", data, 16)[0])
            z["elf_machine"] = float(struct.unpack_from("<H", data, 18)[0])
            z["elf_phoff"] = float(min(struct.unpack_from("<Q", data, 32)[0], 0xFFFF))
            z["elf_shoff"] = float(min(struct.unpack_from("<Q", data, 40)[0], 0xFFFF))
    except Exception:
        pass
    return z


def _pdf_feats(data: bytes) -> Dict[str, float]:
    z = {"pdf_obj_count": 0, "pdf_stream_count": 0, "pdf_xref_present": 0,
         "pdf_trailer_present": 0, "pdf_js_present": 0, "pdf_embedded_files": 0}
    try:
        t = data[:50000]
        z["pdf_obj_count"] = float(t.count(b" obj\n") + t.count(b" obj\r"))
        z["pdf_stream_count"] = float(t.count(b"stream\r\n") + t.count(b"stream\n"))
        z["pdf_xref_present"] = 1.0 if b"xref" in t else 0.0
        z["pdf_trailer_present"] = 1.0 if b"trailer" in t else 0.0
        lo = t.lower()
        z["pdf_js_present"] = 1.0 if (b"/javascript" in lo or b"/js " in lo) else 0.0
        z["pdf_embedded_files"] = float(lo.count(b"/embeddedfile"))
    except Exception:
        pass
    return z


# ── Public API ────────────────────────────────────────────────────────────────

def get_feature_names() -> List[str]:
    global FEATURE_NAMES_CACHE
    if FEATURE_NAMES_CACHE is not None:
        return FEATURE_NAMES_CACHE
    n = []
    n.extend(f"byte_{i:02x}" for i in range(256))
    n.append("global_entropy")
    n.extend(f"chunk_ent_{i}" for i in range(16))
    n.extend(f"has_{ft}" for ft in sorted(MAGIC_SIGNATURES))
    n.extend(f"poly_{m}" for m in sorted(POLYGLOT_INDICATORS))
    n.extend(["printable_ratio", "null_ratio", "high_byte_ratio",
              "avg_string_len", "max_string_len", "string_count"])
    n.extend(["max_zero_run", "max_ff_run", "header_entropy",
              "body_entropy", "header_body_ratio", "zero_run_ratio"])
    n.extend(["pe_valid_dos", "pe_has_pe_sig", "pe_machine",
              "pe_sections", "pe_optional_hdr_size", "pe_characteristics"])
    n.extend(["elf_class", "elf_data", "elf_type",
              "elf_machine", "elf_phoff", "elf_shoff"])
    n.extend(["pdf_obj_count", "pdf_stream_count", "pdf_xref_present",
              "pdf_trailer_present", "pdf_js_present", "pdf_embedded_files"])
    n.extend(["file_size_log", "header_hash_byte"])
    FEATURE_NAMES_CACHE = n
    return n


def extract_features(data: bytes, cfg: dict = None) -> np.ndarray:
    """Extract the full feature vector from raw file bytes → 1-D float64 array."""
    cfg = cfg or {}
    mx = cfg.get("max_file_size_mb", 100) * 1024 * 1024
    if len(data) > mx:
        data = data[:mx]
    nc = cfg.get("chunk_count", 16)
    f: list = []
    f.extend(_byte_hist(data).tolist())
    f.append(_shannon(data))
    f.extend(_chunk_entropies(data, nc))
    td = _detect_types(data)
    f.extend(1.0 if td.get(ft) else 0.0 for ft in sorted(MAGIC_SIGNATURES))
    pd = _detect_polyglots(data)
    f.extend(1.0 if pd.get(m) else 0.0 for m in sorted(POLYGLOT_INDICATORS))
    ss = _string_stats(data)
    f.extend(ss[k] for k in ["printable_ratio", "null_ratio", "high_byte_ratio",
                              "avg_string_len", "max_string_len", "string_count"])
    st = _structural(data)
    f.extend(st[k] for k in ["max_zero_run", "max_ff_run", "header_entropy",
                              "body_entropy", "header_body_ratio", "zero_run_ratio"])
    pe = _pe_feats(data)
    f.extend(pe[k] for k in ["pe_valid_dos", "pe_has_pe_sig", "pe_machine",
                              "pe_sections", "pe_optional_hdr_size", "pe_characteristics"])
    ef = _elf_feats(data)
    f.extend(ef[k] for k in ["elf_class", "elf_data", "elf_type",
                              "elf_machine", "elf_phoff", "elf_shoff"])
    pf = _pdf_feats(data)
    f.extend(pf[k] for k in ["pdf_obj_count", "pdf_stream_count", "pdf_xref_present",
                              "pdf_trailer_present", "pdf_js_present", "pdf_embedded_files"])
    f.append(math.log1p(len(data)))
    f.append(float(hashlib.sha256(data[:1024]).digest()[0]) / 255.0)
    return np.array(f, dtype=np.float64)


def extract_features_from_file(path: str, cfg: dict = None) -> np.ndarray:
    with open(path, "rb") as fh:
        return extract_features(fh.read(), cfg)


def analyze_file(path: str, cfg: dict = None) -> Dict:
    """Full analysis report for a single file."""
    with open(path, "rb") as fh:
        data = fh.read()
    feats = extract_features(data, cfg)
    td = _detect_types(data)
    pd = _detect_polyglots(data)
    types_found = [t for t, v in td.items() if v]
    polys_found = [m for m, v in pd.items() if v]
    return {
        "file": path, "size": len(data), "entropy": _shannon(data),
        "detected_types": types_found, "polyglot_markers": polys_found,
        "string_stats": _string_stats(data), "structural": _structural(data),
        "features": feats, "feature_names": get_feature_names(),
        "is_polyglot_candidate": len(types_found) > 1 or len(polys_found) > 0,
    }
