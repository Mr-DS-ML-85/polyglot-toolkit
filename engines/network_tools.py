"""
Network tools engine — whois, DNS, TCP connect, raw request editor, websocket monitor.

Features:
  - Whois lookup (via socket to whois server)
  - DNS lookup (A, AAAA, MX, NS, TXT, CNAME, SOA)
  - TCP connect tester
  - Raw HTTP request editor
  - Network logs
  - Auto-detect URLs/IPs/domains from text
  - Request history

Author: Mr-DS-ML-85
"""

import os
import re
import json
import time
import socket
import struct
import logging
import threading
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("polyglot_shield.network")

# ── Auto-Detection Patterns ──────────────────────────────────────────────────

URL_PATTERN = re.compile(
    r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?:/[^\s\'"<>\[\]]*)?',
    re.IGNORECASE
)

IP_PATTERN = re.compile(
    r'\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b'
)

DOMAIN_PATTERN = re.compile(
    r'\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:com|net|org|io|co|info|biz|xyz|'
    r'top|me|dev|app|cloud|ru|cn|de|uk|fr|jp|kr|in|br|au|ca|nl|se|no|fi|dk|pl|cz|'
    r'sk|hu|ro|bg|hr|rs|si|ba|me|al|mk|gr|tr|il|ae|sa|eg|za|ng|ke|tz|gh|'
    r'onion|bit)\b',
    re.IGNORECASE
)

EMAIL_PATTERN = re.compile(
    r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
)


def auto_detect_targets(text: str) -> Dict[str, List[str]]:
    """Auto-detect URLs, IPs, domains, and emails from text."""
    return {
        "urls": list(set(URL_PATTERN.findall(text))),
        "ips": list(set(IP_PATTERN.findall(text))),
        "domains": list(set(DOMAIN_PATTERN.findall(text))),
        "emails": list(set(EMAIL_PATTERN.findall(text))),
    }


# ── DNS Lookup ───────────────────────────────────────────────────────────────

class DNSLookup:
    """DNS resolution using socket (no external dependencies)."""

    # DNS query builder
    def _build_query(self, domain: str, qtype: int = 1) -> bytes:
        """Build a DNS query packet."""
        # Header
        tx_id = os.urandom(2)
        flags = b'\x01\x00'  # Standard query, recursion desired
        questions = b'\x00\x01'
        answers = b'\x00\x00'
        authority = b'\x00\x00'
        additional = b'\x00\x00'
        header = tx_id + flags + questions + answers + authority + additional

        # Question section
        question = b''
        for part in domain.split('.'):
            question += bytes([len(part)]) + part.encode()
        question += b'\x00'  # End of domain
        question += struct.pack('!HH', qtype, 1)  # Type, Class IN

        return header + question

    def _parse_response(self, data: bytes) -> List[str]:
        """Parse DNS response, extract answers."""
        results = []
        # Skip header (12 bytes)
        offset = 12

        # Skip question section
        qdcount = struct.unpack('!H', data[4:6])[0]
        for _ in range(qdcount):
            while data[offset] != 0:
                if data[offset] & 0xC0 == 0xC0:  # Pointer
                    offset += 2
                    break
                offset += 1 + data[offset]
            else:
                offset += 1
            offset += 4  # QTYPE + QCLASS

        # Parse answers
        ancount = struct.unpack('!H', data[6:8])[0]
        for _ in range(ancount):
            # Skip name (handle pointers)
            if data[offset] & 0xC0 == 0xC0:
                offset += 2
            else:
                while data[offset] != 0:
                    offset += 1 + data[offset]
                offset += 1

            rtype, rclass, ttl, rdlength = struct.unpack('!HHIH', data[offset:offset + 10])
            offset += 10
            rdata = data[offset:offset + rdlength]
            offset += rdlength

            if rtype == 1 and rdlength == 4:  # A record
                results.append(socket.inet_ntoa(rdata))
            elif rtype == 28 and rdlength == 16:  # AAAA record
                results.append(socket.inet_ntop(socket.AF_INET6, rdata))
            elif rtype in (2, 5, 15):  # NS, CNAME, MX
                name = self._decode_name(data, offset - rdlength)
                if rtype == 15:  # MX
                    preference = struct.unpack('!H', rdata[:2])[0]
                    name = self._decode_name(rdata, 2)
                    results.append(f"{preference} {name}")
                else:
                    results.append(name)
            elif rtype == 16:  # TXT
                txt_len = rdata[0]
                results.append(rdata[1:1 + txt_len].decode('utf-8', errors='replace'))
            elif rtype == 6:  # SOA
                mname = self._decode_name(rdata, 0)
                results.append(f"MNAME: {mname}")

        return results

    def _decode_name(self, data: bytes, offset: int) -> str:
        """Decode DNS name from response."""
        parts = []
        while data[offset] != 0:
            if data[offset] & 0xC0 == 0xC0:
                pointer = struct.unpack('!H', data[offset:offset + 2])[0] & 0x3FFF
                parts.extend(self._decode_name(data, pointer).split('.'))
                return '.'.join(parts)
            length = data[offset]
            offset += 1
            parts.append(data[offset:offset + length].decode('ascii', errors='replace'))
            offset += length
        return '.'.join(parts)

    def lookup(self, domain: str, record_type: str = "A",
               dns_server: str = "8.8.8.8") -> Dict[str, Any]:
        """Perform DNS lookup."""
        type_map = {"A": 1, "AAAA": 28, "MX": 15, "NS": 2, "TXT": 16, "CNAME": 5, "SOA": 6}
        qtype = type_map.get(record_type.upper(), 1)

        try:
            query = self._build_query(domain, qtype)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5)
            sock.sendto(query, (dns_server, 53))
            data, _ = sock.recvfrom(4096)
            sock.close()

            results = self._parse_response(data)
            return {
                "domain": domain,
                "record_type": record_type,
                "dns_server": dns_server,
                "results": results,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"domain": domain, "error": str(e), "record_type": record_type}

    def full_lookup(self, domain: str) -> Dict[str, Any]:
        """Perform full DNS lookup (A, AAAA, MX, NS, TXT)."""
        results = {}
        for rtype in ["A", "AAAA", "MX", "NS", "TXT"]:
            results[rtype] = self.lookup(domain, rtype)
        return results


