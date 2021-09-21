"""Build all images"""

import json
import subprocess

with open("images.json") as f:
    contents = json.loads(f.read())


for image, settings in contents.items():
    subprocess.run(f"./build.sh {image} {settings['dockerfile']}", shell=True, check=True)
