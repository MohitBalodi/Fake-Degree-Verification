"""RQ worker entrypoint. Only OCR jobs run here (Tier 2)."""

import logging

from redis import Redis
from rq import Queue, Worker

from app.core.config import settings

QUEUE_NAME = "ocr"


def main() -> None:
    logging.basicConfig(level=settings.log_level)
    connection = Redis.from_url(settings.redis_url)
    worker = Worker([Queue(QUEUE_NAME, connection=connection)], connection=connection)
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
