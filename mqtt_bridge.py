import paho.mqtt.client as mqtt
import logging
from collections import deque
import asyncio
import time

from config import Settings

log = logging.getLogger("smart_home")

PUBLISH_MESSAGE_RETRY = 3
SUBSCRIBE_TIMEOUT = 15
MQTT_TOPIC_INCOME = "messages/to_home_server"
MQTT_TOPIC_OUTGOING = "messages/to_telegram_bridge"

class MqttClient:
    """
    Инициализировать: client_mqtt = MqttClient(параметры)\n
    Запустить: await start_service()\n
    Остановить: await stop_service()\n
    Осуществляет обмен сообщениями между серверами через MQTT\n
    Проверить очередь входящих сообщений на пустоту:
    is_income_queue_empty() -> bool\n
    Получить входящее сообщение:
    get_incoming_message() -> str\n
    Отправить сообщение:
    send_message(text)\n

    на самом деле можно было отправлять сообщения через await publish_message(text),
    но я до этого не додумался + мне понравилась идея, чтобы это больше было похоже
    на чёрный ящик, у которого только вход и выход
    """
    def __init__(self, username, password, host, port):
        self._mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.income_message_queue = deque() # очередь входящих сообщений
        self.outgoing_message_queue = deque() # очередь исходящих сообщений
        self.subscribed = False
        self.username = username
        self.password = password
        self.host = host
        self.port = port
        self.background_tasks = []
                

    def on_connect(self, client, userdata, flags, reason_code, properties):
        log.info("MQTT подключён")

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        log.info("MQTT отключён")
        self.subscribed = False

    def on_message(self, client, userdata, message):
        text = message.payload.decode()
        log.info("MQTT: пришло сообщение:" + text[:80])
        self.income_message_queue.append(text)

    def on_unsubscribe(self, client, userdata, mid, reason_code_list, properties):
        self.subscribed = False
        log.debug(f"Отписался от брокера; reason_code_list: {reason_code_list!s}")

    def is_income_queue_empty(self) -> bool:
        if len(self.income_message_queue) > 0:
            return False
        return True

    def send_message(self, text):
        self.outgoing_message_queue.append(text)

    def get_incoming_message(self) -> str | None:
        if not self.is_income_queue_empty():
            result = self.income_message_queue[0]
            self.income_message_queue.popleft()

            return result

    async def publish_message(self, text):
        loop = asyncio.get_running_loop()

        retry = 0
        while retry < PUBLISH_MESSAGE_RETRY:
            rc = await loop.run_in_executor(
                None,
                lambda: self._mqttc.publish(MQTT_TOPIC_OUTGOING, text)
            )
            await loop.run_in_executor(None, rc.wait_for_publish)

            error_code = rc[0]
            if error_code == mqtt.MQTT_ERR_SUCCESS:
                log.debug("MqttClient успешно отправил сообщение")
                break
            else:
                retry += 1
                await asyncio.sleep(1)

        if retry == PUBLISH_MESSAGE_RETRY:
            log.warning(f"Не удалось отправить сообщение; reason_code = {error_code!s}")

    async def async_subscribe(self):
        while True:
            try:
                if not self.subscribed:

                    loop = asyncio.get_running_loop()

                    rc = await loop.run_in_executor(
                        None,
                        lambda: self._mqttc.subscribe(MQTT_TOPIC_INCOME, qos=2)
                    )

                    # _mqttc.subscribe(topic, qos) -> tuple(ERROR_CODE, digit)
                    # rc[0] = ERROR_CODE
                    error_code = rc[0]

                    start_time = time.time()
                    while error_code != mqtt.MQTT_ERR_SUCCESS:
                        await asyncio.sleep(1)
                        now = time.time()
                        if now >= SUBSCRIBE_TIMEOUT + start_time:
                            break

                    if error_code == mqtt.MQTT_ERR_SUCCESS:
                        self.subscribed = True
                        log.debug("Подписан на " + MQTT_TOPIC_INCOME)

                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break

    async def sender(self):
        while True:
            try:
                if self._mqttc.is_connected():
                    if self.subscribed:
                        if len(self.outgoing_message_queue) > 0:
                            text = self.outgoing_message_queue[0]
                            self.outgoing_message_queue.popleft()
                            await self.publish_message(text)
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break


    async def start_service(self):
        self._mqttc.on_connect = self.on_connect
        self._mqttc.on_message = self.on_message
        self._mqttc.on_disconnect = self.on_disconnect

        self._mqttc.username_pw_set(self.username, self.password)
        self._mqttc.tls_set()

        self._mqttc.connect(self.host, self.port, keepalive=50)
        self._mqttc.loop_start()

        self.background_tasks.append(
            asyncio.create_task(self.async_subscribe())
        )
        self.background_tasks.append(
            asyncio.create_task(self.sender())
        )

        log.info("MQTT мост запущен")
        

    async def stop_service(self):
        for task in self.background_tasks:
            task.cancel()
        await asyncio.gather(*self.background_tasks)
        self._mqttc.loop_stop()
        log.info("MQTT мост остановлен")

# ------ Test ------

# from config import load_settings

# async def status(mqtt_client):
#     while True:
#         await asyncio.sleep(1)

#         message = mqtt_client.get_incoming_message()
#         #print(message)
#         if message:
#             mqtt_client.outgoing_message_queue.append(message)
            


# async def main():
#     settings = load_settings()

#     mqtt_client = MqttClient(settings.mqtt_username, settings.mqtt_password,
#             settings.mqtt_broker, settings.mqtt_port)

    

# asyncio.run(main())
