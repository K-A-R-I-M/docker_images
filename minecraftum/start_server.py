#!/usr/bin/env python3
import requests
import subprocess
import os
import sys

JAVA = "java"
RAM = os.environ.get("RAM", "8G")

MC_MANIFEST = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
FORGE_PROMO = "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json"


def get_latest_mc():
    r = requests.get(MC_MANIFEST)
    r.raise_for_status()
    return r.json()["latest"]["release"]


def get_latest_forge(mc_version):
    r = requests.get(FORGE_PROMO)
    r.raise_for_status()
    promos = r.json()["promos"]

    if f"{mc_version}-recommended" in promos:
        return promos[f"{mc_version}-recommended"]

    if f"{mc_version}-latest" in promos:
        return promos[f"{mc_version}-latest"]

    print(f"No Forge version available for Minecraft {mc_version}")
    sys.exit(1)


def download_installer(mc_version, forge_version):
    forge_full = f"{mc_version}-{forge_version}"
    installer = f"forge-{forge_full}-installer.jar"

    if os.path.exists(installer):
        return installer

    url = (
        f"https://maven.minecraftforge.net/net/minecraftforge/forge/"
        f"{forge_full}/{installer}"
    )

    print(f"Downloading Forge installer: {forge_full}")
    r = requests.get(url)
    r.raise_for_status()

    with open(installer, "wb") as f:
        f.write(r.content)

    return installer


def install_if_needed(installer):
    if not os.path.exists("run.sh"):
        print("Installing Forge server...")
        subprocess.run([JAVA, "-jar", installer, "--installServer"], check=True)
    else:
        print("Forge already installed. Skipping install.")


def accept_eula():
    if not os.path.exists("eula.txt") or "true" not in open("eula.txt").read():
        print("Accepting EULA...")
        with open("eula.txt", "w") as f:
            f.write("eula=true\n")

def args_update():
    with open("user_jvm_args.txt", "w") as f:
        f.write(f"-Xms1G\n-Xmx{RAM}\n")

def version_k(mc_version, forge_version):
    with open("version_k", "w+") as f:
        f.write(f"{mc_version}\n{forge_version}\n")

import zipfile
import shutil

def manage_mods():
    """
    Ensures mods folder exists and extracts /opt/mine/mods.zip
    into mods/ if present. Safe to run multiple times.
    """

    mods_dir = "mods"
    zip_path = "/mods.zip"
    marker_file = ".mods_extracted"

    # Create mods directory if missing
    os.makedirs(mods_dir, exist_ok=True)

    # If no zip file provided, skip silently
    if not os.path.exists(zip_path):
        print("No mods.zip found at /opt/mine. Skipping mod setup.")
        return

    # If already extracted, skip
    if os.path.exists(os.path.join(mods_dir, marker_file)):
        print("Mods already extracted. Skipping.")
        return

    print("Extracting mods.zip into mods/ ...")

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(mods_dir)

        # Create marker to avoid re-extracting every time
        with open(os.path.join(mods_dir, marker_file), "w") as f:
            f.write("ok")

        print("Mods installed successfully.")

    except zipfile.BadZipFile:
        print("ERROR: mods.zip is not a valid zip file.")
        raise


def start_server():
    print("Starting Forge server...")
    # Use sh explicitly (important in Alpine/Docker)
    subprocess.run(["sh", "./run.sh"], check=True)


def main():
    print("Fetching latest versions...")

    # Lock version tempo
    # mc_version = get_latest_mc()
    # forge_version = get_latest_forge(mc_version)

    mc_version = "1.21.8"
    forge_version = "58.1.0"


    print(f"Minecraft version: {mc_version}")
    print(f"Forge version: {forge_version}")

    installer = download_installer(mc_version, forge_version)
    install_if_needed(installer)
    accept_eula()
    args_update()
    version_k(mc_version, forge_version)
    start_server()


if __name__ == "__main__":
    main()