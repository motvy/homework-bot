import os
import sys
import time
import logging
import requests
from dotenv import load_dotenv
from telebot import TeleBot

load_dotenv()

PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}

HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def check_tokens():
    """Проверяет наличие обязательных переменных окружения."""
    tokens = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    if not all(tokens):
        missing = [
            name
            for name, token in zip(
                ["PRACTICUM_TOKEN", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"],
                tokens,
            )
            if not token
        ]
        logging.critical(
            f"Отсутствует обязательная переменная окружения: {missing}"
        )
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Бот отправил сообщение: "{message}"')
    except Exception as error:
        logging.error(f"Сбой при отправке сообщения в Telegram: {error}")
        raise


def get_api_answer(timestamp):
    """Делает запрос к API сервиса Практикум Домашка."""
    params = {"from_date": timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != 200:
            raise Exception(
                f"Эндпоинт {ENDPOINT} недоступен. "
                f"Код ответа API: {response.status_code}"
            )
        return response.json()
    except requests.RequestException as error:
        logging.error(f"Ошибка при запросе к API: {error}")
        raise Exception(f"Ошибка запроса к API: {error}") from error


def check_response(response):
    """Проверяет корректность ответа API."""
    if not isinstance(response, dict):
        raise TypeError("Ответ API имеет неверный тип, ожидался dict")
    if "homeworks" not in response or "current_date" not in response:
        raise KeyError("В ответе API отсутствуют ожидаемые ключи")
    if not isinstance(response["homeworks"], list):
        raise TypeError('Ключ "homeworks" должен содержать список')
    return response["homeworks"]


def parse_status(homework):
    """Извлекает статус работы из ответа API."""
    if "homework_name" not in homework:
        raise KeyError('В ответе отсутствует ключ "homework_name"')
    if "status" not in homework:
        raise KeyError('В ответе отсутствует ключ "status"')

    homework_name = homework["homework_name"]
    status = homework["status"]
    verdict = HOMEWORK_VERDICTS.get(status)

    if verdict is None:
        raise ValueError(f"Неожиданный статус работы: {status}")
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit("Программа принудительно остановлена.")

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
            else:
                logging.debug("Отсутствие в ответе новых статусов.")

            timestamp = response.get("current_date", timestamp)
            last_error = None  # сброс ошибки после успешного прохода

        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            logging.error(message)
            if str(error) != last_error:
                try:
                    send_message(bot, message)
                except Exception:
                    pass
                last_error = str(error)

        time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
