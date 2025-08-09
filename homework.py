import os
import sys
import time
import logging
import requests
from dotenv import load_dotenv
from telebot import apihelper, TeleBot

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


class PracticumAPIError(Exception):
    """Базовое исключение для проблем с API Практикума."""

    pass


class APIRequestError(PracticumAPIError):
    """Ошибка сетевого запроса (requests.RequestException)."""

    pass


class APIResponseError(PracticumAPIError):
    """Ошибка ответа сервера (не 200)."""

    pass


class APIJSONError(PracticumAPIError):
    """Ошибка при разборе JSON в ответе."""

    pass


def check_tokens():
    """Проверяет наличие обязательных переменных окружения."""
    tokens = (
        (PRACTICUM_TOKEN, "PRACTICUM_TOKEN"),
        (TELEGRAM_TOKEN, "TELEGRAM_TOKEN"),
        (TELEGRAM_CHAT_ID, "TELEGRAM_CHAT_ID"),
    )
    missing = [name for token, name in tokens if not token]

    if missing:
        logging.critical(
            f"Отсутствует обязательная переменная окружения: {missing}"
        )
    return not bool(missing)


def send_message(bot, message):
    """Отправляет сообщение в Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Бот отправил сообщение: "{message}"')
    except (apihelper.ApiException, requests.RequestException) as error:
        logging.error(f"Сбой при отправке сообщения в Telegram: {error}")
        raise


def get_api_answer(timestamp):
    """Делает запрос к API сервиса Практикум Домашка."""
    params = {"from_date": timestamp}

    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params=params, timeout=10
        )
    except requests.RequestException as err:
        raise APIRequestError(f"Ошибка запроса к API: {err}") from err

    if response.status_code != 200:
        raise APIResponseError(
            f"Эндпоинт {ENDPOINT} недоступен. Ответ API: {response.status_code}"
        )

    try:
        return response.json()
    except ValueError as err:
        raise APIJSONError(
            f"Не удалось разобрать JSON в ответе API: {err}"
        ) from err


def check_response(response):
    """Проверяет корректность ответа API."""
    if not isinstance(response, dict):
        raise TypeError("Ответ API имеет неверный тип, ожидался dict")
    if "homeworks" not in response or "current_date" not in response:
        raise KeyError("В ответе API отсутствуют ожидаемые ключи")

    response_homeworks = response["homeworks"]
    if not isinstance(response_homeworks, list):
        raise TypeError('Ключ "homeworks" должен содержать список')
    return response_homeworks


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
    last_error_message = None

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
            last_error_message = None

        except PracticumAPIError as error:
            # Наши предсказуемые ошибки API
            message = f"Сбой в работе программы: {error}"
            logging.error(message)
            if message != last_error_message:
                try:
                    send_message(bot, message)
                except (apihelper.ApiException, requests.RequestException):
                    pass
                last_error_message = message

        except Exception as error:
            # Непредвиденные ошибки
            message = f"Неизвестная ошибка: {error}"
            logging.exception(message)
            if message != last_error_message:
                try:
                    send_message(bot, message)
                except (apihelper.ApiException, requests.RequestException):
                    pass
                last_error_message = message

        time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    main()
