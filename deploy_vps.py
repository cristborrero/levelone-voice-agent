import paramiko
import os
import sys

VPS_IP = "31.220.72.170"
VPS_USER = "root"
VPS_PASS = "Ez!9zhyfm8j9gRGm"
DEPLOY_DIR = "/opt/voice-agent"

print("Connecting to VPS...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    ssh.connect(VPS_IP, username=VPS_USER, password=VPS_PASS)
except Exception as e:
    print(f"Failed to connect: {e}")
    sys.exit(1)

print("Connected. Uploading deploy.zip...")
sftp = ssh.open_sftp()
sftp.put("deploy.zip", "/root/deploy.zip")
sftp.close()

print("Executing deployment commands on VPS...")
commands = [
    f"mkdir -p {DEPLOY_DIR}/data",
    f"apt-get update && apt-get install -y unzip python3-venv",
    f"unzip -o /root/deploy.zip -d {DEPLOY_DIR}",
    f"cd {DEPLOY_DIR} && python3 -m venv .venv",
    f"cd {DEPLOY_DIR} && .venv/bin/pip install httpx fastapi 'uvicorn[standard]' pydantic-settings websockets",
    f"cd {DEPLOY_DIR} && .venv/bin/pip install 'livekit-agents>=0.8.0' 'livekit-plugins-openai' 'livekit-plugins-cartesia' 'tenacity' 'twilio' 'pyyaml'",
    f"cp {DEPLOY_DIR}/infra/voice-agent.service /etc/systemd/system/",
    f"cp {DEPLOY_DIR}/infra/voice-webhook.service /etc/systemd/system/",
    f"systemctl daemon-reload",
    f"systemctl enable voice-agent voice-webhook",
    f"systemctl restart voice-agent voice-webhook",
    "rm /root/deploy.zip"
]

for cmd in commands:
    print(f"Running: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        print(f"Error executing {cmd}:\n{stderr.read().decode()}")
    else:
        print(stdout.read().decode().strip())

ssh.close()
print("Deployment complete!")
