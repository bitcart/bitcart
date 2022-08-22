import json

with open("api/ext/blockexplorer/explorers.json") as f:
    EXPLORERS = json.loads(f.read())
