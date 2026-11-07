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

from telegram_resolver import Resolver
from telegram_actions import TelegramActions
from models import User, Ranks, message_type, Operations

log = logging.getLogger("smart_home")



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
        log.debug(f"access_check wrapper got *args:{str(args)}")
        if len(args) > 1:
            if type(args[1]) == User:
                user = args[1]
                if not user.ignore:
                    if func.__name__ in user.available_functions:
                        return func(*args, **kwargs)
                    else:
                        log.debug(f"User {user.username} ({user.chat_id}) tried to enter in disallowed function.")
                else:
                    log.debug(f"Message from {user.username} ({user.chat_id}) ignored.")
            else:
                log.warning("Function access_check claims User as second argument (because first is self)")
        else:
            log.error("Function access_check claims at least one argument (User)")

    return wrapper


class TelegramBotLogic(TelegramActions):
    def __init__(self, resolver : Resolver):
        self.resolver = resolver

        on_message_function = self.onMessage
        on_callback_function = self.onCallbackQuery
        super().__init__(on_message_function, on_callback_function)


    @access_check
    def echo(self, user : User, message : Message):
        builder = InlineKeyboardBuilder()
        builder.button(text="Назад", callback_data=f"{Operations.take_to_function}|{self.main_menu.__name__}")

        self.sendMessage(message.from_user.id, message.text, reply_markup=builder.as_markup())

    @access_check
    def main_menu(self, user : User, message : Message):
        if user.rank == Ranks.owner:
            text = cleandoc("""
            Главное меню, Господин
            """)
        else:
            text == cleandoc("""
            Главное меню
            """)

        builder = InlineKeyboardBuilder()

        for func_name in user.available_functions:
            if func_name == self.echo.__name__:
                builder.button(text=f"Перейти в {func_name}",
                            callback_data=f"{Operations.change_base_function}|{func_name}")
            else:
                builder.button(text=f"Перейти в {func_name}",
                            callback_data=f"{Operations.take_to_function}|{func_name}")

        builder.adjust(1)

        if len(user.available_functions) == 0:
            text += "\nВам пока не дали ни одной кнопки"
        
        self.sendMessage(text=text, chat_id=user.chat_id, reply_markup=builder.as_markup())
        log.debug(f"Из main_menu отправлено сообщение: text = {text}; chat_id = {user.chat_id}; \
                   reply_markup = {str(deserialize_telegram_object_to_python(builder.as_markup()))}")



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
                [user.available_functions.append(i) for i in self.functions.keys()]
            elif user.rank == Ranks.user:
                user.available_functions.append(self.main_menu.__name__)

            user.base_function = self.main_menu.__name__
            self.greet(user)
            user.first_visit = False

            self.resolver.update_user(user)

        log.debug(f"user.available_functions ({user.username}) содержит: {str(user.available_functions)}")

        func = self.functions.get(user.base_function)
        if func:
            func(user, message)
        else:
            log.debug("Message supressed")
            


    async def onCallbackQuery(self, callback : CallbackQuery):
        if callback.data:
            data = callback.data
            log.debug(f"Got callback data: {data}")

            splitted = data.split("|")
            operation = int(splitted[0])
            if operation == Operations.take_to_function:
                take_to_name = splitted[1]
                func = self.functions.get(take_to_name)
                if func:
                    user = self.resolver.get_info(callback.from_user.id)
                    log.debug(f"{user.username} направлен в {take_to_name} по нажатию кнопки")
                    func(user, None)
                else:
                    log.debug(f"Function {take_to_name} not found")
            elif operation == Operations.change_base_function:
                change_to_name = splitted[1]
                func = self.functions.get(change_to_name)
                if func:
                    log.debug(f"callback.from_user.id = {callback.from_user.id}")
                    user = self.resolver.get_info(callback.from_user.id)
                    user.base_function = change_to_name
                    self.resolver.update_user(user)
                    log.debug(f"Для {user.username} изменилась base_function на {change_to_name}")
                else:
                    log.debug(f"Function {change_to_name} not found")
            else:
                log.debug(f"Operation {splitted[0]} not found")
        else:
            log.debug(f"Got empty callback.data")
