# -*- coding: utf-8 -*-
"""
jy_draft_crypto.py - 剪映 (JianYing Pro) 草稿文件解密/加密工具

原理：加载剪映自带的 videoeditor.dll，调用其导出的 EncryptUtils::decrypt / encrypt / enable
函数（MSVC x64 ABI），复用剪映官方加解密逻辑，而非自行猜测算法。
适用于使用 jianying_draft_encrypt_v2 加密方案的版本（验证 10.3.0 - 11.2.0）。

用法（CLI）:
    python jy_draft_crypto.py -d <encrypted.json> [output.json]   # 解密
    python jy_draft_crypto.py -e <plain.json> [output.json]       # 回加密

作为库:
    from jy_draft_crypto import JyDraftCrypto
    crypto = JyDraftCrypto()  # 自动探测剪映安装目录
    plain = crypto.decrypt(open("draft_content.json","rb").read())
    enc   = crypto.encrypt(plain)
"""
import ctypes
import glob
import json
import os
import re
import sys

K_DEC = "?decrypt@EncryptUtils@lvve@@QEAA?AV?$basic_string@DU?$char_traits@D@std@@V?$allocator@D@2@@std@@AEBV34@0AEA_N@Z"
K_ENC = "?encrypt@EncryptUtils@lvve@@QEAA?AV?$basic_string@DU?$char_traits@D@std@@V?$allocator@D@2@@std@@AEBV34@@Z"
K_ENABLE = "?enable@EncryptUtils@lvve@@QEAAX_N@Z"

_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def find_jianying_dll():
    """自动探测剪映安装目录中的 videoeditor.dll，优先最新版本。"""
    candidates = []

    # 常见安装位置（含多版本并存目录）
    roots = [
        os.environ.get("LOCALAPPDATA", r"C:\Users\11\AppData\Local") + r"\JianyingPro",
        r"C:\Program Files\JianyingPro",
        r"C:\Program Files (x86)\JianyingPro",
        r"D:\Program Files\JianyingPro",
        r"E:\Program Files\JianyingPro",
    ]
    for root in roots:
        if not os.path.isdir(root):
            continue
        # 直接位于根目录
        p = os.path.join(root, "videoeditor.dll")
        if os.path.isfile(p):
            candidates.append(p)
        # 版本子目录
        for sub in glob.glob(os.path.join(root, "*")):
            if os.path.isdir(sub):
                p = os.path.join(sub, "videoeditor.dll")
                if os.path.isfile(p):
                    candidates.append(p)

    if not candidates:
        # 注册表探测
        try:
            import winreg
            for hive, key in [
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            ]:
                try:
                    with winreg.OpenKey(hive, key) as hk:
                        for i in range(winreg.QueryInfoKey(hk)[0]):
                            try:
                                with winreg.OpenKey(hk, winreg.EnumKey(hk, i)) as sub:
                                    name = winreg.QueryValueEx(sub, "DisplayName")[0]
                                    if "jianying" in name.lower() or "剪映" in name:
                                        loc = ""
                                        try:
                                            loc = winreg.QueryValueEx(sub, "InstallLocation")[0]
                                        except OSError:
                                            pass
                                        icon = winreg.QueryValueEx(sub, "DisplayIcon")[0]
                                        if not loc and icon:
                                            loc = os.path.dirname(icon)
                                        if loc:
                                            p = os.path.join(loc, "videoeditor.dll")
                                            if os.path.isfile(p):
                                                candidates.append(p)
                            except OSError:
                                continue
                except OSError:
                    continue
        except ImportError:
            pass

    if not candidates:
        raise RuntimeError(
            "未找到 videoeditor.dll。请检查剪映安装位置，或手动传入 dll 路径到 JyDraftCrypto(dll_path=...)"
        )

    # 按版本号排序取最新
    def ver_key(path):
        m = _VERSION_RE.search(os.path.basename(os.path.dirname(path)))
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)

    candidates.sort(key=ver_key)
    return candidates[-1]


