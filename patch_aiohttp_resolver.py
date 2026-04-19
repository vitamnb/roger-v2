"""
Freqtrade patches aiodns DNS failures on Windows by replacing the aiodns resolver
with a synchronous socket-based resolver that uses the system DNS.
Put this file in the freqtrade user_data directory and add to config:
  "bot_name": "Roger v3",
  "initial_state": "running",
  "force_entry_enable": true,
  "internals": {
    "process_throttle_secs": 5
  }

Actually, patch this at site-packages level:
"""
import sys
import socket


def patch_aiohttp_dns():
    """Replace aiodns with a synchronous system-DNS resolver for aiohttp."""
    import aiodns
    import aiohttp
    import asyncio

    class SystemDNSResolver(aiohttp.abc.AbstractResolver):
        """Use system DNS (socket.getaddrinfo) instead of aiodns."""

        def __init__(self, hosts_cache_size=10000):
            self._cache = {}
            self._hosts_cache_size = hosts_cache_size

        async def resolve(self, host, port, family=socket.AF_INET):
            key = (host, port, family)
            if key not in self._cache:
                loop = asyncio.get_running_loop()
                infos = await loop.run_in_executor(
                    None, socket.getaddrinfo, host, port, family, socket.SOCK_STREAM
                )
                # Peel off the structure aiohttp expects
                family, socktype, proto, _, addr = infos[0]
                self._cache[key] = [(family, socktype, proto, addr)]
                if len(self._cache) > self._hosts_cache_size:
                    # Drop oldest entries
                    oldest = next(iter(self._cache))
                    del self._cache[oldest]
            return self._cache[key]

        async def close(self):
            self._cache.clear()

    # Override aiohttp's default resolver
    aiohttp.DefaultResolver = SystemDNSResolver
    print("[patch_aiohttp_resolver] aiodns patched — aiohttp now uses system DNS")


if __name__ == "__main__":
    patch_aiohttp_dns()