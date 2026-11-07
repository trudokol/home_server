from enum import IntEnum
from dataclasses import dataclass, asdict

class Operations(IntEnum):
    take_to_function = 1
    change_base_function = 2

class message_type(IntEnum):
    # исходящие сообщения
    text            = 1
    video           = 2
    image           = 3
    file            = 4

    # входящие сообщения
    callback_query  = 11
    message         = 12

class Ranks(IntEnum):
    owner           = 1
    user            = 2

@dataclass()
class User():
    fullname : str
    chat_id : int
    username : str
    rank : int
    available_functions : list[str]
    context : dict
    ignore : bool = False
    first_visit : bool = True
    base_function : str | None = None