class MsvcString(ctypes.Structure):
    """MSVC x64 std::string 内存布局（32 字节）"""
    _fields_ = [
        ("_buf", ctypes.c_ubyte * 16),  # union { char small[16]; char* ptr; }
        ("size", ctypes.c_uint64),
        ("capacity", ctypes.c_uint64),
    ]

    @classmethod
    def from_bytes(cls, data: bytes) -> "MsvcString":
        s = cls()
        n = len(data)
        s.size = n
        if n < 16:
            ctypes.memmove(s._buf, data, n)
            s.capacity = 15
        else:
            buf = ctypes.create_string_buffer(data, n + 1)
            ptr = ctypes.cast(buf, ctypes.c_void_p)
            ctypes.memmove(s._buf, ctypes.byref(ctypes.c_void_p(ptr.value)), 8)
            s.capacity = n
            s._keepalive = buf
        return s

    def to_bytes(self) -> bytes:
        if self.capacity < 16:
            return bytes(self._buf[: self.size])
        ptr_val = ctypes.c_uint64.from_buffer(self._buf).value
        if not ptr_val:
            return b""
        return ctypes.string_at(ptr_val, self.size)


class JyDraftCrypto:
    """剪映草稿加解密器（复用 videoeditor.dll 的 EncryptUtils）"""

    def __init__(self, dll_path: str = None):
        if dll_path is None:
            dll_path = find_jianying_dll()
        self.dll_path = os.path.abspath(dll_path)
        self.dll_dir = os.path.dirname(self.dll_path)
        self._load()

    def _load(self):
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
        kernel32.SetDllDirectoryW.restype = ctypes.c_int
        kernel32.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]
        kernel32.LoadLibraryExW.restype = ctypes.c_void_p
        kernel32.GetProcAddress.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        kernel32.GetProcAddress.restype = ctypes.c_void_p

        # 让 DLL 能找到同目录依赖
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = self.dll_dir + ";" + old_path
        self._old_cwd = os.getcwd()
        os.chdir(self.dll_dir)
        kernel32.SetDllDirectoryW("")

        LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR = 0x100
        LOAD_LIBRARY_SEARCH_APPLICATION_DIR = 0x200
        LOAD_LIBRARY_SEARCH_SYSTEM32 = 0x800
        LOAD_LIBRARY_SEARCH_USER_DIRS = 0x400
        flags = (
            LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR
            | LOAD_LIBRARY_SEARCH_APPLICATION_DIR
            | LOAD_LIBRARY_SEARCH_SYSTEM32
            | LOAD_LIBRARY_SEARCH_USER_DIRS
        )
        h = kernel32.LoadLibraryExW(self.dll_path, None, flags)
        if not h:
            h = kernel32.LoadLibraryExW(self.dll_path, None, 0)
        if not h:
            raise RuntimeError(
                f"LoadLibraryExW(videoeditor.dll) 失败 gle={ctypes.get_last_error()} path={self.dll_path}"
            )
        self._h = h

        self._dec = kernel32.GetProcAddress(h, K_DEC.encode("ascii"))
        self._enc = kernel32.GetProcAddress(h, K_ENC.encode("ascii"))
        self._enable = kernel32.GetProcAddress(h, K_ENABLE.encode("ascii"))
        missing = [
            n
            for n, p in [("decrypt", self._dec), ("encrypt", self._enc), ("enable", self._enable)]
            if not p
        ]
        if missing:
            raise RuntimeError(
                f"videoeditor.dll 缺少导出符号 {missing}。该版本可能不使用 jianying_draft_encrypt_v2 方案。"
            )

        DEC_PROTO = ctypes.CFUNCTYPE(
            ctypes.POINTER(MsvcString),
            ctypes.c_void_p,
            ctypes.POINTER(MsvcString),
            ctypes.POINTER(MsvcString),
            ctypes.POINTER(MsvcString),
            ctypes.POINTER(ctypes.c_bool),
        )
        ENC_PROTO = ctypes.CFUNCTYPE(
            ctypes.POINTER(MsvcString),
            ctypes.c_void_p,
            ctypes.POINTER(MsvcString),
            ctypes.POINTER(MsvcString),
        )
        ENB_PROTO = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_bool)
        self._dec_fn = DEC_PROTO(self._dec)
        self._enc_fn = ENC_PROTO(self._enc)
        self._enb_fn = ENB_PROTO(self._enable)

    @property
    def jianying_version(self) -> str:
        """返回对应剪映版本目录名（如 11.2.0.14339）"""
        return os.path.basename(self.dll_dir)

    def decrypt(self, text: bytes) -> bytes:
        """加密草稿内容 -> 明文 JSON 字节"""
        in_s = MsvcString.from_bytes(text)
        param_s = MsvcString.from_bytes(b"{}")
        out_s = MsvcString()
        ok = ctypes.c_bool(False)
        self._dec_fn(None, ctypes.byref(out_s), ctypes.byref(in_s), ctypes.byref(param_s), ctypes.byref(ok))
        if not ok.value:
            raise RuntimeError("decrypt failed (ok=false)")
        return out_s.to_bytes()

    def decrypt_json(self, text: bytes) -> dict:
        """加密草稿内容 -> dict"""
        return json.loads(self.decrypt(text).decode("utf-8"))

    def encrypt(self, text: bytes) -> bytes:
        """明文 JSON 字节 -> 加密草稿内容（base64 文本）"""
        self._enb_fn(None, True)
        in_s = MsvcString.from_bytes(text)
        out_s = MsvcString()
        self._enc_fn(None, ctypes.byref(out_s), ctypes.byref(in_s))
        enc = out_s.to_bytes()
        # 回环校验
        dec = self.decrypt(enc)
        if dec != text:
            raise RuntimeError(
                f"encrypt roundtrip mismatch: in={len(text)} out={len(dec)}"
            )
        return enc

    def encrypt_json(self, obj) -> bytes:
        """dict -> 加密草稿内容"""
        raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return self.encrypt(raw)

    # ---- 文件级便利方法 ----
    def decrypt_file(self, src: str, dst: str = None) -> str:
        with open(src, "rb") as f:
            plain = self.decrypt(f.read())
        if dst is None:
            dst = src + ".dec.json"
        with open(dst, "wb") as f:
            f.write(plain)
        return dst

    def encrypt_file(self, src: str, dst: str = None) -> str:
        with open(src, "rb") as f:
            enc = self.encrypt(f.read())
        if dst is None:
            dst = src + ".enc.json"
        with open(dst, "wb") as f:
            f.write(enc)
        return dst

    def modify_draft(self, draft_dir: str, mutator) -> dict:
        """解密草稿目录下的 draft_content.json，用 mutator(dict) 修改后回加密。

        返回修改后的内容 dict。mutator 可以是:
          - 函数: 接收 dict 并原地修改
          - dict: 直接替换（部分更新用 dict_update）
        """
        content_path = os.path.join(draft_dir, "draft_content.json")
        with open(content_path, "rb") as f:
            content = self.decrypt_json(f.read())

        if callable(mutator):
            mutator(content)
        elif isinstance(mutator, dict):
            content.update(mutator)
        else:
            raise TypeError("mutator 必须是函数或 dict")

        enc = self.encrypt_json(content)
        with open(content_path, "wb") as f:
            f.write(enc)
        return content


def _main(argv):
    def usage():
        print(__doc__)
        return 64

    if len(argv) < 2:
        return usage()

    mode = argv[0]
    if mode not in ("-d", "--dec", "-e", "--enc"):
        return usage()

    src = argv[1]
    dst = argv[2] if len(argv) > 2 else None

    crypto = JyDraftCrypto()
    print(f"[info] 使用剪映版本目录: {crypto.jianying_version}")
    print(f"[info] DLL: {crypto.dll_path}")

    if mode in ("-d", "--dec"):
        out = crypto.decrypt_file(src, dst)
        print(f"[ok] 解密完成 -> {out}")
    else:
        out = crypto.encrypt_file(src, dst)
        print(f"[ok] 回加密完成 -> {out} (roundtrip 校验通过)")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
