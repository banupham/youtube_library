#!/usr/bin/env python3
"""ADB bridge for the Android YouTube Accessibility Collector.

This tool retrieves collector snapshots directly from a connected Android device
without requiring the participant to export/copy files on the phone.

Examples (Windows CMD):

    python scripts\android\android_bridge.py devices
    python scripts\android\android_bridge.py status
    python scripts\android\android_bridge.py pull --today
    python scripts\android\android_bridge.py watch --interval 15

The preferred source is app-specific external storage, which the collector mirrors
to specifically for ADB retrieval. A debug-only ``run-as`` fallback reads the
canonical private copy if the external mirror cannot be pulled.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

PACKAGE = "com.youtube.library.collector"
SERVICE = f"{PACKAGE}/.YouTubeAccessibilityService"
SNAPSHOT_DIR_NAME = "youtube_accessibility_snapshots"
EXTERNAL_DIR = f"/sdcard/Android/data/{PACKAGE}/files/{SNAPSHOT_DIR_NAME}"
INTERNAL_DIR = f"files/{SNAPSHOT_DIR_NAME}"


class BridgeError(RuntimeError):
    pass


@dataclass(frozen=True)
class Device:
    serial: str
    state: str
    detail: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def find_adb() -> str:
    explicit = os.environ.get("ADB")
    if explicit and Path(explicit).exists():
        return explicit

    found = shutil.which("adb")
    if found:
        return found

    exe = "adb.exe" if os.name == "nt" else "adb"
    for env_name in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        root = os.environ.get(env_name)
        if not root:
            continue
        candidate = Path(root) / "platform-tools" / exe
        if candidate.exists():
            return str(candidate)

    raise BridgeError(
        "Không tìm thấy adb. Cài Android SDK Platform-Tools hoặc thêm adb vào PATH."
    )


def adb_command(adb: str, serial: str | None, *args: str) -> list[str]:
    command = [adb]
    if serial:
        command.extend(["-s", serial])
    command.extend(args)
    return command


def run_adb(
    adb: str,
    serial: str | None,
    *args: str,
    text: bool = True,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess:
    result = subprocess.run(
        adb_command(adb, serial, *args),
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        text=text,
        check=False,
    )
    if check and result.returncode != 0:
        stderr = result.stderr.strip() if text and result.stderr else ""
        raise BridgeError(stderr or f"adb command failed: {' '.join(args)}")
    return result


def list_devices(adb: str) -> list[Device]:
    result = run_adb(adb, None, "devices", "-l")
    devices: list[Device] = []
    for raw in result.stdout.splitlines()[1:]:
        line = raw.strip()
        if not line:
            continue
        parts = line.split(maxsplit=2)
        serial = parts[0]
        state = parts[1] if len(parts) > 1 else "unknown"
        detail = parts[2] if len(parts) > 2 else ""
        devices.append(Device(serial=serial, state=state, detail=detail))
    return devices


def select_device(adb: str, requested: str | None) -> Device:
    devices = list_devices(adb)
    if requested:
        for device in devices:
            if device.serial == requested:
                if device.state != "device":
                    raise BridgeError(f"Device {requested} state={device.state}")
                return device
        raise BridgeError(f"Không thấy device serial={requested}")

    ready = [device for device in devices if device.state == "device"]
    if not ready:
        blocked = ", ".join(f"{d.serial}:{d.state}" for d in devices) or "none"
        raise BridgeError(
            "Không có Android device sẵn sàng qua ADB. "
            f"Devices hiện tại: {blocked}"
        )
    if len(ready) > 1:
        joined = ", ".join(device.serial for device in ready)
        raise BridgeError(
            f"Có nhiều device: {joined}. Dùng --serial SERIAL để chọn một máy."
        )
    return ready[0]


def sanitize_token(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", value)[:96] or "device"


def device_day(adb: str, serial: str) -> str:
    result = run_adb(adb, serial, "shell", "date", "+%F", check=False)
    value = (result.stdout or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value
    return datetime.now().date().isoformat()


def list_external_snapshots(adb: str, serial: str) -> list[str]:
    result = run_adb(adb, serial, "shell", "ls", "-1", EXTERNAL_DIR, check=False)
    if result.returncode != 0:
        return []
    return sorted(
        name.strip()
        for name in result.stdout.splitlines()
        if name.strip().endswith(".jsonl")
    )


def list_internal_snapshots(adb: str, serial: str) -> list[str]:
    result = run_adb(
        adb,
        serial,
        "exec-out",
        "run-as",
        PACKAGE,
        "ls",
        "-1",
        INTERNAL_DIR,
        check=False,
    )
    if result.returncode != 0:
        return []
    return sorted(
        name.strip()
        for name in result.stdout.splitlines()
        if name.strip().endswith(".jsonl")
    )


def remote_external_size(adb: str, serial: str, name: str) -> int | None:
    remote = f"{EXTERNAL_DIR}/{name}"
    result = run_adb(
        adb,
        serial,
        "shell",
        "sh",
        "-c",
        f"wc -c < '{remote}'",
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        return int((result.stdout or "").strip())
    except ValueError:
        return None


def pull_one(
    adb: str,
    serial: str,
    name: str,
    local_path: Path,
    *,
    force: bool = False,
) -> tuple[bool, str]:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    remote = f"{EXTERNAL_DIR}/{name}"
    remote_size = remote_external_size(adb, serial, name)

    if (
        not force
        and local_path.exists()
        and remote_size is not None
        and local_path.stat().st_size == remote_size
    ):
        return False, "unchanged"

    result = run_adb(
        adb,
        serial,
        "pull",
        remote,
        str(local_path),
        check=False,
    )
    if result.returncode == 0 and local_path.exists():
        return True, "external"

    # Debug-build fallback. Release builds normally reject run-as; the external
    # mirror above is therefore the primary transport.
    fallback = run_adb(
        adb,
        serial,
        "exec-out",
        "run-as",
        PACKAGE,
        "cat",
        f"{INTERNAL_DIR}/{name}",
        text=False,
        check=False,
    )
    if fallback.returncode == 0 and fallback.stdout:
        local_path.write_bytes(fallback.stdout)
        return True, "run-as"

    return False, "failed"


def snapshot_names(adb: str, serial: str) -> list[str]:
    names = list_external_snapshots(adb, serial)
    if names:
        return names
    return list_internal_snapshots(adb, serial)


def inspect_file(path: Path, show_text: bool) -> None:
    inspector = repo_root() / "scripts" / "android" / "inspect_accessibility_snapshots.py"
    command = [sys.executable, str(inspector), str(path)]
    if show_text:
        command.append("--show-text")
    subprocess.run(command, cwd=str(repo_root()), check=False)


def perform_pull(
    adb: str,
    device: Device,
    *,
    output_dir: Path,
    date: str | None,
    all_files: bool,
    force: bool,
    inspect: bool,
    show_text: bool,
    quiet_unchanged: bool = False,
) -> list[Path]:
    names = snapshot_names(adb, device.serial)
    if not names:
        if not quiet_unchanged:
            print("Chưa thấy snapshot JSONL trên device.")
        return []

    if not all_files:
        wanted_date = date or device_day(adb, device.serial)
        names = [name for name in names if name == f"{wanted_date}.jsonl"]
        if not names:
            if not quiet_unchanged:
                print(f"Không có snapshot cho ngày {wanted_date}.")
            return []

    destination = output_dir / sanitize_token(device.serial)
    changed: list[Path] = []
    for name in names:
        local_path = destination / name
        was_changed, source = pull_one(
            adb,
            device.serial,
            name,
            local_path,
            force=force,
        )
        if was_changed:
            changed.append(local_path)
            print(f"PULL {name} -> {local_path} [{source}]")
            if inspect:
                inspect_file(local_path, show_text)
        elif source == "unchanged":
            if not quiet_unchanged:
                print(f"UNCHANGED {name}")
        else:
            print(f"FAILED {name}", file=sys.stderr)
    return changed


def cmd_devices(adb: str, _args: argparse.Namespace) -> int:
    devices = list_devices(adb)
    if not devices:
        print("Không thấy ADB device.")
        return 1
    for device in devices:
        suffix = f"  {device.detail}" if device.detail else ""
        print(f"{device.serial}\t{device.state}{suffix}")
    return 0


def cmd_status(adb: str, args: argparse.Namespace) -> int:
    device = select_device(adb, args.serial)
    print(f"Device: {device.serial}")

    package_result = run_adb(adb, device.serial, "shell", "pm", "path", PACKAGE, check=False)
    installed = package_result.returncode == 0 and "package:" in (package_result.stdout or "")
    print(f"Collector installed: {'YES' if installed else 'NO'}")

    version = "unknown"
    if installed:
        dump = run_adb(adb, device.serial, "shell", "dumpsys", "package", PACKAGE, check=False)
        match = re.search(r"versionName=([^\s]+)", dump.stdout or "")
        if match:
            version = match.group(1)
    print(f"Collector version: {version}")

    enabled = run_adb(
        adb,
        device.serial,
        "shell",
        "settings",
        "get",
        "secure",
        "enabled_accessibility_services",
        check=False,
    )
    enabled_text = (enabled.stdout or "").strip()
    accessibility_on = PACKAGE in enabled_text or SERVICE in enabled_text
    print(f"Accessibility service: {'ENABLED' if accessibility_on else 'DISABLED'}")

    window = run_adb(adb, device.serial, "shell", "dumpsys", "window", "windows", check=False)
    focus_lines = [
        line.strip()
        for line in (window.stdout or "").splitlines()
        if "mCurrentFocus" in line or "mFocusedApp" in line
    ]
    foreground = any("com.google.android.youtube" in line for line in focus_lines)
    print(f"YouTube foreground: {'YES' if foreground else 'NO'}")
    if focus_lines:
        print(f"Focus: {focus_lines[0][:180]}")

    names = snapshot_names(adb, device.serial)
    print(f"Snapshot files: {len(names)}")
    if names:
        latest = names[-1]
        size = remote_external_size(adb, device.serial, latest)
        size_text = f" ({size} bytes)" if size is not None else ""
        print(f"Latest: {latest}{size_text}")
    print(f"ADB source dir: {EXTERNAL_DIR}")
    return 0


def cmd_pull(adb: str, args: argparse.Namespace) -> int:
    device = select_device(adb, args.serial)
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = repo_root() / output_dir
    date = args.date
    if args.today:
        date = device_day(adb, device.serial)
    perform_pull(
        adb,
        device,
        output_dir=output_dir,
        date=date,
        all_files=args.all,
        force=args.force,
        inspect=args.inspect,
        show_text=args.show_text,
    )
    return 0


def cmd_watch(adb: str, args: argparse.Namespace) -> int:
    device = select_device(adb, args.serial)
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = repo_root() / output_dir
    print(
        f"Watching {device.serial} every {args.interval:.1f}s. "
        "Ctrl+C để dừng."
    )
    try:
        while True:
            changed = perform_pull(
                adb,
                device,
                output_dir=output_dir,
                date=device_day(adb, device.serial),
                all_files=False,
                force=False,
                inspect=args.inspect,
                show_text=args.show_text,
                quiet_unchanged=True,
            )
            if changed:
                print(f"[{datetime.now().isoformat(timespec='seconds')}] updated {len(changed)} file(s)")
            time.sleep(max(2.0, args.interval))
    except KeyboardInterrupt:
        print("\nADB watch stopped.")
        return 0


def cmd_pair(adb: str, args: argparse.Namespace) -> int:
    print("ADB sẽ yêu cầu pairing code hiển thị trên Android Wireless debugging.")
    return subprocess.call([adb, "pair", args.endpoint])


def cmd_connect(adb: str, args: argparse.Namespace) -> int:
    return subprocess.call([adb, "connect", args.endpoint])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CMD/ADB bridge for YouTube Library Android Collector"
    )
    parser.add_argument("--serial", default=None, help="ADB device serial when multiple devices are connected")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("devices", help="List ADB devices")
    sub.add_parser("status", help="Check app/service/YouTube/snapshot status")

    pull = sub.add_parser("pull", help="Pull collector JSONL snapshots to the repository")
    pull_group = pull.add_mutually_exclusive_group()
    pull_group.add_argument("--today", action="store_true", help="Pull the device's current-day snapshot")
    pull_group.add_argument("--date", help="Pull YYYY-MM-DD snapshot")
    pull_group.add_argument("--all", action="store_true", help="Pull all snapshot days")
    pull.add_argument("--output-dir", default="data/android_snapshots")
    pull.add_argument("--force", action="store_true")
    pull.add_argument("--inspect", action="store_true", help="Run snapshot inspector after pull")
    pull.add_argument("--show-text", action="store_true", help="With --inspect, show node text")

    watch = sub.add_parser("watch", help="Continuously pull today's file when it changes")
    watch.add_argument("--interval", type=float, default=15.0)
    watch.add_argument("--output-dir", default="data/android_snapshots")
    watch.add_argument("--inspect", action="store_true")
    watch.add_argument("--show-text", action="store_true")

    pair = sub.add_parser("pair", help="Run adb pair for Android Wireless debugging")
    pair.add_argument("endpoint", help="IP:PAIRING_PORT shown by Android")

    connect = sub.add_parser("connect", help="Connect to an already paired wireless ADB endpoint")
    connect.add_argument("endpoint", help="IP:ADB_PORT shown by Android")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        adb = find_adb()
        if args.command == "devices":
            return cmd_devices(adb, args)
        if args.command == "status":
            return cmd_status(adb, args)
        if args.command == "pull":
            if not (args.today or args.date or args.all):
                args.today = True
            return cmd_pull(adb, args)
        if args.command == "watch":
            return cmd_watch(adb, args)
        if args.command == "pair":
            return cmd_pair(adb, args)
        if args.command == "connect":
            return cmd_connect(adb, args)
        parser.error("unknown command")
    except BridgeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
