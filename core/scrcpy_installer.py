import os
import platform
import shutil
import stat
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path


PHONEVIEW_SCRCPY_VERSION = "v4.1"
PHONEVIEW_BUILD_NAME = "v4.1-phoneview"

INSTALL_ROOT = Path.home() / ".local" / "share" / "phoneview" / "scrcpy"
BIN_ROOT = Path.home() / ".local" / "bin"

SOURCE_URL = (
    "https://github.com/Genymobile/scrcpy/archive/refs/tags/"
    f"{PHONEVIEW_SCRCPY_VERSION}.tar.gz"
)
SERVER_URL = (
    "https://github.com/Genymobile/scrcpy/releases/download/"
    f"{PHONEVIEW_SCRCPY_VERSION}/scrcpy-server-{PHONEVIEW_SCRCPY_VERSION}"
)
SERVER_SHA256 = "deacb991ed2509715160ffdc7907e47b4160eb30d1566217e9047fd5b8850cae"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDORED_SRC = PROJECT_ROOT / "vendor" / "scrcpy" / PHONEVIEW_SCRCPY_VERSION / "app" / "src"


class ScrcpyInstaller:
    """Build and install PhoneView's pinned, patched scrcpy 4.1 engine."""

    @staticmethod
    def target_root():
        return INSTALL_ROOT / PHONEVIEW_BUILD_NAME

    @staticmethod
    def local_binary():
        candidates = [
            ScrcpyInstaller.target_root() / "bin" / "scrcpy",
            BIN_ROOT / "scrcpy-phoneview",
        ]
        for path in candidates:
            if path.is_file() and os.access(path, os.X_OK):
                return str(path)
        return None

    @staticmethod
    def version(binary=None):
        binary = binary or ScrcpyInstaller.local_binary()
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
    def is_phoneview_build():
        return ScrcpyInstaller.local_binary() is not None

    @staticmethod
    def _require_command(command):
        if shutil.which(command):
            return
        raise RuntimeError(
            f"Required build tool '{command}' is missing. "
            "Install the scrcpy build dependencies and run setup again."
        )

    @staticmethod
    def _run(command, cwd=None, env=None, emit=None):
        if emit:
            emit("$ " + " ".join(str(item) for item in command))

        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            env=env,
            capture_output=True,
            text=True,
        )

        output = (result.stdout or "") + (result.stderr or "")
        if emit and output.strip():
            for line in output.splitlines():
                emit(line)

        if result.returncode != 0:
            raise RuntimeError(
                f"Command failed with exit code {result.returncode}: "
                + " ".join(str(item) for item in command)
            )

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

        if not sys_platform_linux():
            raise RuntimeError(
                "The PhoneView scrcpy build currently supports Linux only."
            )

        machine = platform.machine().lower()
        if machine not in ("x86_64", "amd64"):
            raise RuntimeError(
                f"PhoneView scrcpy 4.1 is currently prepared for Linux x86_64, "
                f"not {machine}."
            )

        required = ("python3", "meson", "ninja", "gcc", "pkg-config", "tar")
        for command in required:
            ScrcpyInstaller._require_command(command)

        if not VENDORED_SRC.is_dir():
            raise RuntimeError(
                f"Patched scrcpy source files were not found at: {VENDORED_SRC}"
            )

        target_root = ScrcpyInstaller.target_root()
        target_binary = target_root / "bin" / "scrcpy"

        if target_binary.is_file() and os.access(target_binary, os.X_OK):
            BIN_ROOT.mkdir(parents=True, exist_ok=True)
            link = BIN_ROOT / "scrcpy-phoneview"
            if link.is_symlink() or link.exists():
                link.unlink()
            link.symlink_to(target_binary)
            emit(f"✓ PhoneView scrcpy {PHONEVIEW_BUILD_NAME} is already installed.")
            set_progress(100)
            return str(target_binary)

        INSTALL_ROOT.mkdir(parents=True, exist_ok=True)
        BIN_ROOT.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="phoneview-scrcpy-build-") as temp:
            temp_root = Path(temp)
            source_archive = temp_root / f"scrcpy-{PHONEVIEW_SCRCPY_VERSION}.tar.gz"
            server_file = temp_root / "scrcpy-server"
            source_root = temp_root / "source"

            emit(f"Preparing pinned scrcpy {PHONEVIEW_SCRCPY_VERSION} source.")
            set_progress(5)

            request = urllib.request.Request(
                SOURCE_URL,
                headers={"User-Agent": "PhoneView"},
            )
            with urllib.request.urlopen(request, timeout=30) as response, source_archive.open("wb") as output:
                total = int(response.headers.get("Content-Length") or 0)
                received = 0
                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break
                    output.write(chunk)
                    received += len(chunk)
                    if total:
                        set_progress(5 + (received * 30 / total))

            emit("Extracting pinned source tree...")
            with tarfile.open(source_archive, "r:gz") as archive:
                archive.extractall(temp_root)

            extracted = [
                item for item in temp_root.iterdir()
                if item.is_dir() and item.name.startswith("scrcpy-")
            ]
            if not extracted:
                raise RuntimeError("The scrcpy 4.1 source archive did not extract correctly.")
            source_root = extracted[0]

            emit("Installing PhoneView's patched scrcpy source files...")
            for relative in ("screen.c", "screen.h"):
                source_file = VENDORED_SRC / relative
                destination = source_root / "app" / "src" / relative
                shutil.copy2(source_file, destination)
                emit(f"✓ Patched app/src/{relative}")

            emit("Downloading the matching scrcpy 4.1 Android server...")
            request = urllib.request.Request(
                SERVER_URL,
                headers={"User-Agent": "PhoneView"},
            )
            with urllib.request.urlopen(request, timeout=30) as response, server_file.open("wb") as output:
                shutil.copyfileobj(response, output)

            digest = __import__("hashlib").sha256(server_file.read_bytes()).hexdigest().lower()
            if digest != SERVER_SHA256:
                raise RuntimeError(
                    "scrcpy-server SHA-256 verification failed. "
                    "The server file was not used."
                )
            emit("✓ Matching scrcpy-server checksum verified.")
            set_progress(45)

            build_root = temp_root / "build"
            install_root = temp_root / "install"
            install_root.mkdir()

            emit("Configuring the PhoneView scrcpy build...")
            ScrcpyInstaller._run(
                [
                    "meson",
                    "setup",
                    str(build_root),
                    "--buildtype=release",
                    "--strip",
                    "-Db_lto=true",
                    f"-Dprebuilt_server={server_file}",
                    f"--prefix={install_root}",
                ],
                cwd=source_root,
                emit=emit,
            )
            set_progress(60)

            emit("Compiling PhoneView scrcpy 4.1...")
            ScrcpyInstaller._run(
                ["ninja", "-C", str(build_root)],
                cwd=source_root,
                emit=emit,
            )
            set_progress(82)

            emit("Installing the patched scrcpy engine into PhoneView's private directory...")
            ScrcpyInstaller._run(
                ["ninja", "-C", str(build_root), "install"],
                cwd=source_root,
                emit=emit,
            )

            if target_root.exists():
                shutil.rmtree(target_root)
            shutil.copytree(install_root, target_root)

        target_binary = target_root / "bin" / "scrcpy"
        if not target_binary.is_file():
            raise RuntimeError(
                "The patched scrcpy build completed, but the executable was not found."
            )

        target_binary.chmod(
            target_binary.stat().st_mode
            | stat.S_IXUSR
            | stat.S_IXGRP
            | stat.S_IXOTH
        )

        link = BIN_ROOT / "scrcpy-phoneview"
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(target_binary)

        emit(f"✓ PhoneView scrcpy {PHONEVIEW_BUILD_NAME} installed.")
        emit("✓ Future upstream scrcpy releases will NOT replace this build.")
        set_progress(100)
        return str(target_binary)


def sys_platform_linux():
    return os.name != "nt" and os.sys.platform.startswith("linux")


def main():
    try:
        ScrcpyInstaller.install()
        return 0
    except Exception as exc:
        print(f"ERROR:{exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
