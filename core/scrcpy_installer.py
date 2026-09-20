import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
import hashlib
from pathlib import Path


PHONEVIEW_SCRCPY_VERSION = "v4.1"
PHONEVIEW_BUILD_NAME = "v4.1-phoneview-toolbar"

INSTALL_ROOT = Path.home() / ".local" / "share" / "phoneview" / "scrcpy"
BIN_ROOT = Path.home() / ".local" / "bin"

SERVER_URL = (
    "https://github.com/Genymobile/scrcpy/releases/download/"
    f"{PHONEVIEW_SCRCPY_VERSION}/scrcpy-server-{PHONEVIEW_SCRCPY_VERSION}"
)
SERVER_SHA256 = "deacb991ed2509715160ffdc7907e47b4160eb30d1566217e9047fd5b8850cae"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDORED_ROOT = PROJECT_ROOT / "vendor" / "scrcpy" / PHONEVIEW_SCRCPY_VERSION
SDL_INSTALL_RELATIVE = Path("app") / "deps" / "work" / "install" / "linux-native-shared"


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
    def find_binary():
        """Compatibility helper: only the pinned PhoneView engine is valid."""
        return ScrcpyInstaller.local_binary()

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
                env=ScrcpyInstaller.runtime_environment(),
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
    def _pkg_config_has_sdl3(env):
        try:
            result = subprocess.run(
                ["pkg-config", "--atleast-version=3.2.0", "sdl3"],
                capture_output=True,
                text=True,
                timeout=5,
                env=env,
            )
            return result.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    @staticmethod
    def runtime_library_dir():
        path = ScrcpyInstaller.target_root() / "lib"
        return str(path) if path.is_dir() else ""

    @staticmethod
    def runtime_environment():
        env = os.environ.copy()
        lib_dir = ScrcpyInstaller.runtime_library_dir()
        if lib_dir:
            old = env.get("LD_LIBRARY_PATH", "")
            env["LD_LIBRARY_PATH"] = f"{lib_dir}:{old}" if old else lib_dir
        return env

    @staticmethod
    def _install_launcher(target_binary):
        """Install a portable launcher that exposes the bundled SDL3 runtime."""
        BIN_ROOT.mkdir(parents=True, exist_ok=True)
        launcher = BIN_ROOT / "scrcpy-phoneview"
        if launcher.is_symlink() or launcher.exists():
            launcher.unlink()

        lib_dir = ScrcpyInstaller.target_root() / "lib"
        launcher.write_text(
            "#!/bin/sh\n"
            'SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"\n'
            f'export LD_LIBRARY_PATH="{lib_dir}:$LD_LIBRARY_PATH"\n'
            f'exec "{target_binary}" "$@"\n',
            encoding="utf-8",
        )
        launcher.chmod(0o755)

    @staticmethod
    def _prepare_local_sdl(source_root, env, emit):
        if ScrcpyInstaller._pkg_config_has_sdl3(env):
            emit("✓ SDL3 development files are already available.")
            return env, None

        sdl_script = source_root / "app" / "deps" / "sdl.sh"
        if not sdl_script.is_file():
            raise RuntimeError(f"Vendored SDL3 build script is missing: {sdl_script}")

        emit("↓ System SDL3 development files are unavailable.")
        emit("↓ Building pinned SDL3 3.4.12 locally.")

        for command in ("bash", "cmake", "wget", "tar", "shasum"):
            ScrcpyInstaller._require_command(command)

        ScrcpyInstaller._run(
            ["bash", str(sdl_script), "linux", "native", "shared"],
            cwd=sdl_script.parent,
            env=env,
            emit=emit,
        )

        local_install = source_root / SDL_INSTALL_RELATIVE
        pkgconfig = local_install / "lib" / "pkgconfig"
        local_env = env.copy()
        old_pkg = local_env.get("PKG_CONFIG_PATH", "")
        local_env["PKG_CONFIG_PATH"] = f"{pkgconfig}:{old_pkg}" if old_pkg else str(pkgconfig)

        if not ScrcpyInstaller._pkg_config_has_sdl3(local_env):
            raise RuntimeError("Local SDL3 was built, but pkg-config cannot find it.")

        emit(f"✓ Local SDL3 ready: {local_install}")
        return local_env, local_install

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
            raise RuntimeError("The PhoneView scrcpy build currently supports Linux only.")

        machine = platform.machine().lower()
        if machine not in ("x86_64", "amd64"):
            raise RuntimeError(
                f"PhoneView scrcpy 4.1 is currently prepared for Linux x86_64, not {machine}."
            )

        for command in ("python3", "meson", "ninja", "gcc", "pkg-config", "tar"):
            ScrcpyInstaller._require_command(command)

        if not VENDORED_ROOT.is_dir():
            raise RuntimeError(f"Vendored scrcpy source was not found at: {VENDORED_ROOT}")

        required_source = (
            VENDORED_ROOT / "meson.build",
            VENDORED_ROOT / "app" / "meson.build",
            VENDORED_ROOT / "app" / "src" / "screen.c",
            VENDORED_ROOT / "app" / "src" / "screen.h",
            VENDORED_ROOT / "server" / "meson.build",
        )
        missing = [str(p) for p in required_source if not p.is_file()]
        if missing:
            raise RuntimeError("Vendored scrcpy source tree is incomplete. Missing: " + ", ".join(missing))

        target_root = ScrcpyInstaller.target_root()
        target_binary = target_root / "bin" / "scrcpy"
        target_server = target_root / "share" / "scrcpy" / "scrcpy-server"
        if (
            target_binary.is_file()
            and os.access(target_binary, os.X_OK)
            and target_server.is_file()
            and target_server.stat().st_size > 0
        ):
            ScrcpyInstaller._install_launcher(target_binary)
            emit(f"✓ PhoneView scrcpy {PHONEVIEW_BUILD_NAME} is already installed.")
            set_progress(100)
            return str(target_binary)

        if target_root.exists():
            emit("↓ Existing PhoneView scrcpy installation is incomplete; rebuilding it.")
            shutil.rmtree(target_root)

        INSTALL_ROOT.mkdir(parents=True, exist_ok=True)
        BIN_ROOT.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()

        with tempfile.TemporaryDirectory(prefix="phoneview-scrcpy-build-") as temp:
            temp_root = Path(temp)
            source_root = temp_root / "source"
            build_root = temp_root / "build"
            server_file = temp_root / "scrcpy-server"

            emit(f"Using vendored scrcpy {PHONEVIEW_SCRCPY_VERSION} source.")
            shutil.copytree(
                VENDORED_ROOT,
                source_root,
                ignore=shutil.ignore_patterns("work", "__pycache__", "*.pyc"),
            )
            set_progress(8)

            env, local_sdl_install = ScrcpyInstaller._prepare_local_sdl(
                source_root, env, emit
            )
            set_progress(25)

            emit("Downloading the matching scrcpy 4.1 Android server...")
            request = urllib.request.Request(
                SERVER_URL,
                headers={"User-Agent": "PhoneView"},
            )
            with urllib.request.urlopen(request, timeout=30) as response, server_file.open("wb") as output:
                shutil.copyfileobj(response, output)

            digest = hashlib.sha256(server_file.read_bytes()).hexdigest().lower()
            if digest != SERVER_SHA256:
                raise RuntimeError("scrcpy-server SHA-256 verification failed.")
            emit("✓ Matching scrcpy-server checksum verified.")
            set_progress(40)

            target_root.mkdir(parents=True, exist_ok=True)
            ScrcpyInstaller._run(
                [
                    "meson",
                    "setup",
                    str(build_root),
                    "--buildtype=release",
                    "--strip",
                    "-Db_lto=true",
                    "-Dv4l2=false",
                    "-Dusb=false",
                    f"-Dprebuilt_server={server_file}",
                    f"--prefix={target_root}",
                ],
                cwd=source_root,
                env=env,
                emit=emit,
            )
            set_progress(58)

            emit("Compiling PhoneView scrcpy 4.1...")
            ScrcpyInstaller._run(
                ["ninja", "-C", str(build_root)],
                cwd=source_root,
                env=env,
                emit=emit,
            )
            set_progress(78)

            emit("Installing the patched scrcpy engine...")
            ScrcpyInstaller._run(
                ["ninja", "-C", str(build_root), "install"],
                cwd=source_root,
                env=env,
                emit=emit,
            )

            if local_sdl_install and local_sdl_install.is_dir():
                target_lib = target_root / "lib"
                target_lib.mkdir(parents=True, exist_ok=True)
                for item in (local_sdl_install / "lib").glob("libSDL3.so*"):
                    shutil.copy2(item, target_lib / item.name)

            license_file = source_root / "LICENSE"
            if license_file.is_file():
                shutil.copy2(license_file, target_root / "SCRCPY-LICENSE.txt")

        target_binary = target_root / "bin" / "scrcpy"
        if not target_binary.is_file():
            raise RuntimeError("The patched scrcpy build completed, but the executable was not found.")

        target_binary.chmod(
            target_binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        )

        ScrcpyInstaller._install_launcher(target_binary)

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
