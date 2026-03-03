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


def start_server():
    print("Starting Forge server...")
    # Use sh explicitly (important in Alpine/Docker)
    subprocess.run(["sh", "./run.sh"], check=True)


def main():
    print("Fetching latest versions...")

    mc_version = get_latest_mc()
    forge_version = get_latest_forge(mc_version)

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