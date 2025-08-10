class PracticumAPIError(Exception):
    """Базовое исключение для проблем с API Практикума."""


class APIRequestError(PracticumAPIError):
    """Ошибка сетевого запроса (requests.RequestException)."""


class APIResponseError(PracticumAPIError):
    """Ошибка ответа сервера (не 200)."""


class APIJSONError(PracticumAPIError):
    """Ошибка при разборе JSON в ответе."""
