import json

# NOTE: the infura key being used is metamask one
with open("api/ext/rpc/rpc.json") as f:
    RPC = json.loads(f.read())
