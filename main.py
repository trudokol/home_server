import asyncio
import aiohttp
import logging
import os
from time import time
import json
from aiogram.types import Message, CallbackQuery

from config import load_settings
from mqtt_bridge import MqttClient
from telegram_resolver import Resolver, Ranks, Functions, User
from telegram_actions import TelegramActions, message_type

MINIMAL_FREQUENCY_OF_ERROR_WARNINGS = 60 * 10 # В секундах
HEARTBEAT_FREQUENCY = 60 * 5

log = None
resolver = None
tg_actions = None
mqtt_client = None


async def heartbeat_endpoint(endpoint : str):
    last_error_time = 0
    consecutive_errors_count = 0

    try:
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(endpoint) as responce:
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
                    tg_actions.process_message(message)
                    log.info("Сообщение передано в TelegramActions")

                elif ms_type == message_type.callback_query:
                    message = CallbackQuery.model_validate(message_dict["data"])
                    tg_actions.process_message(message)
                    log.info("Сообщение передано в TelegramActions")
                    
                else:
                    log.warning("Сообщение не поддерживается")

            if not tg_actions.is_outgoing_message_queue_empty():
                message = tg_actions.get_outgoing_message()
                message_json = json.dumps(message)

                mqtt_client.send_message(message_json)
                log.info("Сообщение передано в MqttClient")

    except asyncio.CancelledError:
        pass


async def main():
    global log
    global resolver
    global mqtt_client
    global tg_actions

    settings = load_settings()

    log = logging.getLogger("smart_home")
    debug_mode = logging.DEBUG if settings.debug_mode else logging.INFO
    if not os.path.exists("logs"):
        os.mkdir("logs")
    logging.basicConfig(level=debug_mode, filename="logs/log", filemode='a',
                    format="%(asctime)s %(levelname)s %(message)s")


    mqtt_client = MqttClient(settings.mqtt_username, settings.mqtt_password,
                             settings.mqtt_broker, settings.mqtt_port)
    await mqtt_client.start_service()

    resolver = Resolver(settings.owner_id)
    tg_actions = TelegramActions(resolver)
    await tg_actions.start_service()

    asyncio.create_task(transfer())

    log.info(f"Heartbeat запущен для endpoint: {settings.heartbeat_endpoint}")
    await heartbeat_endpoint(settings.heartbeat_endpoint)
    


if __name__ == "__main__":
    asyncio.run(main())