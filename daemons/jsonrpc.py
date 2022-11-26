from aiohttp import ClientSession
from universalasync import get_event_loop


class JSONRPCError(Exception):
    pass


class RPCProvider:
    def __init__(self, url):
        self.url = url
        self._sessions = {}

    @property
    def session(self):
        loop = get_event_loop()
        session = self._sessions.get(loop)
        if session is not None:
            return session
        self._sessions[loop] = ClientSession()
        return self._sessions[loop]

    async def _close(self) -> None:
        for session in self._sessions.values():
            if session is not None:
                await session.close()

    def __del__(self) -> None:
        loop = get_event_loop()
        if loop.is_running():
            loop.create_task(self._close())
        else:
            loop.run_until_complete(self._close())

    async def raw_request(self, method, **kwargs):
        async with self.session.post(f"{self.url}/{method}", json=kwargs, timeout=5 * 60) as response:
            data = await response.json()
            return data

    async def jsonrpc_request(self, method, **kwargs):
        async with self.session.post(
            f"{self.url}/json_rpc", json={"method": method, "params": kwargs}, timeout=5 * 60
        ) as response:
            data = await response.json()
            if "error" in data:
                raise JSONRPCError(data["error"])
            if "result" not in data:
                raise JSONRPCError("No result field in response")
            return data["result"]
