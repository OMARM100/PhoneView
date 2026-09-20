import hashlib
import os
import platform
import shutil
import stat
import subprocess
import sys
import urllib.request
from pathlib import Path


PHONEVIEW_SCRCPY_VERSION = "v4.1"
PHONEVIEW_BUILD_NAME = "v4.1-phoneview-native-toolbar"

INSTALL_ROOT = Path.home() / ".local" / "share" / "phoneview" / "scrcpy"
BIN_ROOT = Path.home() / ".local" / "bin"

CACHE_ROOT = (
    Path.home()
    / ".cache"
    / "phoneview"
    / "scrcpy"
    / PHONEVIEW_BUILD_NAME
)
SOURCE_CACHE_ROOT = CACHE_ROOT / "source"
BUILD_CACHE_ROOT = CACHE_ROOT / "build"
SERVER_CACHE_ROOT = CACHE_ROOT / "server"

SERVER_URL = (
    "https://github.com/Genymobile/scrcpy/releases/download/"
    f"{PHONEVIEW_SCRCPY_VERSION}/scrcpy-server-{PHONEVIEW_SCRCPY_VERSION}"
)
SERVER_SHA256 = "deacb991ed2509715160ffdc7907e47b4160eb30d1566217e9047fd5b8850cae"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDORED_ROOT = PROJECT_ROOT / "vendor" / "scrcpy" / PHONEVIEW_SCRCPY_VERSION
SDL_INSTALL_RELATIVE = Path("app") / "deps" / "work" / "install" / "linux-native-shared"
SDL_CACHE_VERSION = "3.4.12"
SDL_CACHE_ROOT = (
    Path.home()
    / ".cache"
    / "phoneview"
    / "sdl3"
    / SDL_CACHE_VERSION
    / "linux-native-shared"
)


