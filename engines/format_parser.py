"""
Comprehensive media format parser + differential analysis.

Supports ALL common video, audio, music, photo, and image formats.
Parser differential analysis: compares header claims vs actual content
to detect polyglots, malformed files, and evasion techniques.

Author: Mr-DS-ML-85
"""

import struct
import os
import math
import hashlib
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

logger = logging.getLogger("polyglot_shield.formats")


# ── Format Registry ──────────────────────────────────────────────────────────

@dataclass
class FormatInfo:
    """Parsed format information."""
    format_id: str
    format_name: str
    category: str  # image, video, audio, document, archive, executable
    mime_type: str
    extensions: List[str]
    magic_bytes: List[bytes]
    description: str
    max_header_size: int = 4096


# Complete format registry — ALL common media types
FORMAT_REGISTRY: Dict[str, FormatInfo] = {
    # ── Image Formats ──────────────────────────────────────────────
    "jpeg": FormatInfo("jpeg", "JPEG", "image", "image/jpeg",
        [".jpg", ".jpeg", ".jpe", ".jfif"],
        [b"\xff\xd8\xff"], "JPEG image", 20),
    "png": FormatInfo("png", "PNG", "image", "image/png",
        [".png"],
        [b"\x89PNG\r\n\x1a\n"], "PNG image", 8),
    "gif": FormatInfo("gif", "GIF", "image", "image/gif",
        [".gif"],
        [b"GIF87a", b"GIF89a"], "GIF image", 6),
    "bmp": FormatInfo("bmp", "BMP", "image", "image/bmp",
        [".bmp", ".dib"],
        [b"BM"], "Bitmap image", 2),
    "tiff": FormatInfo("tiff", "TIFF", "image", "image/tiff",
        [".tiff", ".tif"],
        [b"II\x2a\x00", b"MM\x00\x2a"], "TIFF image", 4),
    "webp": FormatInfo("webp", "WebP", "image", "image/webp",
        [".webp"],
        [b"RIFF"], "WebP image (RIFF container)", 12),
    "ico": FormatInfo("ico", "ICO", "image", "image/x-icon",
        [".ico", ".cur"],
        [b"\x00\x00\x01\x00", b"\x00\x00\x02\x00"], "Icon/Cursor", 4),
    "svg": FormatInfo("svg", "SVG", "image", "image/svg+xml",
        [".svg", ".svgz"],
        [b"<svg", b"<?xml"], "SVG vector image", 100),
    "psd": FormatInfo("psd", "PSD", "image", "image/vnd.adobe.photoshop",
        [".psd"],
        [b"8BPS"], "Photoshop document", 4),
    "raw": FormatInfo("raw", "RAW", "image", "image/x-raw",
        [".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2", ".raf", ".pef"],
        [b"II\x2a\x00", b"MM\x00\x2a"], "Camera RAW image", 4),
    "heic": FormatInfo("heic", "HEIC", "image", "image/heic",
        [".heic", ".heif", ".hif"],
        [b"\x00\x00\x00"], "HEIC/HEIF image (HEVC)", 12),
    "avif": FormatInfo("avif", "AVIF", "image", "image/avif",
        [".avif"],
        [b"\x00\x00\x00"], "AV1 image format", 12),
    "jxl": FormatInfo("jxl", "JPEG XL", "image", "image/jxl",
        [".jxl"],
        [b"\xff\x0a", b"\x00\x00\x00\x0cJXL"], "JPEG XL image", 12),
    "pcx": FormatInfo("pcx", "PCX", "image", "image/x-pcx",
        [".pcx"],
        [b"\x0a"], "PCX image", 1),
    "tga": FormatInfo("tga", "TGA", "image", "image/x-tga",
        [".tga"],
        [], "Targa image (no magic)", 18),
    "dds": FormatInfo("dds", "DDS", "image", "image/vnd-ms.dds",
        [".dds"],
        [b"DDS "], "DirectDraw Surface", 4),
    "exr": FormatInfo("exr", "EXR", "image", "image/x-exr",
        [".exr"],
        [b"\x76\x2f\x31\x01"], "OpenEXR image", 4),
    "pgm": FormatInfo("pgm", "PGM", "image", "image/x-portable-graymap",
        [".pgm"],
        [b"P5", b"P2"], "Portable Graymap", 2),
    "ppm": FormatInfo("ppm", "PPM", "image", "image/x-portable-pixmap",
        [".ppm"],
        [b"P6", b"P3"], "Portable Pixmap", 2),
    "pbm": FormatInfo("pbm", "PBM", "image", "image/x-portable-bitmap",
        [".pbm"],
        [b"P4", b"P1"], "Portable Bitmap", 2),
    "hdr": FormatInfo("hdr", "HDR", "image", "image/vnd.radiance",
        [".hdr", ".rgbe"],
        [b"#?RADIANCE", b"#?RGBE"], "Radiance HDR", 16),
    "sgi": FormatInfo("sgi", "SGI", "image", "image/sgi",
        [".sgi", ".rgb", ".rgba", ".bw"],
        [b"\x01\xda"], "SGI image", 2),
    "cin": FormatInfo("cin", "CIN", "image", "image/x-cineon",
        [".cin", ".dpx"],
        [b"\x80\x2a\x5f\xd7"], "Cineon/DPX image", 4),

    # ── Video Formats ──────────────────────────────────────────────
    "mp4": FormatInfo("mp4", "MP4", "video", "video/mp4",
        [".mp4", ".m4v", ".m4p", ".m4b"],
        [b"\x00\x00\x00"], "MPEG-4 Part 14", 12),
    "avi": FormatInfo("avi", "AVI", "video", "video/x-msvideo",
        [".avi"],
        [b"RIFF"], "AVI video (RIFF container)", 12),
    "mkv": FormatInfo("mkv", "MKV", "video", "video/x-matroska",
        [".mkv", ".webm", ".mka", ".mks"],
        [b"\x1a\x45\xdf\xa3"], "Matroska/WebM video", 4),
    "mov": FormatInfo("mov", "MOV", "video", "video/quicktime",
        [".mov", ".qt"],
        [b"\x00\x00\x00"], "QuickTime MOV", 12),
    "wmv": FormatInfo("wmv", "WMV", "video", "video/x-ms-wmv",
        [".wmv", ".asf"],
        [b"\x30\x26\xb2\x75\x8e\x66\xcf\x11"], "Windows Media Video (ASF)", 16),
    "flv": FormatInfo("flv", "FLV", "video", "video/x-flv",
        [".flv"],
        [b"FLV"], "Flash Video", 3),
    "webm": FormatInfo("webm", "WebM", "video", "video/webm",
        [".webm"],
        [b"\x1a\x45\xdf\xa3"], "WebM video", 4),
    "ts": FormatInfo("ts", "MPEG-TS", "video", "video/mp2t",
        [".ts", ".mts", ".m2ts"],
        [b"\x47"], "MPEG Transport Stream", 1),
    "mpg": FormatInfo("mpg", "MPEG-PS", "video", "video/mpeg",
        [".mpg", ".mpeg", ".vob"],
        [b"\x00\x00\x01\xba", b"\x00\x00\x01\xb3"], "MPEG Program Stream", 4),
    "3gp": FormatInfo("3gp", "3GP", "video", "video/3gpp",
        [".3gp", ".3g2"],
        [b"\x00\x00\x00"], "3GPP video", 12),
    "ogv": FormatInfo("ogv", "OGV", "video", "video/ogg",
        [".ogv", ".ogm"],
        [b"OggS"], "Ogg video", 4),
    "rm": FormatInfo("rm", "RealMedia", "video", "application/vnd.rn-realmedia",
        [".rm", ".rmvb"],
        [b".RMF"], "RealMedia video", 4),
    "f4v": FormatInfo("f4v", "F4V", "video", "video/x-f4v",
        [".f4v"],
        [b"\x00\x00\x00"], "Flash F4V video", 12),
    "mxf": FormatInfo("mxf", "MXF", "video", "application/mxf",
        [".mxf"],
        [b"\x06\x0e\x2b\x34"], "Material Exchange Format", 4),
    "divx": FormatInfo("divx", "DIVX", "video", "video/divx",
        [".divx", ".div"],
        [b"RIFF"], "DivX video (AVI)", 12),

    # ── Audio/Music Formats ────────────────────────────────────────
    "mp3": FormatInfo("mp3", "MP3", "audio", "audio/mpeg",
        [".mp3"],
        [b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"ID3"], "MPEG Audio Layer III", 4),
    "flac": FormatInfo("flac", "FLAC", "audio", "audio/flac",
        [".flac"],
        [b"fLaC"], "Free Lossless Audio Codec", 4),
    "wav": FormatInfo("wav", "WAV", "audio", "audio/wav",
        [".wav"],
        [b"RIFF"], "Waveform Audio (RIFF)", 12),
    "ogg": FormatInfo("ogg", "OGG", "audio", "audio/ogg",
        [".ogg", ".oga", ".opus"],
        [b"OggS"], "Ogg Vorbis/Opus audio", 4),
    "aac": FormatInfo("aac", "AAC", "audio", "audio/aac",
        [".aac", ".adts", ".m4a"],
        [b"\xff\xf1", b"\xff\xf9", b"\x00\x00\x00"], "Advanced Audio Coding", 4),
    "wma": FormatInfo("wma", "WMA", "audio", "audio/x-ms-wma",
        [".wma"],
        [b"\x30\x26\xb2\x75\x8e\x66\xcf\x11"], "Windows Media Audio (ASF)", 16),
    "mid": FormatInfo("mid", "MIDI", "audio", "audio/midi",
        [".mid", ".midi", ".kar"],
        [b"MThd"], "MIDI audio", 4),
    "aiff": FormatInfo("aiff", "AIFF", "audio", "audio/aiff",
        [".aiff", ".aif", ".aifc"],
        [b"FORM"], "Audio Interchange File Format", 4),
    "ape": FormatInfo("ape", "APE", "audio", "audio/ape",
        [".ape"],
        [b"MAC "], "Monkey's Audio", 4),
    "wv": FormatInfo("wv", "WavPack", "audio", "audio/wavpack",
        [".wv"],
        [b"wvpk"], "WavPack audio", 4),
    "dsf": FormatInfo("dsf", "DSF", "audio", "audio/dsf",
        [".dsf"],
        [b"DSD "], "DSD Stream File", 4),
    "dff": FormatInfo("dff", "DFF", "audio", "audio/dff",
        [".dff"],
        [b"FRM8"], "DSD Interchange Format", 4),
    "mka": FormatInfo("mka", "MKA", "audio", "audio/x-matroska",
        [".mka"],
        [b"\x1a\x45\xdf\xa3"], "Matroska Audio", 4),
    "au": FormatInfo("au", "AU", "audio", "audio/basic",
        [".au", ".snd"],
        [b".snd"], "Sun/NeXT audio", 4),
    "ra": FormatInfo("ra", "RA", "audio", "audio/vnd.rn-realaudio",
        [".ra", ".ram"],
        [b".ra\xfd"], "RealAudio", 4),
    "ac3": FormatInfo("ac3", "AC3", "audio", "audio/ac3",
        [".ac3", ".eac3"],
        [b"\x0b\x77"], "Dolby Digital AC-3", 2),
    "dts": FormatInfo("dts", "DTS", "audio", "audio/dts",
        [".dts", ".dtshd"],
        [b"\x7f\xfe\x80\x01"], "DTS audio", 4),
    "xm": FormatInfo("xm", "XM", "audio", "audio/xm",
        [".xm"],
        [b"Extended Module:"], "FastTracker II module", 17),
    "s3m": FormatInfo("s3m", "S3M", "audio", "audio/s3m",
        [".s3m"],
        [b"SCRM"], "ScreamTracker III module", 4),
    "it": FormatInfo("it", "IT", "audio", "audio/it",
        [".it"],
        [b"IMPM"], "Impulse Tracker module", 4),
    "mod": FormatInfo("mod", "MOD", "audio", "audio/mod",
        [".mod"],
        [], "Amiga module (no fixed magic)", 1084),

    # ── Document Formats ───────────────────────────────────────────
    "pdf": FormatInfo("pdf", "PDF", "document", "application/pdf",
        [".pdf"],
        [b"%PDF"], "Portable Document Format", 5),
    "docx": FormatInfo("docx", "DOCX", "document",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        [".docx"],
        [b"PK\x03\x04"], "Office Open XML Document", 4),
    "xlsx": FormatInfo("xlsx", "XLSX", "document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        [".xlsx", ".xlsm"],
        [b"PK\x03\x04"], "Office Open XML Spreadsheet", 4),
    "pptx": FormatInfo("pptx", "PPTX", "document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        [".pptx", ".pptm"],
        [b"PK\x03\x04"], "Office Open XML Presentation", 4),
    "doc": FormatInfo("doc", "DOC", "document", "application/msword",
        [".doc"],
        [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"], "MS Word 97-2003 (OLE2)", 8),
    "xls": FormatInfo("xls", "XLS", "document", "application/vnd.ms-excel",
        [".xls", ".xlm"],
        [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"], "MS Excel 97-2003 (OLE2)", 8),
    "ppt": FormatInfo("ppt", "PPT", "document", "application/vnd.ms-powerpoint",
        [".ppt"],
        [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"], "MS PowerPoint 97-2003 (OLE2)", 8),
    "rtf": FormatInfo("rtf", "RTF", "document", "application/rtf",
        [".rtf"],
        [b"{\\rtf"], "Rich Text Format", 5),
    "odt": FormatInfo("odt", "ODT", "document", "application/vnd.oasis.opendocument.text",
        [".odt"],
        [b"PK\x03\x04"], "OpenDocument Text", 4),
    "ods": FormatInfo("ods", "ODS", "document",
        "application/vnd.oasis.opendocument.spreadsheet",
        [".ods"],
        [b"PK\x03\x04"], "OpenDocument Spreadsheet", 4),
    "epub": FormatInfo("epub", "EPUB", "document", "application/epub+zip",
        [".epub"],
        [b"PK\x03\x04"], "Electronic Publication", 4),
    "html": FormatInfo("html", "HTML", "document", "text/html",
        [".html", ".htm", ".xhtml"],
        [b"<!DOCTYPE", b"<!doctype", b"<html", b"<HTML", b"<?xml"], "HTML document", 100),
    "xml": FormatInfo("xml", "XML", "document", "application/xml",
        [".xml", ".xsd", ".xsl"],
        [b"<?xml"], "XML document", 100),
    "csv": FormatInfo("csv", "CSV", "document", "text/csv",
        [".csv"],
        [], "Comma-Separated Values (no magic)", 0),
    "latex": FormatInfo("latex", "LaTeX", "document", "application/x-latex",
        [".tex", ".latex", ".sty", ".cls"],
        [b"\\documentclass", b"\\begin"], "LaTeX document", 100),
    "djvu": FormatInfo("djvu", "DJVU", "document", "image/vnd.djvu",
        [".djvu", ".djv"],
        [b"AT&TFORM"], "DjVu document", 4),

    # ── Archive Formats ────────────────────────────────────────────
    "zip": FormatInfo("zip", "ZIP", "archive", "application/zip",
        [".zip", ".zipx", ".jar", ".war", ".ear", ".apk", ".ipa"],
        [b"PK\x03\x04", b"PK\x05\x06"], "ZIP archive", 4),
    "rar": FormatInfo("rar", "RAR", "archive", "application/vnd.rar",
        [".rar"],
        [b"Rar!\x1a\x07"], "RAR archive", 7),
    "7z": FormatInfo("7z", "7-Zip", "archive", "application/x-7z-compressed",
        [".7z"],
        [b"7z\xbc\xaf\x27\x1c"], "7-Zip archive", 6),
    "gz": FormatInfo("gz", "GZIP", "archive", "application/gzip",
        [".gz", ".tgz"],
        [b"\x1f\x8b"], "GZIP archive", 2),
    "bz2": FormatInfo("bz2", "BZIP2", "archive", "application/x-bzip2",
        [".bz2", ".tbz2"],
        [b"BZ"], "BZIP2 archive", 2),
    "xz": FormatInfo("xz", "XZ", "archive", "application/x-xz",
        [".xz", ".txz"],
        [b"\xfd7zXZ"], "XZ archive", 6),
    "lz4": FormatInfo("lz4", "LZ4", "archive", "application/x-lz4",
        [".lz4"],
        [b"\x04\x22\x4d\x18"], "LZ4 archive", 4),
    "zst": FormatInfo("zst", "Zstandard", "archive", "application/zstd",
        [".zst"],
        [b"\x28\xb5\x2f\xfd"], "Zstandard archive", 4),
    "tar": FormatInfo("tar", "TAR", "archive", "application/x-tar",
        [".tar", ".tar.gz", ".tar.bz2", ".tar.xz"],
        [], "TAR archive (257-byte magic at offset 257)", 263),
    "cab": FormatInfo("cab", "CAB", "archive", "application/vnd.ms-cab-compressed",
        [".cab"],
        [b"MSCF"], "Windows Cabinet", 4),
    "iso": FormatInfo("iso", "ISO", "archive", "application/x-iso9660-image",
        [".iso", ".img"],
        [b"\x01CD001", b"CD001"], "ISO 9660 image", 6),
    "dmg": FormatInfo("dmg", "DMG", "archive", "application/x-apple-diskimage",
        [".dmg"],
        [b"\x78\x01", b"koly"], "Apple Disk Image", 4),
    "lzh": FormatInfo("lzh", "LZH", "archive", "application/x-lzh-compressed",
        [".lzh", ".lha"],
        [b"-lh"], "LZH archive", 3),
    "z": FormatInfo("z", "Z", "archive", "application/x-compress",
        [".Z"],
        [b"\x1f\x9d", b"\x1f\xa0"], "Unix compress", 2),
    "lzma": FormatInfo("lzma", "LZMA", "archive", "application/x-lzma",
        [".lzma"],
        [b"\x5d\x00\x00"], "LZMA archive", 3),

    # ── Executable Formats ─────────────────────────────────────────
    "pe": FormatInfo("pe", "PE", "executable", "application/x-msdownload",
        [".exe", ".dll", ".sys", ".scr", ".ocx"],
        [b"MZ"], "Windows PE executable", 2),
    "elf": FormatInfo("elf", "ELF", "executable", "application/x-elf",
        [".elf", ".so", ".o", ".bin"],
        [b"\x7fELF"], "Linux ELF executable", 4),
    "macho": FormatInfo("macho", "Mach-O", "executable", "application/x-mach-binary",
        [".dylib", ".bundle", ".kext"],
        [b"\xfe\xed\xfa", b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe",
         b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe\xcf\xfa\xed\xfe"],
        "macOS Mach-O executable", 4),
    "java_cls": FormatInfo("java_cls", "Java Class", "executable",
        "application/java-vm",
        [".class"],
        [b"\xca\xfe\xba\xbe"], "Java class file", 4),
    "dex": FormatInfo("dex", "DEX", "executable", "application/x-android-dex",
        [".dex", ".odex"],
        [b"dex\n"], "Android DEX bytecode", 4),
    "wasm": FormatInfo("wasm", "WASM", "executable", "application/wasm",
        [".wasm"],
        [b"\x00asm"], "WebAssembly module", 4),
    "lnk": FormatInfo("lnk", "LNK", "executable", "application/x-ms-shortcut",
        [".lnk"],
        [b"\x4c\x00\x00\x00"], "Windows Shortcut", 4),
    "msi": FormatInfo("msi", "MSI", "executable", "application/x-msi",
        [".msi"],
        [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"], "Windows Installer (OLE2)", 8),
    "appx": FormatInfo("appx", "APPX", "executable", "application/x-appx",
        [".appx", ".msix"],
        [b"PK\x03\x04"], "Windows App Package", 4),
    "ko": FormatInfo("ko", "Kernel Module", "executable", "application/x-object",
        [".ko"],
        [b"\x7fELF"], "Linux kernel module", 4),

    # ── Script/Markup Formats ──────────────────────────────────────
    "ps": FormatInfo("ps", "PostScript", "document", "application/postscript",
        [".ps", ".eps", ".ai"],
        [b"%!PS", b"\xc5\xd0\xd3\xc6"], "PostScript/EPS", 4),
    "swf": FormatInfo("swf", "SWF", "executable", "application/x-shockwave-flash",
        [".swf"],
        [b"FWS", b"CWS", b"ZWS"], "Shockwave Flash", 3),
    "torrent": FormatInfo("torrent", "Torrent", "document", "application/x-bittorrent",
        [".torrent"],
        [b"d8:announce"], "BitTorrent file", 11),
    "sqlite": FormatInfo("sqlite", "SQLite", "document", "application/x-sqlite3",
        [".sqlite", ".sqlite3", ".db"],
        [b"SQLite format 3"], "SQLite database", 16),
}


# ── Parser Differential Analysis ─────────────────────────────────────────────

@dataclass
class DifferentialResult:
    """Result of parser differential analysis."""
    format_id: str
    declared_format: Optional[str]  # From extension
    detected_format: Optional[str]  # From magic bytes
    header_claims: Dict[str, Any]   # What the header says
    actual_content: Dict[str, Any]  # What's really there
    mismatches: List[str]           # Discrepancies
    anomalies: List[str]            # Suspicious findings
    risk_score: float               # 0.0-1.0
    details: Dict[str, Any] = field(default_factory=dict)


class FormatParser:
    """Comprehensive format parser with differential analysis."""

    def __init__(self):
        self.formats = FORMAT_REGISTRY
        # Build extension → format_id lookup
        self._ext_map: Dict[str, str] = {}
        for fid, finfo in self.formats.items():
            for ext in finfo.extensions:
                self._ext_map[ext.lower()] = fid

    def identify_by_magic(self, data: bytes) -> List[Tuple[str, float]]:
        """Identify format by magic bytes. Returns list of (format_id, confidence)."""
        if not data:
            return []
        results = []
        for fid, finfo in self.formats.items():
            for magic in finfo.magic_bytes:
                if not magic:
                    continue
                # Check at offset 0
                if data[:len(magic)] == magic:
                    results.append((fid, 1.0))
                    break
                # For RIFF-based formats, check sub-type
                if magic == b"RIFF" and data[:4] == b"RIFF":
                    if len(data) >= 12:
                        sub = data[8:12]
                        if fid == "webp" and sub == b"WEBP":
                            results.append((fid, 1.0))
                            break
                        elif fid == "avi" and sub == b"AVI ":
                            results.append((fid, 1.0))
                            break
                        elif fid == "wav" and sub == b"WAVE":
                            results.append((fid, 1.0))
                            break
                        elif fid == "aiff" and sub in (b"AIFF", b"AIFC"):
                            results.append((fid, 1.0))
                            break
        # Sort by confidence
        results.sort(key=lambda x: -x[1])
        return results

    def identify_by_extension(self, filepath: str) -> Optional[str]:
        """Identify format by file extension."""
        ext = os.path.splitext(filepath)[1].lower()
        return self._ext_map.get(ext)

    def parse_header(self, data: bytes, format_id: str) -> Dict[str, Any]:
        """Parse format-specific header fields."""
        if not data or format_id not in self.formats:
            return {}

        info = self.formats[format_id]
        header: Dict[str, Any] = {"format": format_id, "size": len(data)}

        try:
            if format_id == "png":
                header.update(self._parse_png_header(data))
            elif format_id in ("jpeg",):
                header.update(self._parse_jpeg_header(data))
            elif format_id == "gif":
                header.update(self._parse_gif_header(data))
            elif format_id == "bmp":
                header.update(self._parse_bmp_header(data))
            elif format_id == "tiff":
                header.update(self._parse_tiff_header(data))
            elif format_id in ("mp4", "mov", "3gp", "f4v", "heic", "avif"):
                header.update(self._parse_mp4_header(data))
            elif format_id in ("mkv", "webm"):
                header.update(self._parse_matroska_header(data))
            elif format_id == "avi":
                header.update(self._parse_avi_header(data))
            elif format_id == "flv":
                header.update(self._parse_flv_header(data))
            elif format_id in ("mp3",):
                header.update(self._parse_mp3_header(data))
            elif format_id == "flac":
                header.update(self._parse_flac_header(data))
            elif format_id == "wav":
                header.update(self._parse_wav_header(data))
            elif format_id in ("ogg", "ogv", "oga", "opus"):
                header.update(self._parse_ogg_header(data))
            elif format_id == "mid":
                header.update(self._parse_midi_header(data))
            elif format_id == "pdf":
                header.update(self._parse_pdf_header(data))
            elif format_id in ("zip", "docx", "xlsx", "pptx", "apk", "jar", "odt", "ods", "epub", "appx"):
                header.update(self._parse_zip_header(data))
            elif format_id in ("rar",):
                header.update(self._parse_rar_header(data))
            elif format_id == "7z":
                header.update(self._parse_7z_header(data))
            elif format_id == "gz":
                header.update(self._parse_gz_header(data))
            elif format_id == "pe":
                header.update(self._parse_pe_header(data))
            elif format_id == "elf":
                header.update(self._parse_elf_header(data))
            elif format_id == "macho":
                header.update(self._parse_macho_header(data))
            elif format_id in ("doc", "xls", "ppt", "msi"):
                header.update(self._parse_ole2_header(data))
            elif format_id == "sqlite":
                header.update(self._parse_sqlite_header(data))
        except Exception as e:
            header["parse_error"] = str(e)

        return header

    def differential_analysis(self, filepath: str) -> DifferentialResult:
        """Full parser differential analysis — compare extension vs content."""
        with open(filepath, "rb") as f:
            data = f.read(65536)  # Read first 64KB

        ext = os.path.splitext(filepath)[1].lower()
        full_ext = os.path.splitext(filepath)[1].lower()

        # 1. Identify by extension
        declared = self._ext_map.get(ext)

        # 2. Identify by magic bytes
        magic_ids = self.identify_by_magic(data)
        detected = magic_ids[0][0] if magic_ids else None

        # 3. Parse header with detected format
        header_claims = self.parse_header(data, detected or declared or "unknown") \
            if (detected or declared) else {}

        # 4. Detect mismatches
        mismatches = []
        anomalies = []
        risk = 0.0

        if declared and detected and declared != detected:
            # Check if they're in the same container family
            declared_info = self.formats.get(declared)
            detected_info = self.formats.get(detected)
            if declared_info and detected_info:
                if declared_info.category != detected_info.category:
                    mismatches.append(
                        f"Extension claims {declared_info.category} ({declared}), "
                        f"content is {detected_info.category} ({detected})")
                    risk += 0.5
                elif declared != detected:
                    # Same category but different format
                    mismatches.append(
                        f"Extension={declared}, Magic={detected}")
                    risk += 0.3

        # 5. Check for multiple format signatures
        all_formats = self.identify_by_magic(data)
        if len(all_formats) > 1:
            names = [f[0] for f in all_formats]
            anomalies.append(f"Multiple format signatures: {', '.join(names)}")
            risk += 0.3

        # 6. Check for polyglot markers
        polyglot_markers = self._find_polyglot_markers(data)
        if polyglot_markers:
            anomalies.extend(polyglot_markers)
            risk += 0.2 * len(polyglot_markers)

        # 7. Entropy analysis
        entropy = self._shannon(data)
        if entropy > 7.5:
            anomalies.append(f"Very high entropy ({entropy:.2f}) — possible encryption/compression")
            risk += 0.1

        # 8. Check for trailing data beyond expected format end
        trailing = self._check_trailing(data, detected or declared)
        if trailing:
            anomalies.append(trailing)
            risk += 0.2

        # 9. Actual content analysis
        actual_content = {
            "entropy": entropy,
            "size": len(data),
            "magic_formats": [f[0] for f in magic_ids],
            "null_byte_ratio": sum(1 for b in data if b == 0) / max(len(data), 1),
            "high_byte_ratio": sum(1 for b in data if b > 0x7f) / max(len(data), 1),
        }

        # 10. Header claims vs actual
        if "width" in header_claims and "height" in header_claims:
            w = header_claims.get("width", 0)
            h = header_claims.get("height", 0)
            if w > 0 and h > 0:
                expected_size = w * h * 3  # rough RGB estimate
                if len(data) > expected_size * 3:
                    anomalies.append(
                        f"File much larger than expected for {w}x{h} image "
                        f"({len(data):,} vs ~{expected_size:,} expected)")
                    risk += 0.2

        return DifferentialResult(
            format_id=detected or declared or "unknown",
            declared_format=declared,
            detected_format=detected,
            header_claims=header_claims,
            actual_content=actual_content,
            mismatches=mismatches,
            anomalies=anomalies,
            risk_score=min(risk, 1.0),
            details={"magic_matches": all_formats},
        )

    def scan_directory(self, directory: str) -> List[DifferentialResult]:
        """Scan all files in a directory for format anomalies."""
        results = []
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    result = self.differential_analysis(fpath)
                    if result.mismatches or result.anomalies or result.risk_score > 0.1:
                        results.append(result)
                except Exception:
                    pass
        return results

    # ── Format-Specific Parsers ────────────────────────────────────

    def _parse_png_header(self, data: bytes) -> Dict:
        if len(data) < 25:
            return {}
        # IHDR chunk at offset 8
        w = struct.unpack(">I", data[16:20])[0]
        h = struct.unpack(">I", data[20:24])[0]
        bit_depth = data[24]
        color_type = data[25]
        ct_names = {0: "Grayscale", 2: "RGB", 3: "Indexed", 4: "Grayscale+Alpha", 6: "RGBA"}
        return {"width": w, "height": h, "bit_depth": bit_depth,
                "color_type": ct_names.get(color_type, f"Unknown({color_type})"),
                "interlace": data[28] if len(data) > 28 else 0}

    def _parse_jpeg_header(self, data: bytes) -> Dict:
        result = {}
        # Parse JPEG markers
        i = 2
        while i < len(data) - 1:
            if data[i] != 0xff:
                break
            marker = data[i+1]
            if marker == 0xe0:  # APP0 (JFIF)
                result["jfif"] = True
            elif marker == 0xe1:  # APP1 (EXIF)
                result["exif"] = True
            elif marker == 0xdb:  # DQT
                result["dqt"] = True
            elif marker == 0xc0:  # SOF0 (baseline)
                if i + 9 < len(data):
                    h = struct.unpack(">H", data[i+5:i+7])[0]
                    w = struct.unpack(">H", data[i+7:i+9])[0]
                    result["width"] = w
                    result["height"] = h
                    result["encoding"] = "baseline"
                break
            elif marker == 0xc2:  # SOF2 (progressive)
                if i + 9 < len(data):
                    h = struct.unpack(">H", data[i+5:i+7])[0]
                    w = struct.unpack(">H", data[i+7:i+9])[0]
                    result["width"] = w
                    result["height"] = h
                    result["encoding"] = "progressive"
                break
            elif marker == 0xda:  # SOS — stop
                break
            if i + 3 < len(data):
                length = struct.unpack(">H", data[i+2:i+4])[0]
                i += 2 + length
            else:
                break
        return result

    def _parse_gif_header(self, data: bytes) -> Dict:
        if len(data) < 13:
            return {}
        w = struct.unpack("<H", data[6:8])[0]
        h = struct.unpack("<H", data[8:10])[0]
        flags = data[10]
        return {"width": w, "height": h, "version": data[:6].decode('ascii', errors='replace'),
                "color_resolution": ((flags >> 4) & 7) + 1,
                "has_gct": bool(flags & 0x80),
                "gct_size": 2 ** ((flags & 7) + 1) if flags & 0x80 else 0}

    def _parse_bmp_header(self, data: bytes) -> Dict:
        if len(data) < 26:
            return {}
        w = struct.unpack("<i", data[18:22])[0]
        h = abs(struct.unpack("<i", data[22:26])[0])
        bpp = struct.unpack("<H", data[28:30])[0]
        return {"width": w, "height": h, "bpp": bpp}

    def _parse_tiff_header(self, data: bytes) -> Dict:
        if len(data) < 8:
            return {}
        endian = "II" if data[:2] == b"II" else "MM"
        return {"byte_order": endian}

    def _parse_mp4_header(self, data: bytes) -> Dict:
        result = {}
        offset = 0
        atoms_found = []
        while offset + 8 <= len(data) and offset < 4096:
            try:
                size = struct.unpack(">I", data[offset:offset+4])[0]
                atom_type = data[offset+4:offset+8]
                if size < 8:
                    break
                atoms_found.append(atom_type.decode('ascii', errors='replace'))
                if atom_type == b"ftyp":
                    brand = data[offset+8:offset+12].decode('ascii', errors='replace')
                    result["ftyp_brand"] = brand
                    if offset + 16 <= len(data):
                        result["ftyp_version"] = data[offset+12:offset+16].hex()
                elif atom_type == b"mvhd" and size >= 20:
                    version = data[offset+8]
                    result["mvhd_version"] = version
                offset += size
            except Exception:
                break
        result["top_atoms"] = atoms_found[:20]
        return result

    def _parse_matroska_header(self, data: bytes) -> Dict:
        result = {}
        if len(data) >= 5 and data[0] == 0x1a:
            # EBML header
            vint_len = data[4] & 0x0f
            result["ebml"] = True
            if len(data) > 40:
                # Try to find DocType
                idx = data.find(b"\x42\x82")
                if idx != -1 and idx + 10 < len(data):
                    doctype_len = data[idx + 2] & 0x7f
                    if doctype_len < 20:
                        doctype = data[idx+3:idx+3+doctype_len]
                        result["doctype"] = doctype.decode('ascii', errors='replace').strip('\x00')
        return result

    def _parse_avi_header(self, data: bytes) -> Dict:
        if len(data) < 12:
            return {}
        return {"riff_size": struct.unpack("<I", data[4:8])[0],
                "form_type": data[8:12].decode('ascii', errors='replace')}

    def _parse_flv_header(self, data: bytes) -> Dict:
        if len(data) < 9:
            return {}
        version = data[3]
        flags = data[4]
        return {"version": version, "has_video": bool(flags & 1),
                "has_audio": bool(flags & 4)}

    def _parse_mp3_header(self, data: bytes) -> Dict:
        result = {}
        # Check for ID3v2 tag
        if data[:3] == b"ID3":
            version = f"2.{data[3]}.{data[4]}"
            size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
            result["id3v2"] = {"version": version, "tag_size": size}
            # Skip ID3 tag to find frame
            offset = 10 + size
        else:
            offset = 0
        # Find sync frame
        for i in range(offset, min(offset + 4096, len(data) - 4)):
            if data[i] == 0xff and (data[i+1] & 0xe0) == 0xe0:
                header = struct.unpack(">I", data[i:i+4])[0]
                version = (header >> 19) & 3
                layer = (header >> 17) & 3
                bitrate_idx = (header >> 12) & 0xf
                sample_idx = (header >> 10) & 3
                result["mpeg_version"] = {0: "2.5", 2: "2", 3: "1"}.get(version, "?")
                result["layer"] = {1: "III", 2: "II", 3: "I"}.get(layer, "?")
                result["frame_offset"] = i
                break
        return result

    def _parse_flac_header(self, data: bytes) -> Dict:
        if len(data) < 18:
            return {}
        # STREAMINFO block
        block_size = struct.unpack(">I", data[5:9])[0]
        sample_info = struct.unpack(">I", data[14:18])[0]
        sample_rate = (sample_info >> 12) & 0xfffff
        channels = ((sample_info >> 9) & 7) + 1
        bits_per_sample = ((sample_info >> 4) & 0x1f) + 1
        return {"sample_rate": sample_rate, "channels": channels,
                "bits_per_sample": bits_per_sample}

    def _parse_wav_header(self, data: bytes) -> Dict:
        if len(data) < 44:
            return {}
        if data[8:12] != b"WAVE":
            return {}
        channels = struct.unpack("<H", data[22:24])[0]
        sample_rate = struct.unpack("<I", data[24:28])[0]
        bits = struct.unpack("<H", data[34:36])[0]
        return {"channels": channels, "sample_rate": sample_rate,
                "bits_per_sample": bits, "form_type": "WAVE"}

    def _parse_ogg_header(self, data: bytes) -> Dict:
        if len(data) < 28:
            return {}
        version = data[4]
        header_type = data[5]
        return {"ogg_version": version, "header_type": header_type}

    def _parse_midi_header(self, data: bytes) -> Dict:
        if len(data) < 14:
            return {}
        format_type = struct.unpack(">H", data[8:10])[0]
        tracks = struct.unpack(">H", data[10:12])[0]
        division = struct.unpack(">H", data[12:14])[0]
        fmt_names = {0: "Single track", 1: "Multi-track synchronous", 2: "Multi-track asynchronous"}
        return {"format_type": fmt_names.get(format_type, str(format_type)),
                "tracks": tracks, "time_division": division}

    def _parse_pdf_header(self, data: bytes) -> Dict:
        result = {}
        # PDF version
        if data[:5] == b"%PDF-":
            result["pdf_version"] = data[5:8].decode('ascii', errors='replace')
        # Count objects, streams, etc.
        text = data[:50000]
        result["obj_count"] = text.count(b" obj\n") + text.count(b" obj\r")
        result["stream_count"] = text.count(b"stream\r\n") + text.count(b"stream\n")
        result["has_xref"] = b"xref" in text
        result["has_trailer"] = b"trailer" in text
        result["has_js"] = b"/JavaScript" in text.lower() or b"/js " in text.lower()
        result["has_embedded"] = b"/EmbeddedFile" in text.lower()
        return result

    def _parse_zip_header(self, data: bytes) -> Dict:
        result = {}
        if data[:4] == b"PK\x03\x04":
            version = struct.unpack("<H", data[4:6])[0]
            flags = struct.unpack("<H", data[6:8])[0]
            compression = struct.unpack("<H", data[8:10])[0]
            result["min_version"] = version
            result["flags"] = flags
            result["compression"] = {0: "stored", 8: "deflate", 12: "bzip2",
                                      14: "lzma", 93: "zstd"}.get(compression, str(compression))
            result["encrypted"] = bool(flags & 1)
            result["has_descriptor"] = bool(flags & 8)
            # Count entries
            eocd = data.rfind(b"PK\x05\x06")
            if eocd != -1 and eocd + 18 <= len(data):
                result["entry_count"] = struct.unpack("<H", data[eocd+8:eocd+10])[0]
        return result

    def _parse_rar_header(self, data: bytes) -> Dict:
        result = {}
        if len(data) >= 7:
            if data[6] & 0x04:
                result["rar_version"] = 5
            else:
                result["rar_version"] = 4
        return result

    def _parse_7z_header(self, data: bytes) -> Dict:
        if len(data) < 12:
            return {}
        major = data[6]
        minor = data[7]
        return {"version": f"{major}.{minor}"}

    def _parse_gz_header(self, data: bytes) -> Dict:
        if len(data) < 10:
            return {}
        flags = data[3]
        result = {"flags": flags}
        if flags & 1:
            result["text"] = True
        if flags & 4:
            result["extra"] = True
        if flags & 8:
            # Find filename
            end = data.find(b"\x00", 10)
            if end != -1:
                result["original_filename"] = data[10:end].decode('ascii', errors='replace')
        return result

    def _parse_pe_header(self, data: bytes) -> Dict:
        result = {}
        if len(data) < 64 or data[:2] != b"MZ":
            return result
        pe_off = struct.unpack("<I", data[60:64])[0]
        if pe_off + 24 > len(data):
            return result
        if data[pe_off:pe_off+4] != b"PE\x00\x00":
            return result
        machine = struct.unpack("<H", data[pe_off+4:pe_off+6])[0]
        sections = struct.unpack("<H", data[pe_off+6:pe_off+8])[0]
        machine_names = {0x14c: "x86", 0x8664: "x64", 0x1c0: "ARM", 0xaa64: "ARM64"}
        result["machine"] = machine_names.get(machine, f"0x{machine:04x}")
        result["sections"] = sections
        return result

    def _parse_elf_header(self, data: bytes) -> Dict:
        result = {}
        if len(data) < 20 or data[:4] != b"\x7fELF":
            return result
        result["class"] = {1: "32-bit", 2: "64-bit"}.get(data[4], "?")
        result["endian"] = {1: "little", 2: "big"}.get(data[5], "?")
        result["os_abi"] = data[7]
        etype = struct.unpack("<H" if data[5] == 1 else ">H", data[16:18])[0]
        result["type"] = {1: "REL", 2: "EXEC", 3: "DYN", 4: "CORE"}.get(etype, str(etype))
        machine = struct.unpack("<H" if data[5] == 1 else ">H", data[18:20])[0]
        result["machine"] = {3: "x86", 62: "x64", 40: "ARM", 183: "ARM64"}.get(machine, str(machine))
        return result

    def _parse_macho_header(self, data: bytes) -> Dict:
        result = {}
        if len(data) < 8:
            return result
        magic = struct.unpack(">I", data[:4])[0]
        if magic == 0xfeedface:
            result["arch"] = "32-bit"
            result["endian"] = "native"
        elif magic == 0xfeedfacf:
            result["arch"] = "64-bit"
            result["endian"] = "native"
        elif magic == 0xcefaedfe:
            result["arch"] = "32-bit"
            result["endian"] = "reversed"
        elif magic == 0xcffaedfe:
            result["arch"] = "64-bit"
            result["endian"] = "reversed"
        if len(data) >= 12:
            endian = ">" if magic in (0xfeedface, 0xfeedfacf) else "<"
            cputype = struct.unpack(endian + "I", data[4:8])[0]
            result["cputype"] = {0: "x86", 7: "x86_64", 12: "ARM", 16: "ARM64"}.get(
                cputype & 0xff, str(cputype))
        return result

    def _parse_ole2_header(self, data: bytes) -> Dict:
        result = {}
        if len(data) < 8 or data[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            return result
        result["ole2"] = True
        # Sector size
        if len(data) >= 32:
            sector_shift = struct.unpack("<H", data[30:32])[0]
            result["sector_size"] = 2 ** sector_shift
        return result

    def _parse_sqlite_header(self, data: bytes) -> Dict:
        result = {}
        if len(data) < 100 or data[:16] != b"SQLite format 3":
            return result
        page_size = struct.unpack(">H", data[16:18])[0]
        result["page_size"] = page_size if page_size != 1 else 65536
        result["version"] = f"{data[96]}.{data[97]}.{data[98]}"
        return result

    # ── Helpers ────────────────────────────────────────────────────

    def _shannon(self, data: bytes) -> float:
        if not data:
            return 0.0
        freq = [0] * 256
        for b in data:
            freq[b] += 1
        l = len(data)
        return -sum((f/l) * math.log2(f/l) for f in freq if f > 0)

    def _find_polyglot_markers(self, data: bytes) -> List[str]:
        """Find evidence of polyglot structures."""
        markers = []
        # Check for multiple format signatures in one file
        sigs = {
            "PE": b"MZ", "ELF": b"\x7fELF", "PDF": b"%PDF",
            "ZIP": b"PK\x03\x04", "GIF": b"GIF8", "PNG": b"\x89PNG",
            "JPEG": b"\xff\xd8", "Script": b"#!/", "HTML": b"<html",
            "VBS": b"CreateObject", "PS1": b"powershell",
        }
        found = []
        for name, sig in sigs.items():
            if sig in data:
                found.append(name)
        if len(found) > 1:
            markers.append(f"Multiple format signatures in single file: {', '.join(found)}")

        # Check for suspicious patterns
        if data[:2] == b"MZ" and b"PK" in data[100:]:
            markers.append("PE+ZIP polyglot (executable archive)")
        if data[:4] == b"%PDF" and b"MZ" in data[100:]:
            markers.append("PDF+PE polyglot (document+executable)")
        if b"#!/" in data[100:] and data[:4] not in (b"#!/", b"\x7fEL"):
            markers.append("Script embedded in non-script file")

        return markers

    def _check_trailing(self, data: bytes, format_id: Optional[str]) -> Optional[str]:
        """Check for suspicious trailing data after format end marker."""
        if not format_id:
            return None
        end_markers = {
            "jpeg": (b"\xff\xd9", 2),
            "png": (b"IEND", 8),
            "gif": (b"\x3b", 1),
            "pdf": (b"%%EOF", 5),
        }
        marker_info = end_markers.get(format_id)
        if not marker_info:
            return None
        marker, extra = marker_info
        pos = data.rfind(marker)
        if pos != -1 and pos + extra < len(data):
            trailing = len(data) - pos - extra
            if trailing > 16:
                return f"{trailing:,} bytes of trailing data after {format_id.upper()} end marker"
        return None
