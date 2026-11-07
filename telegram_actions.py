import asyncio
import logging
from collections import deque
from enum import IntEnum
from dataclasses import dataclass, asdict
from time import time
from functools import wraps
from inspect import cleandoc

from aiogram.utils.markdown import html_decoration
from aiogram.utils.serialization import deserialize_telegram_object_to_python
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from models import User, Ranks, message_type, Operations

log = logging.getLogger("smart_home")





class TelegramActions:
    """
    Обработчик сообщений и нажатий InlineKeyboard. Предусмотрена модуляция.
    Инициализировать:
    tg_actions = TelegramActions(Resolver)\n
    Запустить:
    await start_service()\n
    Обработать сообщение или нажатие InlineKeyboard:
    process_message(Message | CallbackQuery)\n
    Проверить очередь обработанных сообщений на пустоту:
    is_outgoing_message_queue_empty()\n
    Получить обработанное сообщение:
    get_outgoing_message()\n
    Остановить:
    await stop_service()\n

    Модуляция: место для модуляци отмечено в коде комментарием MODULATE_HERE.\n
    Функции для отправки сообщения в телеграм:
    sendMessage(chat_id, text, reply_markup | None)
    """

    def __init__(self, on_message_function : function, on_callback_function : function):
        self.functions = {
            self.main_menu.__name__ : self.main_menu,
            self.echo.__name__ : self.echo
        }

        self.income_message_queue = deque() # очередь входящих сообщений на обработку
        self.outgoing_message_queue = deque() # очередь исходящих сообщений на отправку
        self.background_tasks = []

        self.onMessage = on_message_function
        self.onCallbackQuery = on_callback_function


    def process_message(self, message : Message | CallbackQuery):
        self.income_message_queue.append(message)

    def is_outgoing_message_queue_empty(self) -> bool:
        if len(self.outgoing_message_queue) > 0:
            return False
        return True

    def get_outgoing_message(self) -> dict | None:
        if not self.is_outgoing_message_queue_empty():
            result = self.outgoing_message_queue[0]
            self.outgoing_message_queue.popleft()

            return result


    async def distributor(self, message : Message | CallbackQuery):
        if type(message) == Message:
            await self.onMessage(message)
        elif type(message) == CallbackQuery:
            await self.onCallbackQuery(message)

        else:
            # Подавлять необрабатываемые сообщения
            log.warning("сообщение не поддерживается")

    async def handler(self):
        try:
            while True:
                await asyncio.sleep(0.1)
                if len(self.income_message_queue) > 0:
                    for_process = self.income_message_queue[0]
                    self.income_message_queue.popleft()

                    await self.distributor(for_process)

        except asyncio.CancelledError:
            log.info("TelegramActions: handler got asyncio.CancelledError")


    async def start_service(self):
        self.background_tasks.append(
            asyncio.create_task(self.handler())
        )

        log.info("TelegramActions запущен")


    async def stop_service(self):
        for task in self.background_tasks:
            task.cancel()
        await asyncio.gather(*self.background_tasks)
        self._mqttc.loop_stop()
        log.info("TelegramActions остановлен")


    def sendMessage(self, chat_id : int, text : str, reply_markup = None):
        if reply_markup:
            reply_markup_dict = deserialize_telegram_object_to_python(reply_markup)
            reply_markup = reply_markup_dict

        data = {"chat_id" : chat_id, "text" : text, "reply_markup" : reply_markup}
        message = {"message_type" : message_type.text, "data" : data}

        self.outgoing_message_queue.append(message)