class ScrcpyInstaller:
    """Build and install PhoneView's pinned, patched scrcpy 4.1 engine."""

    @staticmethod
    def target_root():
        return INSTALL_ROOT / PHONEVIEW_BUILD_NAME

    @staticmethod
    def local_binary():
        path = ScrcpyInstaller.target_root() / "bin" / "scrcpy"
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
        return None

    @staticmethod
    def find_binary():
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
    def _source_stamp():
        digest = hashlib.sha256()
        digest.update(PHONEVIEW_BUILD_NAME.encode("utf-8"))
        digest.update(b"\\0")

        ignored = {"work", "__pycache__", ".git"}
        for path in sorted(VENDORED_ROOT.rglob("*")):
            if not path.is_file():
                continue
            try:
                relative = path.relative_to(VENDORED_ROOT)
            except ValueError:
                continue
            if any(part in ignored for part in relative.parts):
                continue
            digest.update(str(relative).encode("utf-8"))
            digest.update(b"\\0")
            digest.update(path.read_bytes())
            digest.update(b"\\0")

        return digest.hexdigest()

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
        BIN_ROOT.mkdir(parents=True, exist_ok=True)
        launcher = BIN_ROOT / "scrcpy-phoneview"
        if launcher.is_symlink() or launcher.exists():
            launcher.unlink()

        lib_dir = ScrcpyInstaller.target_root() / "lib"
        launcher.write_text(
            "#!/bin/sh\n"
            'export LD_LIBRARY_PATH="' + str(lib_dir) + ':$LD_LIBRARY_PATH"\n'
            'exec "' + str(target_binary) + '" "$@"\n',
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

        pkgconfig = SDL_CACHE_ROOT / "lib" / "pkgconfig"
        cached_env = env.copy()
        old_pkg = cached_env.get("PKG_CONFIG_PATH", "")
        cached_env["PKG_CONFIG_PATH"] = (
            f"{pkgconfig}:{old_pkg}" if old_pkg else str(pkgconfig)
        )

        if (
            (pkgconfig / "sdl3.pc").is_file()
            and any(SDL_CACHE_ROOT.glob("lib/libSDL3.so*"))
            and ScrcpyInstaller._pkg_config_has_sdl3(cached_env)
        ):
            emit(f"✓ Cached SDL3 {SDL_CACHE_VERSION} is ready.")
            return cached_env, SDL_CACHE_ROOT

        emit("↓ System SDL3 development files are unavailable.")
        emit(
            f"↓ Building pinned SDL3 {SDL_CACHE_VERSION} locally "
            "(cached for future builds)."
        )

        for command in ("bash", "cmake", "wget", "tar", "shasum"):
            ScrcpyInstaller._require_command(command)

        ScrcpyInstaller._run(
            ["bash", str(sdl_script), "linux", "native", "shared"],
            cwd=sdl_script.parent,
            env=env,
            emit=emit,
        )

        local_install = source_root / SDL_INSTALL_RELATIVE
        local_pkgconfig = local_install / "lib" / "pkgconfig"
        local_env = env.copy()
        old_pkg = local_env.get("PKG_CONFIG_PATH", "")
        local_env["PKG_CONFIG_PATH"] = (
            f"{local_pkgconfig}:{old_pkg}"
            if old_pkg
            else str(local_pkgconfig)
        )

        if not ScrcpyInstaller._pkg_config_has_sdl3(local_env):
            raise RuntimeError(
                "Local SDL3 was built, but pkg-config cannot find it."
            )

        if SDL_CACHE_ROOT.exists():
            shutil.rmtree(SDL_CACHE_ROOT)
        SDL_CACHE_ROOT.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(local_install, SDL_CACHE_ROOT)

        cached_env = env.copy()
        old_pkg = cached_env.get("PKG_CONFIG_PATH", "")
        cached_env["PKG_CONFIG_PATH"] = (
            f"{pkgconfig}:{old_pkg}" if old_pkg else str(pkgconfig)
        )

        emit(f"✓ Cached SDL3 {SDL_CACHE_VERSION} is ready.")
        return cached_env, SDL_CACHE_ROOT

    @staticmethod
    def _prepare_server():
        SERVER_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
        server_file = SERVER_CACHE_ROOT / (
            f"scrcpy-server-{PHONEVIEW_SCRCPY_VERSION}"
        )

        if server_file.is_file():
            digest = hashlib.sha256(server_file.read_bytes()).hexdigest().lower()
            if digest == SERVER_SHA256:
                return server_file

        request = urllib.request.Request(
            SERVER_URL,
            headers={"User-Agent": "PhoneView"},
        )
        with urllib.request.urlopen(request, timeout=30) as response, server_file.open(
            "wb"
        ) as output:
            shutil.copyfileobj(response, output)

        digest = hashlib.sha256(server_file.read_bytes()).hexdigest().lower()
        if digest != SERVER_SHA256:
            server_file.unlink(missing_ok=True)
            raise RuntimeError("scrcpy-server SHA-256 verification failed.")

        return server_file

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
                f"PhoneView scrcpy 4.1 is currently prepared for Linux x86_64, not {machine}."
            )

        for command in ("python3", "meson", "ninja", "gcc", "pkg-config", "tar"):
            ScrcpyInstaller._require_command(command)

        try:
            gtk_check = subprocess.run(
                ["pkg-config", "--atleast-version=3.20", "gtk+-3.0"],
                capture_output=True,
                text=True,
                timeout=5,
                env=os.environ.copy(),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(
                "Could not check GTK3 development files with pkg-config."
            ) from exc

        if gtk_check.returncode != 0:
            raise RuntimeError(
                "PhoneView's native toolbar requires GTK3 development files. "
                "Install the package providing gtk+-3.0 (for example libgtk-3-dev) "
                "then run setup again."
            )

        if not VENDORED_ROOT.is_dir():
            raise RuntimeError(
                f"Vendored scrcpy source was not found at: {VENDORED_ROOT}"
            )

        source_stamp = ScrcpyInstaller._source_stamp()
        target_root = ScrcpyInstaller.target_root()
        target_binary = target_root / "bin" / "scrcpy"
        target_server = target_root / "share" / "scrcpy" / "scrcpy-server"
        target_stamp = target_root / ".phoneview-source-stamp"

        if (
            target_binary.is_file()
            and os.access(target_binary, os.X_OK)
            and target_server.is_file()
            and target_server.stat().st_size > 0
            and target_stamp.is_file()
            and target_stamp.read_text(encoding="utf-8").strip() == source_stamp
        ):
            ScrcpyInstaller._install_launcher(target_binary)
            emit(
                f"✓ PhoneView scrcpy {PHONEVIEW_BUILD_NAME} is up to date; "
                "skipping build."
            )
            set_progress(100)
            return str(target_binary)

        CACHE_ROOT.mkdir(parents=True, exist_ok=True)
        SOURCE_CACHE_ROOT.parent.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()

        emit(f"Using vendored scrcpy {PHONEVIEW_SCRCPY_VERSION} source.")

        shutil.copytree(
            VENDORED_ROOT,
            SOURCE_CACHE_ROOT,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("work", "__pycache__", "*.pyc"),
        )
        set_progress(10)

        env, local_sdl_install = ScrcpyInstaller._prepare_local_sdl(
            SOURCE_CACHE_ROOT,
            env,
            emit,
        )
        set_progress(25)

        server_file = ScrcpyInstaller._prepare_server()
        emit("✓ Matching scrcpy-server checksum verified.")
        set_progress(40)

        target_root.mkdir(parents=True, exist_ok=True)
        meson_private = BUILD_CACHE_ROOT / "meson-private"
        if meson_private.is_dir():
            emit("✓ Reusing incremental Meson/Ninja build cache.")
            meson_command = [
                "meson",
                "setup",
                "--reconfigure",
                str(BUILD_CACHE_ROOT),
            ]
        else:
            emit("↓ Creating the cached scrcpy build tree.")
            meson_command = [
                "meson",
                "setup",
                str(BUILD_CACHE_ROOT),
            ]

        meson_command += [
            "--buildtype=release",
            "--strip",
            "-Db_lto=false",
            "-Dv4l2=false",
            "-Dusb=false",
            f"-Dprebuilt_server={server_file}",
            f"--prefix={target_root}",
        ]

        ScrcpyInstaller._run(
            meson_command,
            cwd=SOURCE_CACHE_ROOT,
            env=env,
            emit=emit,
        )
        set_progress(58)

        emit("Compiling only changed PhoneView/scrcpy files...")
        ScrcpyInstaller._run(
            ["ninja", "-C", str(BUILD_CACHE_ROOT)],
            cwd=SOURCE_CACHE_ROOT,
            env=env,
            emit=emit,
        )
        set_progress(78)

        emit("Installing the patched scrcpy engine...")
        ScrcpyInstaller._run(
            ["ninja", "-C", str(BUILD_CACHE_ROOT), "install"],
            cwd=SOURCE_CACHE_ROOT,
            env=env,
            emit=emit,
        )

        if local_sdl_install and local_sdl_install.is_dir():
            target_lib = target_root / "lib"
            target_lib.mkdir(parents=True, exist_ok=True)
            for item in (local_sdl_install / "lib").glob("libSDL3.so*"):
                shutil.copy2(item, target_lib / item.name)

        license_file = SOURCE_CACHE_ROOT / "LICENSE"
        if license_file.is_file():
            shutil.copy2(license_file, target_root / "SCRCPY-LICENSE.txt")

        if not target_binary.is_file():
            raise RuntimeError(
                "The patched scrcpy build completed, but the executable was not found."
            )

        target_stamp.write_text(source_stamp + "\n", encoding="utf-8")
        target_binary.chmod(
            target_binary.stat().st_mode
            | stat.S_IXUSR
            | stat.S_IXGRP
            | stat.S_IXOTH
        )

        ScrcpyInstaller._install_launcher(target_binary)

        emit(f"✓ PhoneView scrcpy {PHONEVIEW_BUILD_NAME} installed.")
        emit("✓ Future upstream scrcpy releases will NOT replace this build.")
        emit("✓ Future PhoneView source edits will use incremental builds.")
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
