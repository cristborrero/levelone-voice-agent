"""Deploy script — builds a clean zip and uploads it to the VPS via SSH."""
from __future__ import annotations

import io
import os
import sys
import zipfile
from pathlib import Path

import paramiko
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

load_dotenv()

VPS_IP = os.environ["VPS_IP"]
VPS_USER = os.environ["VPS_USER"]
VPS_PASS = os.environ["VPS_PASSWORD"]
DEPLOY_DIR = "/opt/voice-agent"

ROOT = Path(__file__).parent

INCLUDE_DIRS = ["app", "config", "infra"]
INCLUDE_FILES = ["pyproject.toml"]

EXCLUDE_PATTERNS = {
    "__pycache__",
    ".venv",
    ".git",
    "tests",
    ".atl",
    ".env",
    "deploy.zip",
    "deploy_vps.py",
    "uv.lock",
}


# ---------------------------------------------------------------------------
# Zip builder
# ---------------------------------------------------------------------------

def _should_exclude(path: Path) -> bool:
    return any(part in EXCLUDE_PATTERNS for part in path.parts)


def build_zip() -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for dir_name in INCLUDE_DIRS:
            for file in (ROOT / dir_name).rglob("*"):
                if file.is_file() and not _should_exclude(file.relative_to(ROOT)):
                    zf.write(file, file.relative_to(ROOT))
        for fname in INCLUDE_FILES:
            p = ROOT / fname
            if p.exists():
                zf.write(p, fname)
        # Always include .env so the VPS has the runtime config
        env_file = ROOT / ".env"
        if env_file.exists():
            zf.write(env_file, ".env")
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Deploy
# ---------------------------------------------------------------------------

def main() -> None:
    print("Building deploy zip…")
    zip_buf = build_zip()
    zip_size = zip_buf.getbuffer().nbytes
    print(f"  {zip_size / 1024:.1f} KB")

    print(f"Connecting to {VPS_USER}@{VPS_IP}…")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(VPS_IP, username=VPS_USER, password=VPS_PASS)
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    print("Uploading…")
    sftp = ssh.open_sftp()
    sftp.putfo(zip_buf, "/root/deploy.zip")
    sftp.close()

    commands = [
        f"mkdir -p {DEPLOY_DIR}/data",
        "apt-get install -y unzip python3-venv -qq",
        f"unzip -o /root/deploy.zip -d {DEPLOY_DIR}",
        f"cd {DEPLOY_DIR} && python3 -m venv .venv",
        (
            f"cd {DEPLOY_DIR} && .venv/bin/pip install -q "
            "httpx fastapi 'uvicorn[standard]' pydantic-settings pydantic "
            "websockets pyyaml structlog tenacity python-dotenv resend "
            "python-dateutil openai groq paramiko "
            "'livekit-agents>=0.8.0' livekit-plugins-openai livekit-plugins-cartesia"
        ),
        f"cp {DEPLOY_DIR}/infra/voice-agent.service /etc/systemd/system/",
        f"cp {DEPLOY_DIR}/infra/voice-webhook.service /etc/systemd/system/",
        "systemctl daemon-reload",
        "systemctl enable voice-agent voice-webhook",
        "systemctl restart voice-agent voice-webhook",
        "rm /root/deploy.zip",
    ]

    for cmd in commands:
        label = cmd[:70] + ("…" if len(cmd) > 70 else "")
        print(f"  → {label}")
        _, stdout, stderr = ssh.exec_command(cmd)
        status = stdout.channel.recv_exit_status()
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        if status != 0:
            print(f"    ERROR (exit {status}):")
            if err:
                print(f"    {err}")
            ssh.close()
            sys.exit(1)
        if out:
            print(f"    {out}")

    print("\nChecking service status…")
    _, stdout, _ = ssh.exec_command(
        "systemctl is-active voice-agent voice-webhook"
    )
    print(stdout.read().decode().strip())

    ssh.close()
    print("\nDeploy complete.")


if __name__ == "__main__":
    main()
