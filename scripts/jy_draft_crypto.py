"""Verified Jianying draft encryption backend.

The encrypted container is handled by the installed Jianying Pro
``videoeditor.dll``.  This module does not infer encryption from a product
version and does not implement or guess the cipher.
"""

from __future__ import annotations

import argparse
import ctypes
import glob
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable


K_DEC = "?decrypt@EncryptUtils@lvve@@QEAA?AV?$basic_string@DU?$char_traits@D@std@@V?$allocator@D@2@@std@@AEBV34@0AEA_N@Z"
K_ENC = "?encrypt@EncryptUtils@lvve@@QEAA?AV?$basic_string@DU?$char_traits@D@std@@V?$allocator@D@2@@std@@AEBV34@@Z"
K_ENABLE = "?enable@EncryptUtils@lvve@@QEAAX_N@Z"
_VERSION_RE = re.compile(r"(?<!\d)(\d+(?:\.\d+){1,4})(?!\d)")


def _version_key(path: Path) -> tuple[int, ...]:
    matches = _VERSION_RE.findall(str(path))
    if not matches:
        return (0,)
    return max((tuple(int(part) for part in value.split(".")) for value in matches), default=(0,))


def _candidate_roots() -> Iterable[Path]:
    for variable in ("LOCALAPPDATA", "ProgramFiles", "ProgramFiles(x86)"):
        value = os.environ.get(variable)
        if value:
            yield Path(value) / "JianyingPro"

    for drive in ("C:", "D:", "E:"):
        yield Path(drive + os.sep) / "Program Files" / "JianyingPro"


def _registry_candidates() -> Iterable[Path]:
    if os.name != "nt":
        return
    try:
        import winreg
    except ImportError:
        return

    uninstall = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, uninstall) as parent:
                for index in range(winreg.QueryInfoKey(parent)[0]):
                    try:
                        with winreg.OpenKey(parent, winreg.EnumKey(parent, index)) as entry:
                            name = str(winreg.QueryValueEx(entry, "DisplayName")[0])
                            if "jianying" not in name.lower() and "剪映" not in name:
                                continue
                            location = ""
                            for field in ("InstallLocation", "DisplayIcon"):
                                try:
                                    location = str(winreg.QueryValueEx(entry, field)[0]).strip('"')
                                    if location:
                                        break
                                except OSError:
                                    pass
                            if location:
                                p = Path(location)
                                yield (p if p.is_dir() else p.parent) / "videoeditor.dll"
                    except OSError:
                        continue
        except OSError:
            continue


def find_jianying_dll() -> str:
    """Return the newest discovered compatible DLL candidate path.

    An explicitly set ``JIANYING_VIDEOEDITOR_DLL`` wins outright: it is meant
    to pin a specific install and must not be outvoted by the version sort.
    """

    explicit = os.environ.get("JIANYING_VIDEOEDITOR_DLL", "").strip('"')
    if explicit:
        pinned = Path(explicit)
        if not pinned.is_file():
            raise RuntimeError(
                f"JIANYING_VIDEOEDITOR_DLL points to a missing file: {explicit}"
            )
        return str(pinned.resolve())

    candidates: set[Path] = set()
    for root in list(_candidate_roots()) + list(_registry_candidates()):
        if root.name.lower() == "videoeditor.dll" and root.is_file():
            candidates.add(root.resolve())
            continue
        if not root.is_dir():
            continue
        direct = root / "videoeditor.dll"
        if direct.is_file():
            candidates.add(direct.resolve())
        for value in glob.glob(str(root / "*" / "videoeditor.dll")):
            candidates.add(Path(value).resolve())

    if not candidates:
        raise RuntimeError(
            "No Jianying videoeditor.dll was found. Set JIANYING_VIDEOEDITOR_DLL "
            "to an exact path. Encrypted projects require Windows and an installed compatible Jianying build."
        )
    return str(sorted(candidates, key=lambda value: (_version_key(value), str(value)))[-1])


class MsvcString(ctypes.Structure):
    """MSVC x64 ``std::string`` layout used by the verified exports.

    Note: heap buffers returned by encrypt/decrypt are never freed (the DLL
    does not export its ``~basic_string``), so each call leaks one allocation.
    Acceptable for short-lived CLI processes; do not embed in long-running
    loops without an upper bound.
    """

    _fields_ = [
        ("_buf", ctypes.c_ubyte * 16),
        ("size", ctypes.c_uint64),
        ("capacity", ctypes.c_uint64),
    ]

    @classmethod
    def from_bytes(cls, data: bytes) -> "MsvcString":
        value = cls()
        value.size = len(data)
        if len(data) < 16:
            ctypes.memmove(value._buf, data, len(data))
            value.capacity = 15
        else:
            buffer = ctypes.create_string_buffer(data, len(data) + 1)
            pointer = ctypes.cast(buffer, ctypes.c_void_p)
            ctypes.memmove(value._buf, ctypes.byref(ctypes.c_void_p(pointer.value)), 8)
            value.capacity = len(data)
            value._keepalive = buffer
        return value

    def to_bytes(self) -> bytes:
        if self.capacity < 16:
            return bytes(self._buf[: self.size])
        pointer = ctypes.c_uint64.from_buffer(self._buf).value
        return ctypes.string_at(pointer, self.size) if pointer else b""


