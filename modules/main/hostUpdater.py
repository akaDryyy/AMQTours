from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path


class HostScriptUpdater:
    """Checks for and installs host-script updates without depending on the UI."""

    def __init__(self, project_root, version_path, repo="akaDryyy/AMQTours", branch="main"):
        self.project_root = Path(project_root)
        self.version_path = Path(version_path)
        self.repo = repo
        self.branch = branch
        self.commit_api_url = f"https://api.github.com/repos/{repo}/commits/{branch}"
        self.zip_url = f"https://github.com/{repo}/archive/refs/heads/{branch}.zip"

    def run_git(self, args, timeout=25):
        return subprocess.run(
            ["git", *args],
            cwd=self.project_root,
            text=True,
            capture_output=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def has_git_updater(self):
        return bool(shutil.which("git") and (self.project_root / ".git").exists())

    def github_main_sha(self):
        request = urllib.request.Request(
            self.commit_api_url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "AMQ-Host-Script",
            },
        )
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return str(payload.get("sha", "")).strip()

    def local_zip_version_sha(self):
        try:
            with self.version_path.open(encoding="utf-8") as file:
                payload = json.load(file)
            return str(payload.get("github_main_sha", "")).strip()
        except (OSError, json.JSONDecodeError):
            return ""

    def zip_version_state(self):
        local = self.local_zip_version_sha()
        try:
            remote = self.github_main_sha()
        except urllib.error.HTTPError as exc:
            return {
                "status": "update_available",
                "local": local,
                "remote": "",
                "message": f"Host Script version check unavailable ({exc.code}); update anyway",
                "updater": "zip",
            }
        except Exception:
            return {
                "status": "update_available",
                "local": local,
                "remote": "",
                "message": "Host Script version check unavailable; update anyway",
                "updater": "zip",
            }
        if not remote:
            return {
                "status": "update_available",
                "local": local,
                "remote": remote,
                "message": "Host Script version check unavailable; update anyway",
                "updater": "zip",
            }
        if local and local == remote:
            return {
                "status": "up_to_date",
                "local": local,
                "remote": remote,
                "message": "Host Script is up to date",
                "updater": "zip",
            }
        return {
            "status": "update_available",
            "local": local,
            "remote": remote,
            "message": "Host Script update available",
            "updater": "zip",
        }

    def check_version(self):
        try:
            if not self.has_git_updater():
                return self.zip_version_state()

            fetch_result = self.run_git(["fetch", "--quiet", "origin", self.branch], timeout=45)
            if fetch_result.returncode != 0:
                raise RuntimeError(fetch_result.stderr.strip() or fetch_result.stdout.strip() or "git fetch failed")
            local_result = self.run_git(["rev-parse", "HEAD"])
            remote_result = self.run_git(["rev-parse", f"origin/{self.branch}"])
            local = local_result.stdout.strip()
            remote = remote_result.stdout.strip()
            if local_result.returncode != 0 or remote_result.returncode != 0 or not local or not remote:
                return {
                    "status": "unknown",
                    "local": local,
                    "remote": remote,
                    "message": "Host Script version could not be checked",
                }
            if local == remote or self.run_git(["merge-base", "--is-ancestor", f"origin/{self.branch}", "HEAD"]).returncode == 0:
                return {
                    "status": "up_to_date",
                    "local": local,
                    "remote": remote,
                    "message": "Host Script is up to date",
                    "updater": "git",
                }
            if self.run_git(["merge-base", "--is-ancestor", "HEAD", f"origin/{self.branch}"]).returncode == 0:
                return {
                    "status": "update_available",
                    "local": local,
                    "remote": remote,
                    "message": "Host Script update available",
                    "updater": "git",
                }
            return {
                "status": "unknown",
                "local": local,
                "remote": remote,
                "message": "Host Script differs from GitHub main",
                "updater": "git",
            }
        except Exception as exc:
            return {
                "status": "unknown",
                "local": "",
                "remote": "",
                "message": f"Host Script version could not be checked: {type(exc).__name__}",
            }

    def install_update(self):
        if self.has_git_updater():
            return self.update_from_git()
        return self.prepare_zip_update()

    def update_from_git(self):
        fetch = self.run_git(["fetch", "origin", self.branch], timeout=60)
        if fetch.returncode != 0:
            raise RuntimeError(fetch.stderr.strip() or fetch.stdout.strip() or "git fetch failed")
        pull = self.run_git(["pull", "--ff-only", "origin", self.branch], timeout=90)
        if pull.returncode != 0:
            raise RuntimeError(pull.stderr.strip() or pull.stdout.strip() or "git pull failed")
        return "Host Script updated. Restart the script to use the newest version."

    def prepare_zip_update(self):
        try:
            remote_sha = self.github_main_sha()
        except Exception:
            remote_sha = ""

        temp_root = Path(tempfile.mkdtemp(prefix="amqtours_update_"))
        zip_path = temp_root / "amqtours_main.zip"
        extract_root = temp_root / "extracted"
        request = urllib.request.Request(self.zip_url, headers={"User-Agent": "AMQ-Host-Script"})
        with urllib.request.urlopen(request, timeout=60) as response:
            zip_path.write_bytes(response.read())
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_root)

        candidates = [path for path in extract_root.iterdir() if path.is_dir()]
        if not candidates:
            raise RuntimeError("Downloaded update package was empty.")
        package_root = candidates[0]
        version_path = package_root / "config" / "host_script_version.json"
        version_path.parent.mkdir(parents=True, exist_ok=True)
        version_path.write_text(
            json.dumps(
                {
                    "github_main_sha": remote_sha,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "source": "zip",
                    "source_url": self.zip_url,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        self._start_zip_update_process(package_root, temp_root)
        return "Update downloaded. Close the host script to finish installing it."

    def _start_zip_update_process(self, package_root, temp_root):
        runner_path = temp_root / "finish_amqtours_update.py"
        runner_path.write_text(self._runner_script(), encoding="utf-8")
        subprocess.Popen(
            [
                sys.executable,
                str(runner_path),
                str(os.getpid()),
                str(package_root),
                str(self.project_root),
                str(temp_root),
            ],
            cwd=str(temp_root),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    @staticmethod
    def _runner_script():
        return r'''
from __future__ import annotations

import ctypes
import os
import shutil
import sys
import time
import traceback
from pathlib import Path


def wait_for_process(pid: int):
    if os.name == "nt":
        synchronize = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(synchronize, False, pid)
        if handle:
            try:
                ctypes.windll.kernel32.WaitForSingleObject(handle, 0xFFFFFFFF)
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
            return
    while True:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(1)


def copy_update(source: Path, target: Path, temp_root: Path):
    if not source.exists():
        raise FileNotFoundError(f"Update source not found: {source}")
    if not target.exists():
        raise FileNotFoundError(f"Update target not found: {target}")

    ui_settings = target / "config" / "ui_settings.json"
    ui_backup = temp_root / "ui_settings.backup.json"
    if ui_settings.exists():
        ui_backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ui_settings, ui_backup)

    skip_top_level = {".git", "credentials", "__pycache__"}
    ignore = shutil.ignore_patterns("__pycache__")
    for item in source.iterdir():
        if item.name in skip_top_level:
            continue
        destination = target / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True, ignore=ignore)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)

    if ui_backup.exists():
        ui_settings.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ui_backup, ui_settings)

    version_source = source / "config" / "host_script_version.json"
    version_target = target / "config" / "host_script_version.json"
    if version_source.exists():
        version_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(version_source, version_target)


def main():
    pid = int(sys.argv[1])
    source = Path(sys.argv[2])
    target = Path(sys.argv[3])
    temp_root = Path(sys.argv[4])
    log_path = temp_root / "amqtours_update.log"
    try:
        wait_for_process(pid)
        copy_update(source, target, temp_root)
        shutil.rmtree(temp_root, ignore_errors=True)
    except Exception:
        log_path.write_text(traceback.format_exc(), encoding="utf-8")


if __name__ == "__main__":
    main()
'''
