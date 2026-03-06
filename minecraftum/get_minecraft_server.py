#!/usr/bin/env python3
import requests
import subprocess
import os
import glob

JAVA = "java"
RAM = "12G"

MC_VERSION = "1.20.1"
FORGE_VERSION = "47.2.0"

INSTALLER = f"forge-{MC_VERSION}-{FORGE_VERSION}-installer.jar"
FORGE_SERVER_PATTERN = f"forge-{MC_VERSION}-{FORGE_VERSION}-*.jar"

installer_url = (
    f"https://maven.minecraftforge.net/net/minecraftforge/forge/"
    f"{MC_VERSION}-{FORGE_VERSION}/"
    f"{INSTALLER}"
)

# Step 1 — Download installer if missing
if not os.path.exists(INSTALLER):
    print("Downloading Forge installer...")
    r = requests.get(installer_url)
    r.raise_for_status()
    open(INSTALLER, "wb").write(r.content)

# Step 2 — Check if Forge server already installed
forge_server_jars = [
    f for f in glob.glob(FORGE_SERVER_PATTERN)
    if "installer" not in f
]

if not forge_server_jars:
    print("Forge not installed. Installing...")
    subprocess.run([JAVA, "-jar", INSTALLER, "--installServer"], check=True)
else:
    print("Forge already installed. Skipping install.")

# Step 3 — Accept EULA automatically
if not os.path.exists("eula.txt") or "true" not in open("eula.txt").read():
    print("Accepting EULA...")
    with open("eula.txt", "w") as f:
        f.write("eula=true\n")

# Step 4 — Find Forge server jar
forge_server_jars = [
    f for f in glob.glob(FORGE_SERVER_PATTERN)
    if "installer" not in f
]

if not forge_server_jars:
    raise Exception("Forge server jar not found after install")

forge_server = forge_server_jars[0]

# Step 5 — Start server
print(f"Starting server: {forge_server}")
subprocess.run([JAVA, f"-Xmx{RAM}", "-jar", forge_server, "nogui"])