# ── Whois Lookup ─────────────────────────────────────────────────────────────

class WhoisLookup:
    """Whois lookup via direct socket connection to whois servers."""

    WHOIS_SERVERS = {
        "default": "whois.iana.org",
        ".com": "whois.verisign-grs.com",
        ".net": "whois.verisign-grs.com",
        ".org": "whois.pir.org",
        ".io": "whois.nic.io",
        ".co": "whois.nic.co",
        ".me": "whois.nic.me",
        ".info": "whois.afilias.net",
        ".biz": "whois.neulevel.biz",
        ".ru": "whois.tcinet.ru",
        ".cn": "whois.cnnic.cn",
        ".de": "whois.denic.de",
        ".uk": "whois.nic.uk",
        ".xyz": "whois.nic.xyz",
        ".top": "whois.nic.top",
    }

    def lookup(self, target: str) -> Dict[str, Any]:
        """Perform whois lookup for domain or IP."""
        # Determine whois server
        server = self.WHOIS_SERVERS["default"]
        for tld, srv in self.WHOIS_SERVERS.items():
            if tld != "default" and target.lower().endswith(tld):
                server = srv
                break

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((server, 43))
            sock.send((target + "\r\n").encode())

            response = b""
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                response += data
            sock.close()

            text = response.decode("utf-8", errors="replace")

            # Parse key fields
            parsed = self._parse_whois(text)

            return {
                "target": target,
                "server": server,
                "raw": text[:5000],
                "parsed": parsed,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"target": target, "error": str(e)}

    def _parse_whois(self, text: str) -> Dict[str, str]:
        """Parse whois response into key fields."""
        fields = {}
        key_patterns = {
            "registrar": r"Registrar:\s*(.+)",
            "creation_date": r"Creation Date:\s*(.+)",
            "expiration_date": r"Registry Expiry Date:\s*(.+)",
            "updated_date": r"Updated Date:\s*(.+)",
            "name_servers": r"Name Server:\s*(.+)",
            "status": r"Domain Status:\s*(.+)",
            "registrant_org": r"Registrant Organization:\s*(.+)",
            "registrant_country": r"Registrant Country:\s*(.+)",
        }

        for key, pattern in key_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                fields[key] = matches[0].strip() if len(matches) == 1 else [m.strip() for m in matches]

        return fields


# ── TCP Connect Tester ───────────────────────────────────────────────────────

