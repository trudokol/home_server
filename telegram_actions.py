import asyncio
import logging
from collections import deque
from enum import IntEnum
from dataclasses import dataclass

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery

from telegram_resolver import Ranks, Functions, User, Resolver

log = logging.getLogger("smart_home")


class message_type(IntEnum):
    # исходящие сообщения
    text            = 1
    video           = 2
    image           = 3
    file            = 4

    # входящие сообщения
    callback_query  = 11
    message         = 12


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
    def __init__(self, resolver : Resolver):
        self.resolver = resolver
        self.income_message_queue = deque() # очередь входящих сообщений на обработку
        self.outgoing_message_queue = deque() # очередь исходящих сообщений на отправку
        self.background_tasks = []


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
            pass


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



    def sendMessage(self, chat_id : int, text : str, reply_makrup = None):
        data = {"chat_id" : chat_id, "text" : text, "reply_makrup" : reply_makrup}
        message = {"message_type" : message_type.text, "data" : data}

        self.outgoing_message_queue.append(message)


    # MODULATE_HERE
    # Ниже писать логику обработки сообщений


    def echo(self, message : Message):
        self.sendMessage(message.from_user.id, message.text)


    async def onMessage(self, message : Message):
        self.echo(message)

    async def onCallbackQuery(self, callback : CallbackQuery):
        pass



