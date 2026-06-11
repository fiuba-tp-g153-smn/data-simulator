"""Entrypoint: load settings, wire the app, serve uvicorn."""

import logging

import uvicorn

from feed_simulator.config import Settings
from feed_simulator.factories import create_application


def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = Settings.from_env()
    app = create_application(settings)
    uvicorn.run(app, host="0.0.0.0", port=settings.port, log_level="info")


if __name__ == "__main__":
    run()
