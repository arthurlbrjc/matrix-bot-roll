import asyncio
import os


async def serve_health_check() -> None:
    """Bind a minimal HTTP endpoint so platforms that health-check a port see the container as alive."""
    port = int(os.environ.get("PORT", 8080))
    server = await asyncio.start_server(_respond_health_check, "0.0.0.0", port)
    async with server:
        await server.serve_forever()


async def _respond_health_check(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    await reader.read(1024)
    writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
    await writer.drain()
    writer.close()
    await writer.wait_closed()
