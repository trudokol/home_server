import asyncio
import logging
from collections import deque
from enum import IntEnum
from dataclasses import dataclass, asdict
import os
import json

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery

log = logging.getLogger("smart_home")


class Ranks(IntEnum):
    owner           = 1
    user            = 2

class Functions(IntEnum):
    database_lookup = 1

@dataclass()
class User():
    fullname : str
    chat_id : int
    username : str
    rank : int
    available_functions : list[int]
    context : dict



class Resolver:
    """
    Сохраняет данные о пользователях в data/resolved в формате json.
    data/resolved содержит опознанных пользователей в формате {chat_id : User}\n
    Инициализировать:
    resolver = Resolver(owner_id)\n
    Добавить пользователя из объекта телеграм (Message или CallbackQuery):
    add_user_from_telegram_object(telegram_object)\n
    Добавить пользователя:
    add_user(User)\n
    Удалить пользователя по chat_id или экземпляру класса User:
    delete_user(chat_id | User)\n
    Обновить данные о пользователе:
    update_user(User)\n
    Команды add_user, delete_user, update_user автоматически сохраняют изменения в файл data/resolved
    """
    def __init__(self, owner_id : int):
        data = {}
        if os.path.exists("data/resolved"):
            with open("data/resolved", 'r') as document:
                raw = json.loads(document.read())

                if type(raw) == dict:
                    for key, value in raw.items():
                        user = User(**value)
                        data[int(key)] = user
        else:
            if not os.path.exists("data"):
                os.mkdir("data")

        self.resolved : dict = data
        self.owner_id = owner_id


    def get_info(self, chat_id : int) -> User | None:
        if self.resolved.get(chat_id):
            return self.resolved[chat_id]
        else:
            return None


    def _update_json(self):
        data = {}
        for key, value in self.resolved.items():
            data[key] = asdict(value)
        data_json = json.dumps(data)

        with open("data/resolved", "w") as document:
            document.write(data_json)


    def add_user(self, user : User):
        self.resolved[user.chat_id] = user
        self._update_json()

    def update_user(self, user : User):
        self.add_user(user)

    def delete_user(self, chat_id : int | User) -> bool:
        if type(chat_id) == User:
            chat_id = User.chat_id
            
        if self.resolved.get(chat_id):
            self.resolved.pop(chat_id)
            self._update_json()
            return True
        else:
            return False


    def add_user_from_telegram_object(self, telegram_object : Message | CallbackQuery):
        fullname = telegram_object.from_user.full_name
        chat_id = telegram_object.from_user.id
        username = telegram_object.from_user.username
        context = {}

        if chat_id == self.owner_id:
            rank = Ranks.owner
            available_functions = [i.value for i in Functions.__members__.values()]
            # доступны все функции
        else:
            rank = Ranks.user
            available_functions = []
            # ничего не доступно

        user = User(fullname=fullname, chat_id=chat_id, username=username, rank=rank,
                    available_functions=available_functions, context=context)

        self.add_user(user)




        

    

    # add user
    # update user
    # delete user

    # write updated dict    

