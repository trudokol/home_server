import asyncio
import aiohttp
import logging
import os
from time import time
import json
from aiogram.types import Message, CallbackQuery
from aiogram.utils.serialization import deserialize_telegram_object_to_python
import signal
from functools import partial

from models import *
from config import load_settings
from mqtt_bridge import MqttClient
from telegram_resolver import Resolver
from telegram_bot_logic import TelegramBotLogic

MINIMAL_FREQUENCY_OF_ERROR_WARNINGS = 60 * 10 # В секундах
HEARTBEAT_FREQUENCY = 60 * 5

log = None
resolver = None
tg_bot_logic = None
mqtt_client = None


async def heartbeat_endpoint(endpoint : str):
    last_error_time = 0
    consecutive_errors_count = 0

    try:
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(endpoint) as responce:
                        log.debug(f"responce code: {responce.status}")
                        if responce.status != 200:
                            if consecutive_errors_count >= 3:
                                consecutive_errors_count = 0

                                log.warning(f"Inappropriate responce (heartbeat): {responce.status}")
                            else:
                                consecutive_errors_count += 1
                        else:
                            consecutive_errors_count = 0
                            

            except aiohttp.ClientError as error:
                if time() - last_error_time > MINIMAL_FREQUENCY_OF_ERROR_WARNINGS:
                    last_error_time = time()

                    log.warning(f"Client Error: {error}")

            await asyncio.sleep(HEARTBEAT_FREQUENCY)

    except asyncio.CancelledError:
        pass


async def transfer():
    try:
        while True:
            await asyncio.sleep(0.1)
            if not mqtt_client.is_income_queue_empty():
                message_json = mqtt_client.get_incoming_message()
                message_dict = json.loads(message_json)
                
                ms_type = message_dict.get("message_type")

                if ms_type == message_type.message:
                    message = Message.model_validate(message_dict["data"])
                    tg_bot_logic.process_message(message)
                    log.info("Сообщение передано в TelegramActions")

                elif ms_type == message_type.callback_query:
                    message = CallbackQuery.model_validate(message_dict["data"])
                    tg_bot_logic.process_message(message)
                    log.info("Сообщение передано в TelegramActions")
                    
                else:
                    log.warning("Сообщение не поддерживается")

            if not tg_bot_logic.is_outgoing_message_queue_empty():
                message = tg_bot_logic.get_outgoing_message()
                message_json = json.dumps(message)

                mqtt_client.send_message(message_json)
                log.info("Сообщение передано в MqttClient")

    except asyncio.CancelledError:
        pass


async def ask_exit(loop, background_tasks, signal):
    log.info("Получен сигнал об остановке (%s), завершаю работу..." % signal)
    
    for task in background_tasks:
        task.cancel()

    await asyncio.gather(*background_tasks)

    if tg_bot_logic:
        await tg_bot_logic.stop_service()
    if mqtt_client:
        await mqtt_client.stop_service()

    loop.stop()
    

async def main():
    global log
    global resolver
    global mqtt_client
    global tg_bot_logic

    background_tasks = []

    settings = load_settings()

    log = logging.getLogger("smart_home")
    debug_mode = logging.DEBUG if settings.debug_mode else logging.INFO
    if not os.path.exists("logs"):
        os.mkdir("logs")
    logging.basicConfig(level=debug_mode, filename="logs/log", filemode='a',
                    format="%(asctime)s %(levelname)s %(message)s")


    mqtt_client = MqttClient(settings.mqtt_username, settings.mqtt_password,
                             settings.mqtt_broker, settings.mqtt_port,
                             client_id=settings.client_id,
                             mqtt_topic_income=settings.mqtt_topic_income,
                             mqtt_topic_outgoing=settings.mqtt_topic_outgoing)
    await mqtt_client.start_service()

    resolver = Resolver(settings.owner_id)
    tg_bot_logic = TelegramBotLogic(resolver)
    await tg_bot_logic.start_service()

    background_tasks.append(
        asyncio.create_task(transfer())
    )

    background_tasks.append(
        asyncio.create_task(heartbeat_endpoint(settings.heartbeat_endpoint))
    )
    log.info(f"Heartbeat запущен для endpoint: {settings.heartbeat_endpoint}")


    loop = asyncio.get_running_loop()
    for sig in ["SIGINT", "SIGTERM"]:
        try:
            loop.add_signal_handler(
                getattr(signal, sig),
                partial(ask_exit, loop, background_tasks, sig)
            )
        except NotImplementedError:
            log.debug("Got NotImplementedError on signal %s" % sig)

    try:
        while True:
            await asyncio.sleep(0.5)
    except Exception as error:
        log.debug(f"Got exception in main loop: {str(error)}")
    


if __name__ == "__main__":
    asyncio.run(main())