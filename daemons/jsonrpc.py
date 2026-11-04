from aiohttp import ClientSession, ClientTimeout
from universalasync import LoopLocal


class JSONRPCError(Exception):
    pass


class RPCProvider:
    def __init__(self, url):
        self.url = url
        self._sessions = LoopLocal(ClientSession.close)

    @property
    def session(self):
        return self._sessions.get(ClientSession)

    async def raw_request(self, method, **kwargs):
        async with self.session.post(f"{self.url}/{method}", json=kwargs, timeout=ClientTimeout(total=5 * 60)) as response:
            return await response.json()

    async def jsonrpc_request(self, method, **kwargs):
        async with self.session.post(
            f"{self.url}/json_rpc", json={"method": method, "params": kwargs}, timeout=ClientTimeout(total=5 * 60)
        ) as response:
            data = await response.json()
            if "error" in data:
                raise JSONRPCError(data["error"])
            if "result" not in data:
                raise JSONRPCError("No result field in response")
            return data["result"]

    async def request(self, kind, method, **kwargs):
        if kind == "jsonrpc":
            return await self.jsonrpc_request(method, **kwargs)
        if kind == "raw":
            return await self.raw_request(method, **kwargs)
        raise ValueError("Invalid request kind")