class JyDraftCrypto:
    """Call Jianying's encryption exports and verify every encryption round trip."""

    def __init__(self, dll_path: str | None = None):
        if os.name != "nt":
            raise RuntimeError("Encrypted Jianying projects are currently supported only on Windows")
        self.dll_path = str(Path(dll_path or find_jianying_dll()).resolve())
        self.dll_dir = str(Path(self.dll_path).parent)
        self._load()

    def _load(self) -> None:
        self._dll_directory = os.add_dll_directory(self.dll_dir) if hasattr(os, "add_dll_directory") else None
        self._library = ctypes.WinDLL(self.dll_path)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetProcAddress.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        kernel32.GetProcAddress.restype = ctypes.c_void_p

        def address(symbol: str) -> int:
            result = kernel32.GetProcAddress(self._library._handle, symbol.encode("ascii"))
            if not result:
                raise RuntimeError(f"videoeditor.dll does not expose the required symbol: {symbol}")
            return result

        dec = address(K_DEC)
        enc = address(K_ENC)
        enable = address(K_ENABLE)
        dec_proto = ctypes.CFUNCTYPE(
            ctypes.POINTER(MsvcString), ctypes.c_void_p, ctypes.POINTER(MsvcString),
            ctypes.POINTER(MsvcString), ctypes.POINTER(MsvcString), ctypes.POINTER(ctypes.c_bool)
        )
        enc_proto = ctypes.CFUNCTYPE(
            ctypes.POINTER(MsvcString), ctypes.c_void_p, ctypes.POINTER(MsvcString), ctypes.POINTER(MsvcString)
        )
        enable_proto = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_bool)
        self._decrypt_fn = dec_proto(dec)
        self._encrypt_fn = enc_proto(enc)
        self._enable_fn = enable_proto(enable)

    @property
    def jianying_version(self) -> str:
        return Path(self.dll_dir).name

    def decrypt(self, encrypted: bytes) -> bytes:
        source = MsvcString.from_bytes(encrypted)
        params = MsvcString.from_bytes(b"{}")
        output = MsvcString()
        ok = ctypes.c_bool(False)
        self._decrypt_fn(None, ctypes.byref(output), ctypes.byref(source), ctypes.byref(params), ctypes.byref(ok))
        if not ok.value:
            raise RuntimeError("Jianying decrypt returned ok=false")
        return output.to_bytes()

    def decrypt_json(self, encrypted: bytes) -> dict[str, Any]:
        value = json.loads(self.decrypt(encrypted).decode("utf-8-sig"))
        if not isinstance(value, dict):
            raise ValueError("Decoded Jianying content is not a JSON object")
        return value

    def encrypt(self, plain: bytes) -> bytes:
        self._enable_fn(None, True)
        source = MsvcString.from_bytes(plain)
        output = MsvcString()
        self._encrypt_fn(None, ctypes.byref(output), ctypes.byref(source))
        encrypted = output.to_bytes()
        decoded = self.decrypt(encrypted)
        if decoded != plain:
            raise RuntimeError(f"Encryption round-trip mismatch: input={len(plain)} decoded={len(decoded)}")
        return encrypted

    def encrypt_json(self, value: dict[str, Any]) -> bytes:
        plain = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return self.encrypt(plain)


def parse_plain_json(data: bytes) -> dict[str, Any] | None:
    try:
        value = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--decrypt", metavar="PATH")
    group.add_argument("--encrypt", metavar="PATH")
    parser.add_argument("--output", required=True)
    parser.add_argument("--dll")
    args = parser.parse_args(argv)
    backend = JyDraftCrypto(args.dll)
    source = Path(args.decrypt or args.encrypt)
    target = Path(args.output)
    if args.decrypt:
        target.write_bytes(backend.decrypt(source.read_bytes()))
    else:
        plain = source.read_bytes()
        json.loads(plain.decode("utf-8-sig"))
        target.write_bytes(backend.encrypt(plain))
    print(json.dumps({"ok": True, "output": str(target), "dll": backend.dll_path}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    # See jianying_project._hard_exit: TerminateProcess skips videoeditor.dll
    # detach so its buffered banners never leak into stdout after our JSON.
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    if os.name == "nt":
        ctypes.windll.kernel32.TerminateProcess(ctypes.c_void_p(-1), code)
    os._exit(code)
