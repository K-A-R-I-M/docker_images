import os
import subprocess
import urllib.request

SERVER_DIR = "/app/data"
MODS_ZIP = "/app/data/mods.zip"

NEOFORGE_VERSION = "21.8.52" # 1.21.8
INSTALLER_URL = f"https://maven.neoforged.net/releases/net/neoforged/neoforge/{NEOFORGE_VERSION}/neoforge-{NEOFORGE_VERSION}-installer.jar"

INSTALLER_FILE = f"{SERVER_DIR}/neoforge-installer.jar"


def run(cmd):
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True, check=True)


def download_neoforge():
    if os.path.exists(INSTALLER_FILE):
        print("NeoForge installer already exists.")
        return

    print("Downloading NeoForge installer...")
    urllib.request.urlretrieve(INSTALLER_URL, INSTALLER_FILE)
    print("Download complete.")


def install_server():
    print("Installing NeoForge server...")
    run(f"cd {SERVER_DIR} && java -jar neoforge-installer.jar --installServer")


def accept_eula():
    eula_path = os.path.join(SERVER_DIR, "eula.txt")

    with open(eula_path, "w") as f:
        f.write("eula=true\n")

    print("EULA accepted.")


def manage_mods():
    mods_dir = os.path.join(SERVER_DIR, "mods")
    marker = os.path.join(mods_dir, ".mods_extracted")

    os.makedirs(mods_dir, exist_ok=True)

    if not os.path.exists(MODS_ZIP):
        print("No mods.zip found.")
        return

    if os.path.exists(marker):
        print("Mods already installed.")
        return

    print("Extracting mods...")

    run(f"unzip -o {MODS_ZIP} -d {mods_dir}")

    open(marker, "w").close()


def start_server():
    print("Starting server...")

    run(f"""
    cd {SERVER_DIR} &&
    java -Xms4G -Xmx6G \
    @user_jvm_args.txt \
    @libraries/net/neoforged/neoforge/*/unix_args.txt \
    nogui
    """)


def main():
    os.makedirs(SERVER_DIR, exist_ok=True)

    download_neoforge()
    install_server()
    accept_eula()
    manage_mods()
    start_server()


if __name__ == "__main__":
    main()