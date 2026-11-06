import asyncio
import logging
from collections import deque
from enum import IntEnum
from dataclasses import dataclass, asdict
from time import time
from functools import wraps
from inspect import cleandoc
from aiogram.utils.markdown import html_decoration

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from telegram_resolver import Ranks, User, Resolver

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

class Operations(IntEnum):
    take_to_function = 1


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
        self.functions = {
            self.main_menu.__name__ : self.main_menu,
            self.echo.__name__ : self.echo
        }


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

    def access_check(func):
        """
        Эта функция предназначена только для декорирования.\n
        <b>Первый аргумент всегда должен быть User'ом, которого мы проверяем.</b>\n
        Все пользователи, у которых есть доступ к функции
        будут пропущены дальше, для других же сработает заглушка.
        Для игнорируемых пользователей сработает другая.
        """

        @wraps(func)
        def wrapper(*args, **kwargs):
            if len(args) > 0:
                if type(args[0]) == User:
                    user = args[0]
                    if not user.ignore:
                        if func.__name__ in user.available_functions:
                            return func(*args, **kwargs)
                        else:
                            log.debug(f"User {user.username} ({user.chat_id}) tried to enter in disallowed function.")
                    else:
                        log.debug(f"Message from {user.username} ({user.chat_id}) ignored.")
                else:
                    log.warning("Function access_check claims User as first argument")
            else:
                log.error("Function access_check claims at least one argument (User)")

        return wrapper



    @access_check
    def echo(self, message : Message):
        builder = InlineKeyboardBuilder()
        builder.button(text="Назад", callback_data=f"{Operations.take_to_function}|{self.main_menu.__name__}")

        self.sendMessage(message.from_user.id, message.text, reply_makrup=builder.as_markup())

    @access_check
    def main_menu(self, user : User):
        if user.rank == Ranks.owner:
            text = cleandoc("""
            Главном меню, Господин
            """)
        else:
            text == cleandoc("""
            Главном меню
            """)

        builder = InlineKeyboardBuilder()

        for func_name in user.available_functions:
            builder.button(text=f"Перейти в {func_name}",
                           callback_data=f"{Operations.take_to_function}|{func_name}")

        if len(user.available_functions) == 0:
            text += "\nВам пока не дали ни одной кнопки"
        
        self.sendMessage(text=text, chat_id=user.chat_id, reply_makrup=builder.as_markup())



    def greet(self, user : User):
        if user.rank == Ranks.owner:
            greeting_text = cleandoc("""
            ПРИВЕТ СОЗДАТЕЛЬ!!!!11!!
            обожаю тебя
            """)
        else:
            greeting_text = html_decoration.quote(cleandoc("""
            привет, <user>!
            """).replace("<user>", user.username))
        
        self.sendMessage(chat_id=user.chat_id, text=greeting_text)

    async def onMessage(self, message : Message):
        user = self.resolver.get_info(message.from_user.id)

        if user is None: # первое пришествие
            self.resolver.add_user_from_telegram_object(message)
            user = self.resolver.get_info(message.from_user.id) # добавлен пользователь без прав

            if user.rank == Ranks.owner:
                user.available_functions = self.functions.keys()
            elif user.rank == Ranks.user:
                user.available_functions.append(self.main_menu.__name__)

            user.base_function = self.main_menu.__name__
            self.greet(user)
            user.first_visit = False

            self.resolver.update_user(user)

        func = self.functions.get(user.base_function)
        if func:
            func(func)
            


    async def onCallbackQuery(self, callback : CallbackQuery):
        if callback.data:
            data = callback.data
            splitted = data.split("|")
            if splitted[0] == Operations.take_to_function:
                take_to_name = splitted[1]
                func = self.functions.get(take_to_name)
                if func:
                    user = self.resolver.get_info(callback.from_user.chat_id)
                    func(user)