class TCPConnectTester:
    """TCP port connectivity tester."""

    def test(self, host: str, port: int, timeout: float = 3.0) -> Dict[str, Any]:
        """Test TCP connection to host:port."""
        start = time.time()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            elapsed = time.time() - start
            sock.close()

            return {
                "host": host,
                "port": port,
                "open": result == 0,
                "latency_ms": round(elapsed * 1000, 2),
                "timestamp": datetime.now().isoformat(),
            }
        except socket.timeout:
            return {"host": host, "port": port, "open": False, "error": "timeout",
                    "latency_ms": round((time.time() - start) * 1000, 2)}
        except Exception as e:
            return {"host": host, "port": port, "open": False, "error": str(e)}

    def scan_ports(self, host: str, ports: List[int],
                   timeout: float = 2.0) -> List[Dict[str, Any]]:
        """Scan multiple ports."""
        results = []
        for port in ports:
            results.append(self.test(host, port, timeout))
        return results

    def common_ports_scan(self, host: str) -> List[Dict[str, Any]]:
        """Scan common ports."""
        common = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 993, 995,
                  1433, 1521, 3306, 3389, 5432, 5900, 6379, 8080, 8443, 9090, 27017]
        return self.scan_ports(host, common)


# ── Raw Request Editor ───────────────────────────────────────────────────────

class RawRequestEditor:
    """Build and send raw HTTP requests."""

    def parse(self, raw_request: str) -> Dict[str, Any]:
        """Parse a raw HTTP request string."""
        lines = raw_request.strip().split('\r\n')
        if not lines:
            return {"error": "Empty request"}

        # Parse request line
        parts = lines[0].split(' ', 2)
        method = parts[0] if len(parts) > 0 else "GET"
        path = parts[1] if len(parts) > 1 else "/"
        version = parts[2] if len(parts) > 2 else "HTTP/1.1"

        # Parse headers
        headers = {}
        body = ""
        in_body = False
        for line in lines[1:]:
            if in_body:
                body += line + "\r\n"
            elif line == "":
                in_body = True
            else:
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()

        return {
            "method": method,
            "path": path,
            "version": version,
            "headers": headers,
            "body": body.strip(),
            "host": headers.get("Host", ""),
        }

    def build(self, method: str, host: str, path: str = "/",
              headers: Optional[Dict[str, str]] = None,
              body: str = "", https: bool = False) -> str:
        """Build a raw HTTP request."""
        if headers is None:
            headers = {}
        headers.setdefault("Host", host)
        headers.setdefault("Connection", "close")

        request = f"{method} {path} HTTP/1.1\r\n"
        for key, value in headers.items():
            request += f"{key}: {value}\r\n"
        if body:
            headers["Content-Length"] = str(len(body))
            # Rebuild with Content-Length
            request = f"{method} {path} HTTP/1.1\r\n"
            for key, value in headers.items():
                request += f"{key}: {value}\r\n"
            request += f"\r\n{body}"
        else:
            request += "\r\n"

        return request

    def send(self, raw_request: str, host: str, port: int = 80,
             timeout: float = 10.0) -> Dict[str, Any]:
        """Send a raw HTTP request."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)

            if port == 443:
                import ssl
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                sock = context.wrap_socket(sock, server_hostname=host)

            sock.connect((host, port))
            sock.send(raw_request.encode())

            response = b""
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                response += data
            sock.close()

            response_text = response.decode("utf-8", errors="replace")

            # Parse response
            resp_lines = response_text.split("\r\n", 1)
            status_line = resp_lines[0] if resp_lines else ""
            status_parts = status_line.split(" ", 2)
            status_code = int(status_parts[1]) if len(status_parts) > 1 else 0

            return {
                "status_code": status_code,
                "status_line": status_line,
                "headers": resp_lines[1][:2000] if len(resp_lines) > 1 else "",
                "body": response_text[-5000:] if len(response_text) > 5000 else response_text,
                "size": len(response),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"error": str(e)}


# ── Request History ──────────────────────────────────────────────────────────

class RequestHistory:
    """Persistent request history log."""

    def __init__(self, history_file: str = None):
        self.history_file = history_file or os.path.expanduser(
            "~/.polyglot/request_history.jsonl")
        self._ensure_dir()

    def _ensure_dir(self):
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)

    def add(self, entry: Dict[str, Any]):
        """Add entry to history."""
        entry["timestamp"] = datetime.now().isoformat()
        with open(self.history_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent history entries."""
        if not os.path.exists(self.history_file):
            return []
        with open(self.history_file) as f:
            lines = f.readlines()
        entries = []
        for line in lines[-limit:]:
            try:
                entries.append(json.loads(line.strip()))
            except Exception:
                pass
        return entries

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search history."""
        entries = self.get(limit=500)
        return [e for e in entries if query.lower() in json.dumps(e).lower()]

    def clear(self):
        """Clear history."""
        if os.path.exists(self.history_file):
            os.remove(self.history_file)
