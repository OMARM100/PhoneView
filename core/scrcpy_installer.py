import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path


GITHUB_API = "https://api.github.com/repos/Genymobile/scrcpy/releases/latest"
INSTALL_ROOT = Path.home() / ".local" / "share" / "phoneview" / "scrcpy"
BIN_ROOT = Path.home() / ".local" / "bin"


class ScrcpyInstaller:
    """Install/update the official stable scrcpy release without apt."""

    @staticmethod
    def local_binary():
        candidates = [
            BIN_ROOT / "scrcpy",
            INSTALL_ROOT / "current" / "scrcpy",
        ]
        for path in candidates:
            if path.is_file() and os.access(path, os.X_OK):
                return str(path)
        return None

    @staticmethod
    def system_binary():
        return shutil.which("scrcpy")

    @staticmethod
    def find_binary():
        return ScrcpyInstaller.local_binary() or ScrcpyInstaller.system_binary()

    @staticmethod
    def version(binary=None):
        binary = binary or ScrcpyInstaller.find_binary()
        if not binary:
            return ""
        try:
            result = subprocess.run(
                [binary, "--version"],
                capture_output=True,
                text=True,
                timeout=4,
            )
            return (result.stdout or result.stderr or "").splitlines()[0].strip()
        except (OSError, subprocess.SubprocessError):
            return ""

    @staticmethod
    def _latest_release():
        request = urllib.request.Request(
            GITHUB_API,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "PhoneView",
            },
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def install(progress=None, log=None):
        def emit(message):
            if log:
                log(message)
            print(message, flush=True)

        def set_progress(value):
            value = max(0, min(100, int(value)))
            if progress:
                progress(value)
            print(f"PROGRESS:{value}", flush=True)

        if not sys.platform.startswith("linux"):
            raise RuntimeError(
                "The automatic official scrcpy updater currently supports Linux only."
            )

        machine = platform.machine().lower()
        if machine not in ("x86_64", "amd64"):
            raise RuntimeError(
                f"No official PhoneView installer is configured for Linux architecture: {machine}"
            )

        emit("Checking the latest stable scrcpy release from the official GitHub repository...")
        set_progress(3)

        release = ScrcpyInstaller._latest_release()
        tag = release.get("tag_name", "")
        if not tag or release.get("draft") or release.get("prerelease"):
            raise RuntimeError("GitHub did not return a stable scrcpy release.")

        assets = release.get("assets", [])
        filename = f"scrcpy-linux-x86_64-{tag}.tar.gz"
        asset = next((item for item in assets if item.get("name") == filename), None)
        if not asset:
            raise RuntimeError(
                f"The official release {tag} does not contain the Linux x86_64 archive."
            )

        archive_url = asset.get("browser_download_url")
        expected_digest = asset.get("digest", "")
        if not archive_url:
            raise RuntimeError("The official release archive has no download URL.")

        target_root = INSTALL_ROOT / tag
        target_bin = target_root / "scrcpy"

        if target_bin.is_file() and os.access(target_bin, os.X_OK):
            BIN_ROOT.mkdir(parents=True, exist_ok=True)
            link = BIN_ROOT / "scrcpy"
            if link.is_symlink() or link.exists():
                link.unlink()
            link.symlink_to(target_bin)
            emit(f"✓ scrcpy {tag} is already installed.")
            set_progress(100)
            return str(target_bin)

        INSTALL_ROOT.mkdir(parents=True, exist_ok=True)
        BIN_ROOT.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="phoneview-scrcpy-") as temp:
            archive = Path(temp) / filename

            emit(f"Downloading official scrcpy {tag}...")
            request = urllib.request.Request(
                archive_url,
                headers={"User-Agent": "PhoneView"},
            )

            with urllib.request.urlopen(request, timeout=30) as response, archive.open("wb") as output:
                total = int(response.headers.get("Content-Length") or 0)
                received = 0

                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break

                    output.write(chunk)
                    received += len(chunk)

                    if total:
                        set_progress(10 + (received * 65 / total))

            emit("Verifying the official release checksum...")
            set_progress(78)

            if expected_digest.startswith("sha256:"):
                expected = expected_digest.split(":", 1)[1].lower()
                digest = hashlib.sha256(archive.read_bytes()).hexdigest().lower()

                if digest != expected:
                    raise RuntimeError(
                        "Checksum verification failed. The downloaded archive was not installed."
                    )

                emit("✓ SHA-256 checksum verified.")
            else:
                emit("! GitHub did not expose an asset digest; archive verification was skipped.")

            extract_root = Path(temp) / "extract"
            extract_root.mkdir()

            with tarfile.open(archive, "r:gz") as tar:
                tar.extractall(extract_root)

            binary = next(
                (
                    path
                    for path in extract_root.rglob("scrcpy")
                    if path.is_file() and os.access(path, os.X_OK)
                ),
                None,
            )

            if binary is None:
                raise RuntimeError(
                    "The official archive was downloaded, but scrcpy was not found inside it."
                )

            if target_root.exists():
                shutil.rmtree(target_root)

            shutil.copytree(binary.parent, target_root)

        target_bin = target_root / "scrcpy"
        target_bin.chmod(
            target_bin.stat().st_mode
            | stat.S_IXUSR
            | stat.S_IXGRP
            | stat.S_IXOTH
        )

        link = BIN_ROOT / "scrcpy"
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(target_bin)

        emit(f"✓ Official scrcpy {tag} installed in {target_root}.")
        emit(f"✓ PhoneView will use {link} before any old system scrcpy.")
        set_progress(100)
        return str(target_bin)


def main():
    try:
        ScrcpyInstaller.install()
        return 0
    except Exception as exc:
        print(f"ERROR:{exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
