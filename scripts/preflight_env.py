#!/usr/bin/env python3
"""
ThermalForge 环境自检脚本
=========================
在不同电脑上运行此脚本，自动检测 3 个本地依赖软件：
  1. SolidWorks      — 模型优化（COM 自动化）
  2. ANSYS SpaceClaim — 工程 CAD 几何生成
  3. ANSYS Fluent     — CFD 热仿真

检测策略（每个软件按优先级依次尝试）：
  ① 环境变量（SOLIDWORKS_EXE / SPACECLAIM_EXE / FLUENT_EXE）
  ② Windows 注册表（InstallPath / ProgID）
  ③ 常见安装路径扫描（Program Files / ProgramData）
  ④ PATH 中的可执行文件（shutil.which）

检测完成后：
  - 在终端打印彩色报告
  - 生成 .env.thermalforge 文件（供项目 Settings 读取）
  - 可选 --launch 参数自动启动已检测到的软件

用法：
  python preflight_env.py              # 仅检测
  python preflight_env.py --launch     # 检测 + 启动
  python preflight_env.py --launch sw  # 仅启动 SolidWorks
  python preflight_env.py --check-only # 仅检测，不写 .env
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ──────────────────────────────────────────────
# 数据结构
# ──────────────────────────────────────────────


@dataclass
class SoftwareDetection:
    """单个软件的检测结果。"""
    name: str
    display_name: str
    found: bool = False
    version: str = ""
    install_dir: str = ""
    executable: str = ""
    api_version: str = ""
    evidence: str = ""           # 检测依据
    warnings: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)


@dataclass
class PreflightReport:
    """完整自检报告。"""
    solidworks: SoftwareDetection = field(
        default_factory=lambda: SoftwareDetection("solidworks", "SolidWorks")
    )
    spaceclaim: SoftwareDetection = field(
        default_factory=lambda: SoftwareDetection("spaceclaim", "ANSYS SpaceClaim")
    )
    fluent: SoftwareDetection = field(
        default_factory=lambda: SoftwareDetection("fluent", "ANSYS Fluent")
    )
    python_ok: bool = False
    python_version: str = ""
    python_path: str = ""
    missing_packages: list[str] = field(default_factory=list)
    timestamp: str = ""

    @property
    def all_found(self) -> bool:
        return self.solidworks.found and self.spaceclaim.found and self.fluent.found

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "all_found": self.all_found,
            "python": {
                "ok": self.python_ok,
                "version": self.python_version,
                "path": self.python_path,
                "missing_packages": self.missing_packages,
            },
            "solidworks": _detection_to_dict(self.solidworks),
            "spaceclaim": _detection_to_dict(self.spaceclaim),
            "fluent": _detection_to_dict(self.fluent),
        }


def _detection_to_dict(d: SoftwareDetection) -> dict:
    return {
        "found": d.found,
        "version": d.version,
        "install_dir": d.install_dir,
        "executable": d.executable,
        "api_version": d.api_version,
        "evidence": d.evidence,
        "warnings": d.warnings,
        "extra": d.extra,
    }


# ──────────────────────────────────────────────
# 注册表工具
# ──────────────────────────────────────────────

def _try_winreg():
    """安全导入 winreg（非 Windows 返回 None）。"""
    try:
        import winreg
        return winreg
    except ImportError:
        return None


def _reg_read(winreg, hive, subkey: str, value_name: str) -> Optional[str]:
    """读取注册表字符串值，失败返回 None。"""
    try:
        with winreg.OpenKey(hive, subkey) as key:
            data, _ = winreg.QueryValueEx(key, value_name)
            return str(data)
    except OSError:
        return None


def _reg_enum_subkeys(winreg, hive, subkey: str) -> list[str]:
    """枚举注册表子键名列表。"""
    try:
        with winreg.OpenKey(hive, subkey) as key:
            names = []
            i = 0
            while True:
                try:
                    name, _ = winreg.EnumKey(key, i)
                    names.append(name)
                    i += 1
                except OSError:
                    break
            return names
    except OSError:
        return []


def _reg_find_install_dir(
    winreg, hive, subkey: str, value_names: tuple[str, ...]
) -> tuple[str, str]:
    """在注册表键中依次尝试多个值名，返回 (install_dir, which_value_name)。"""
    for vn in value_names:
        val = _reg_read(winreg, hive, subkey, vn)
        if val and Path(val).exists():
            return val, vn
    # 即使路径不存在也返回最后一个非空值
    for vn in value_names:
        val = _reg_read(winreg, hive, subkey, vn)
        if val:
            return val, vn
    return "", ""


# ──────────────────────────────────────────────
# SolidWorks 检测
# ──────────────────────────────────────────────

def detect_solidworks() -> SoftwareDetection:
    """检测 SolidWorks 安装位置和版本。"""
    det = SoftwareDetection("solidworks", "SolidWorks")

    # ① 环境变量
    env_exe = os.environ.get("SOLIDWORKS_EXE", "")
    if env_exe and Path(env_exe).exists():
        det.found = True
        det.executable = env_exe
        det.install_dir = str(Path(env_exe).parent)
        det.evidence = "环境变量 SOLIDWORKS_EXE"
        det.warnings.append("由环境变量指定，未验证版本")

    winreg = _try_winreg()

    # ② 注册表：SolidWorks 安装信息
    if not det.found and winreg:
        # SolidWorks 主安装信息在 HKLM\SOFTWARE\SolidWorks\<版本>
        for hive in (winreg.HKEY_LOCAL_MACHINE,):
            sw_root = r"SOFTWARE\SolidWorks"
            for ver_key in _reg_enum_subkeys(winreg, hive, sw_root):
                if not ver_key.startswith("SOLIDWORKS "):
                    continue
                base = f"{sw_root}\\{ver_key}"
                install_dir, vn = _reg_find_install_dir(
                    winreg, hive, base,
                    ("InstallDir", "SolidWorks Folder", "Path"),
                )
                if install_dir:
                    det.found = True
                    det.version = ver_key.replace("SOLIDWORKS ", "")
                    det.install_dir = install_dir
                    det.executable = str(Path(install_dir) / "sldworks.exe")
                    if not Path(det.executable).exists():
                        # 尝试 bin 子目录
                        alt = Path(install_dir) / "bin" / "sldworks.exe"
                        if alt.exists():
                            det.executable = str(alt)
                    det.evidence = f"注册表 HKLM\\{base}\\{vn}"
                    break
            if det.found:
                break

        # 备选：COM ProgID SldWorks.Application 的 CLSID 映射
        if not det.found:
            for hive in (winreg.HKEY_CLASSES_ROOT,):
                try:
                    with winreg.OpenKey(hive, "SldWorks.Application"):
                        det.found = True
                        det.evidence = "注册表 ProgID SldWorks.Application（COM 可用）"
                        det.warnings.append("检测到 COM 接口但未找到安装目录，将使用 COM Dispatch")
                        break
                except OSError:
                    pass

    # ③ 常见安装路径
    if not det.found:
        common_paths = [
            r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS",
            r"C:\Program Files\SolidWorks Corp\SOLIDWORKS",
            r"C:\Program Files\Common Files\SolidWorks Shared",
        ]
        # 尝试扫描各版本
        for base in common_paths:
            base_path = Path(base)
            if base_path.exists():
                # 查找 sldworks.exe
                exe = base_path / "sldworks.exe"
                if not exe.exists():
                    exe = base_path / "bin" / "sldworks.exe"
                if exe.exists():
                    det.found = True
                    det.executable = str(exe)
                    det.install_dir = str(base_path)
                    det.evidence = f"常见路径 {base}"
                    break

        # 扫描 Program Files 下的 SolidWorks 目录（支持版本子目录）
        if not det.found:
            for pf in (r"C:\Program Files", r"C:\Program Files (x86)"):
                pf_path = Path(pf)
                if not pf_path.exists():
                    continue
                for entry in pf_path.iterdir():
                    if "solidworks" in entry.name.lower():
                        exe = entry / "sldworks.exe"
                        if not exe.exists():
                            exe = entry / "bin" / "sldworks.exe"
                        if exe.exists():
                            det.found = True
                            det.executable = str(exe)
                            det.install_dir = str(entry)
                            det.evidence = f"扫描 {pf} 发现 {entry.name}"
                            break
                if det.found:
                    break

    # ④ PATH
    if not det.found:
        which = shutil.which("sldworks") or shutil.which("SLDWORKS")
        if which:
            det.found = True
            det.executable = which
            det.install_dir = str(Path(which).parent)
            det.evidence = "PATH 中的 sldworks"

    return det


# ──────────────────────────────────────────────
# ANSYS SpaceClaim 检测
# ──────────────────────────────────────────────

# SpaceClaim API 版本映射
_SC_API_MAP = {
    "v261": "V261",
    "v252": "V252",
    "v251": "V251",
    "v242": "V242",
    "v241": "V241",
    "v232": "V232",
    "v231": "V231",
}


def detect_spaceclaim() -> SoftwareDetection:
    """检测 ANSYS SpaceClaim 安装位置和版本。"""
    det = SoftwareDetection("spaceclaim", "ANSYS SpaceClaim")

    # ① 环境变量
    env_exe = os.environ.get("SPACECLAIM_EXE", "")
    if env_exe and Path(env_exe).exists():
        det.found = True
        det.executable = env_exe
        det.install_dir = str(Path(env_exe).parent)
        det.api_version = _infer_sc_api_version(env_exe)
        det.version = _infer_ansys_version(env_exe)
        det.evidence = "环境变量 SPACECLAIM_EXE"

    winreg = _try_winreg()

    # ② 注册表：ANSYS 安装路径
    if not det.found and winreg:
        for hive in (winreg.HKEY_LOCAL_MACHINE,):
            ansys_root = r"SOFTWARE\ANSYS, Inc."
            install_dir, vn = _reg_find_install_dir(
                winreg, hive, ansys_root,
                ("ANSYS_INSTALL_DIR", "InstallPath", "ANSYSLI_INSTALL_DIR"),
            )
            if install_dir:
                det.found = True
                det.install_dir = install_dir
                det.version = _infer_ansys_version(install_dir)
                det.evidence = f"注册表 HKLM\\{ansys_root}\\{vn}"
                # 查找 SpaceClaim.exe
                exe = _find_spaceclaim_exe(install_dir)
                if exe:
                    det.executable = exe
                    det.api_version = _infer_sc_api_version(exe)
                else:
                    det.warnings.append("找到 ANSYS 安装目录但未找到 SpaceClaim.exe")
                break

    # ③ 常见安装路径
    if not det.found:
        ansys_versions = ["v261", "v252", "v251", "v242", "v241", "v232", "v231"]
        for pf in (r"C:\Program Files", r"C:\Program Files (x86)"):
            for ver in ansys_versions:
                # SpaceClaim 可能的路径模式
                candidates = [
                    Path(pf) / "ANSYS Inc" / ver / "scdm" / "SpaceClaim.exe",
                    Path(pf) / "ANSYS Inc" / ver / "SpaceClaim" / "SpaceClaim.exe",
                    Path(pf) / "ANSYS Inc" / ver / "scdm" / "SpaceClaim.exe",
                ]
                for c in candidates:
                    if c.exists():
                        det.found = True
                        det.executable = str(c)
                        det.install_dir = str(c.parent)
                        det.version = ver
                        det.api_version = _SC_API_MAP.get(ver, "V252")
                        det.evidence = f"常见路径 {c}"
                        break
                if det.found:
                    break
            if det.found:
                break

    # ④ PATH
    if not det.found:
        which = shutil.which("SpaceClaim") or shutil.which("SpaceClaim.exe")
        if which:
            det.found = True
            det.executable = which
            det.install_dir = str(Path(which).parent)
            det.api_version = _infer_sc_api_version(which)
            det.version = _infer_ansys_version(which)
            det.evidence = "PATH 中的 SpaceClaim"

    return det


def _find_spaceclaim_exe(ansys_dir: str) -> str:
    """在 ANSYS 安装目录中查找 SpaceClaim.exe。"""
    base = Path(ansys_dir)
    # 按版本号排序，取最新的
    version_dirs = sorted(
        [d for d in base.iterdir() if d.is_dir() and d.name.startswith("v")],
        reverse=True,
    )
    for vd in version_dirs:
        for sub in ("scdm", "SpaceClaim"):
            exe = vd / sub / "SpaceClaim.exe"
            if exe.exists():
                return str(exe)
    return ""


def _infer_sc_api_version(path: str) -> str:
    """从路径推断 SpaceClaim API 版本。"""
    lowered = path.lower().replace("/", "\\")
    for token, version in _SC_API_MAP.items():
        if token in lowered:
            return version
    return "V252"


def _infer_ansys_version(path: str) -> str:
    """从路径推断 ANSYS 版本号。"""
    match = re.search(r"v(\d{3})", path, re.IGNORECASE)
    if match:
        return "v" + match.group(1)
    return ""


# ──────────────────────────────────────────────
# ANSYS Fluent 检测
# ──────────────────────────────────────────────

def detect_fluent() -> SoftwareDetection:
    """检测 ANSYS Fluent 安装位置和版本。"""
    det = SoftwareDetection("fluent", "ANSYS Fluent")

    # ① 环境变量
    env_exe = os.environ.get("FLUENT_EXE", "")
    if env_exe and Path(env_exe).exists():
        det.found = True
        det.executable = env_exe
        det.install_dir = str(Path(env_exe).parent)
        det.version = _infer_ansys_version(env_exe)
        det.evidence = "环境变量 FLUENT_EXE"

    winreg = _try_winreg()

    # ② 注册表：复用 ANSYS 安装路径
    if not det.found and winreg:
        for hive in (winreg.HKEY_LOCAL_MACHINE,):
            ansys_root = r"SOFTWARE\ANSYS, Inc."
            install_dir, vn = _reg_find_install_dir(
                winreg, hive, ansys_root,
                ("ANSYS_INSTALL_DIR", "InstallPath", "ANSYSLI_INSTALL_DIR"),
            )
            if install_dir:
                exe = _find_fluent_exe(install_dir)
                if exe:
                    det.found = True
                    det.executable = exe
                    det.install_dir = str(Path(exe).parent)
                    det.version = _infer_ansys_version(exe)
                    det.evidence = f"注册表 HKLM\\{ansys_root}\\{vn} → {exe}"
                # 即使没找到 fluent.exe，也记录 ANSYS 目录
                if not det.found:
                    det.extra["ansys_install_dir"] = install_dir
                    det.warnings.append(
                        f"找到 ANSYS 安装目录 {install_dir} 但未找到 fluent.exe"
                    )

    # ③ 常见安装路径
    if not det.found:
        ansys_versions = ["v261", "v252", "v251", "v242", "v241", "v232", "v231"]
        for pf in (r"C:\Program Files", r"C:\Program Files (x86)"):
            for ver in ansys_versions:
                candidates = [
                    Path(pf) / "ANSYS Inc" / ver / "fluent" / "ntbin" / "win64" / "fluent.exe",
                    Path(pf) / "ANSYS Inc" / ver / "fluent" / "ntbin" / "winx64" / "fluent.exe",
                ]
                for c in candidates:
                    if c.exists():
                        det.found = True
                        det.executable = str(c)
                        det.install_dir = str(c.parent)
                        det.version = ver
                        det.evidence = f"常见路径 {c}"
                        break
                if det.found:
                    break
            if det.found:
                break

    # ④ PATH
    if not det.found:
        which = shutil.which("fluent") or shutil.which("fluent.exe")
        if which:
            det.found = True
            det.executable = which
            det.install_dir = str(Path(which).parent)
            det.version = _infer_ansys_version(which)
            det.evidence = "PATH 中的 fluent"

    return det


def _find_fluent_exe(ansys_dir: str) -> str:
    """在 ANSYS 安装目录中查找 fluent.exe。"""
    base = Path(ansys_dir)
    version_dirs = sorted(
        [d for d in base.iterdir() if d.is_dir() and d.name.startswith("v")],
        reverse=True,
    )
    for vd in version_dirs:
        for arch in ("win64", "winx64"):
            exe = vd / "fluent" / "ntbin" / arch / "fluent.exe"
            if exe.exists():
                return str(exe)
    return ""


# ──────────────────────────────────────────────
# Python 环境检测
# ──────────────────────────────────────────────

def check_python() -> tuple[bool, str, str, list[str]]:
    """检测 Python 版本和必需依赖包。

    返回 (ok, version, path, missing_packages)。
    """
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    path = sys.executable

    required = {
        "pydantic": "Pydantic（数据模型）",
        "pydantic_settings": "pydantic-settings（配置管理）",
        "fastapi": "FastAPI（API 框架）",
        "uvicorn": "Uvicorn（ASGI 服务器）",
    }
    # Windows / SolidWorks 额外依赖
    if sys.platform == "win32":
        required["win32com"] = "pywin32（SolidWorks COM 自动化）"
        required["comtypes"] = "comtypes（COM 备选接口）"

    missing = []
    for module, desc in required.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(f"{module} — {desc}")

    ok = len(missing) == 0 and sys.version_info >= (3, 11)
    return ok, version, path, missing


# ──────────────────────────────────────────────
# .env 文件生成
# ──────────────────────────────────────────────

def write_env_file(report: PreflightReport, output_path: Path) -> None:
    """将检测结果写入 .env.thermalforge 文件。"""
    lines = [
        "# ThermalForge 环境配置 — 由 preflight_env.py 自动生成",
        f"# 生成时间: {report.timestamp}",
        "",
        "# ── Python ──",
        f"# Python {report.python_version} @ {report.python_path}",
        "",
    ]

    if report.solidworks.found:
        lines.extend([
            "# ── SolidWorks ──",
            f"SOLIDWORKS_ENABLED=true",
        ])
        if report.solidworks.executable:
            lines.append(f'SOLIDWORKS_EXE={report.solidworks.executable}')
        lines.append(f"SOLIDWORKS_TIMEOUT_SECONDS=900.0")
    else:
        lines.extend([
            "# ── SolidWorks（未检测到）──",
            "SOLIDWORKS_ENABLED=false",
        ])
    lines.append("")

    if report.spaceclaim.found and report.spaceclaim.executable:
        lines.extend([
            "# ── ANSYS SpaceClaim ──",
            f'SPACECLAIM_EXE={report.spaceclaim.executable}',
            f"# API 版本: {report.spaceclaim.api_version}",
            f"# 版本: {report.spaceclaim.version}",
        ])
    else:
        lines.extend([
            "# ── ANSYS SpaceClaim（未检测到）──",
            "# SPACECLAIM_EXE=",
        ])
    lines.append("")

    if report.fluent.found and report.fluent.executable:
        lines.extend([
            "# ── ANSYS Fluent ──",
            f'FLUENT_EXE={report.fluent.executable}',
            f"# 版本: {report.fluent.version}",
        ])
    else:
        lines.extend([
            "# ── ANSYS Fluent（未检测到）──",
            "# FLUENT_EXE=",
        ])

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ──────────────────────────────────────────────
# 终端报告打印
# ──────────────────────────────────────────────

# ANSI 颜色码
_C_GREEN = "\033[92m"
_C_RED = "\033[91m"
_C_YELLOW = "\033[93m"
_C_CYAN = "\033[96m"
_C_BOLD = "\033[1m"
_C_DIM = "\033[2m"
_C_RESET = "\033[0m"


def _enable_ansi_colors():
    """在 Windows 10+ 启用 ANSI 颜色支持。"""
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


def _status_icon(found: bool) -> str:
    return f"{_C_GREEN}[OK]{_C_RESET}" if found else f"{_C_RED}[MISSING]{_C_RESET}"


def _print_detection(det: SoftwareDetection):
    """打印单个软件检测结果。"""
    icon = _status_icon(det.found)
    print(f"\n  {icon}  {_C_BOLD}{det.display_name}{_C_RESET}")

    if det.found:
        if det.version:
            print(f"       版本:     {det.version}")
        if det.api_version:
            print(f"       API 版本: {det.api_version}")
        if det.executable:
            print(f"       可执行:   {det.executable}")
        if det.install_dir:
            print(f"       安装目录: {det.install_dir}")
        if det.evidence:
            print(f"       检测依据: {_C_DIM}{det.evidence}{_C_RESET}")
    else:
        print(f"       {_C_YELLOW}未检测到安装{_C_RESET}")
        if det.warnings:
            for w in det.warnings:
                print(f"       {_C_YELLOW}⚠ {w}{_C_RESET}")

    for w in det.warnings if det.found else []:
        print(f"       {_C_YELLOW}⚠ {w}{_C_RESET}")


def print_report(report: PreflightReport):
    """打印完整的彩色终端报告。"""
    _enable_ansi_colors()

    print()
    print(f"  {_C_BOLD}{_C_CYAN}══════════════════════════════════════════════════{_C_RESET}")
    print(f"  {_C_BOLD}{_C_CYAN}  ThermalForge 环境自检报告{_C_RESET}")
    print(f"  {_C_BOLD}{_C_CYAN}══════════════════════════════════════════════════{_C_RESET}")
    print(f"  {_C_DIM}时间: {report.timestamp}{_C_RESET}")

    # Python
    py_icon = _status_icon(report.python_ok)
    print(f"\n  {py_icon}  {_C_BOLD}Python 运行环境{_C_RESET}")
    print(f"       版本:   {report.python_version}")
    print(f"       路径:   {report.python_path}")
    if report.missing_packages:
        print(f"       {_C_YELLOW}缺失依赖包:{_C_RESET}")
        for pkg in report.missing_packages:
            print(f"         • {pkg}")
    else:
        print(f"       {_C_GREEN}所有必需依赖包已安装{_C_RESET}")

    # 三个软件
    _print_detection(report.solidworks)
    _print_detection(report.spaceclaim)
    _print_detection(report.fluent)

    # 总结
    print()
    found_count = sum([
        report.solidworks.found,
        report.spaceclaim.found,
        report.fluent.found,
    ])
    if report.all_found and report.python_ok:
        print(f"  {_C_GREEN}{_C_BOLD}✓ 全部检测通过，环境就绪！{_C_RESET}")
    else:
        print(f"  {_C_YELLOW}{_C_BOLD}⚠ 检测到 {found_count}/3 个软件{_C_RESET}", end="")
        if not report.python_ok:
            print(f"  {_C_RED}+ Python 环境不完整{_C_RESET}", end="")
        print()
        print(f"  {_C_DIM}缺失的软件可使用对应环境变量手动指定路径。{_C_RESET}")

    print()


# ──────────────────────────────────────────────
# 软件启动
# ──────────────────────────────────────────────

def launch_software(det: SoftwareDetection) -> bool:
    """启动检测到的软件，返回是否成功。"""
    if not det.found or not det.executable:
        if not det.found:
            print(f"  {_C_YELLOW}跳过 {det.display_name}：未检测到{_C_RESET}")
        return False

    exe = det.executable
    if not Path(exe).exists():
        print(f"  {_C_RED}{det.display_name} 可执行文件不存在: {exe}{_C_RESET}")
        return False

    try:
        if sys.platform == "win32":
            os.startfile(exe)  # type: ignore[attr-defined]
        else:
            subprocess.Popen([exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"  {_C_GREEN}已启动 {det.display_name}: {exe}{_C_RESET}")
        return True
    except Exception as exc:
        print(f"  {_C_RED}启动 {det.display_name} 失败: {exc}{_C_RESET}")
        return False


# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────

def run_preflight(
    write_env: bool = True,
    env_path: Path | None = None,
) -> PreflightReport:
    """执行完整自检，返回报告。"""
    from datetime import datetime, timezone

    report = PreflightReport()
    report.timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Python
    report.python_ok, report.python_version, report.python_path, report.missing_packages = (
        check_python()
    )

    # 三个软件
    report.solidworks = detect_solidworks()
    report.spaceclaim = detect_spaceclaim()
    report.fluent = detect_fluent()

    # 写 .env
    if write_env:
        if env_path is None:
            env_path = Path(__file__).resolve().parent.parent / ".env.thermalforge"
        write_env_file(report, env_path)

    return report


def main():
    parser = argparse.ArgumentParser(
        description="ThermalForge 环境自检：检测 SolidWorks / SpaceClaim / Fluent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--launch", nargs="?", const="all",
        help="检测后启动软件：all（全部）或 sw/solidworks, sc/spaceclaim, fl/fluent",
    )
    parser.add_argument(
        "--check-only", action="store_true",
        help="仅检测，不写入 .env.thermalforge 文件",
    )
    parser.add_argument(
        "--env-path", type=str, default="",
        help=".env.thermalforge 输出路径（默认项目根目录）",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="以 JSON 格式输出结果（不打印彩色报告）",
    )
    args = parser.parse_args()

    env_path = Path(args.env_path) if args.env_path else None
    report = run_preflight(
        write_env=not args.check_only,
        env_path=env_path,
    )

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        print_report(report)

    # 启动软件
    if args.launch:
        print(f"\n  {_C_CYAN}启动软件...{_C_RESET}")
        launch_map = {
            "all": [report.solidworks, report.spaceclaim, report.fluent],
            "sw": [report.solidworks],
            "solidworks": [report.solidworks],
            "sc": [report.spaceclaim],
            "spaceclaim": [report.spaceclaim],
            "fl": [report.fluent],
            "fluent": [report.fluent],
        }
        targets = launch_map.get(args.launch, [])
        if not targets:
            print(f"  {_C_RED}未知目标: {args.launch}{_C_RESET}")
            print(f"  可选: all, sw, sc, fl")
            sys.exit(1)
        for det in targets:
            launch_software(det)
            time.sleep(1)
        print()

    # 退出码
    sys.exit(0 if report.all_found else 1)


if __name__ == "__main__":
    main()
