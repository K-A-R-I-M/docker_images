#!/usr/bin/env python3
import requests

# Step 1: Get the version manifest
version_manifest_url = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
response = requests.get(version_manifest_url)
version_manifest = response.json()

# Step 2: Get the latest release version
latest_version = version_manifest["latest"]["release"]

# Step 3: Find the URL for the latest version details
versions = version_manifest["versions"]
latest_version_info = next(version for version in versions if version["id"] == latest_version)

# Step 4: Get the download URL for the server JAR from the version details
version_url = latest_version_info["url"]
version_response = requests.get(version_url)
version_data = version_response.json()

# Step 5: Get the server JAR URL
server_jar_url = version_data["downloads"]["server"]["url"]

print(f"Latest Minecraft server JAR URL: {server_jar_url}")

# Download the server JAR
server_jar_response = requests.get(server_jar_url)

# Save it to a file
with open("minecraft_server_latest.jar", "wb") as file:
    file.write(server_jar_response.content)

print("Minecraft server JAR downloaded successfully!")
