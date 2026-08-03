import asyncio
import logging
import os

from matrix_bot_roll.health_check import serve_health_check
from matrix_bot_roll.logging_setup import configure_logging
from matrix_bot_roll.matrix_client import run_client
from matrix_bot_roll.message_handler import handle_room_message

configure_logging()
logger = logging.getLogger(__name__)
logger.info("Starting bot", extra={"pid": os.getpid()})


async def main() -> None:
    """Launch the Matrix sync client and, if enabled, the health-check server, running until either exits."""
    tasks = [run_client(handle_room_message)]
    if os.environ.get("ENABLE_HEALTH_CHECK", "").lower() in ("1", "true", "yes"):
        tasks.append(serve_health_check())
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Fallback in case signal handlers didn't fire in time (e.g. Windows)
        logger.info("Interrupted")
    except Exception:
        # Last resort so a crash is a JSON log line, not a bare stderr traceback.
        logger.exception("Unhandled exception, shutting down")
