import asyncio
import logging
import sys

from config import load_settings

log = logging.getLogger("smart_home")
logging.basicConfig(level=logging.INFO, filename="logs/log", filemode='a',
    format="%(asctime)s %(levelname)s %(message)s")

log.info("CI/CD works!")