"""Build images only when paths specified are changed"""

import json
import re
import subprocess

with open("images.json") as f:
    contents = json.loads(f.read())


def grep(string, search):
    return bool(re.search(search, string))


def is_changed(files):
    return grep(
        subprocess.run(
            "git diff $COMMIT_RANGE --name-status",
            shell=True,
            stdout=subprocess.PIPE,
            universal_newlines=True,
        ).stdout,
        f"({'|'.join(files)})",
    )


for image, settings in contents.items():
    if is_changed(settings["files"]):
        subprocess.run(f"./build.sh {image} {settings['dockerfile']}", shell=True)
