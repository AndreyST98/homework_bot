import json
import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    filemode='w',
    format='%(asctime)s -%(levelname)s - %(message)s - %(name)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s -%(levelname)s - %(message)s - %(name)s'
)
handler.setFormatter(formatter)


class TheAnswerIsNot200Error(Exception):
    """Ответ сервера не равен 200."""


class RequestExceptionError(Exception):
    """Ошибка запроса."""


class HomeworkVerdictError(Exception):
    """Ошибка запроса."""


class ListHomeworkEmptyError(Exception):
    """Ошибка ключа homeworks или response."""


def send_message(bot, message):
    """Отправка сообщения в Телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(
            f'Сообщение в Telegram отправлено: {message}')
    except telegram.TelegramError as telegram_error:
        logger.error(
            f'Сообщение в Telegram не отправлено: {telegram_error}')


def get_api_answer(current_timestamp):
    """Получение данных с API YP."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != 200:
            code_api_msg = (
                f'Эндпоинт {ENDPOINT} недоступен.'
                f' Код ответа API: {response.status_code}')
            logger.error(code_api_msg)
            raise TheAnswerIsNot200Error(code_api_msg)
        return response.json()
    except requests.exceptions.RequestException as request_error:
        code_api_msg = f'Код ответа API (RequestException): {request_error}'
        logger.error(code_api_msg)
        raise RequestExceptionError(code_api_msg)
    except json.JSONDecodeError as value_error:
        code_api_msg = f'Код ответа API (ValueError): {value_error}'
        logger.error(code_api_msg)
        raise json.JSONDecodeError(code_api_msg)


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        message = 'Ответ не является словарем!'
        logger.error(message)
        raise TypeError(message)

    if 'homeworks' not in response:
        message = 'Ключа homeworks нет в словаре.'
        logger.error(message)
        raise KeyError(message)
    if not isinstance(response['homeworks'], list):
        message = 'Домашние работы не являются списком!'
        logger.error(message)
        raise TypeError(message)
    if not response['homeworks']:
        message = 'Список работ пуст!'
        logger.error(message)
        raise ListHomeworkEmptyError(message)
    return response['homeworks']


def parse_status(homework):
    """Достаем статус работы."""
    if not isinstance(homework, dict):
        message = 'Ответ не является словарем!'
        logger.error(message)
        raise TypeError(message)
    if 'homework_name' not in homework:
        message = 'Ключа homework_name нет в словаре.'
        logger.error(message)
        raise KeyError(message)
    if 'status' not in homework:
        message = 'Ключа status нет в словаре.'
        logger.error(message)
        raise KeyError(message)
    if homework['status'] not in HOMEWORK_STATUSES:
        message = "Нет вердикта."
        logger.error(message)
        raise HomeworkVerdictError("Нет вердикта!")
    homework_name = homework['homework_name']
    homework_status = homework['status']
    verdict = HOMEWORK_STATUSES[homework_status]
    return(f'Изменился статус проверки работы "{homework_name}".'
           f'{verdict}')


def check_tokens():
    """Проверка наличия токенов."""
    no_tokens_msg = (
        'Программа принудительно остановлена. '
        'Отсутствует обязательная переменная окружения:')
    token = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    for item in token:
        if item is None or len(item) == 0:
            logger.critical(f'{no_tokens_msg} TELEGRAM_CHAT_ID')
            return False
        return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    tmp_status = 'reviewing'
    error_message = None
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if homework and tmp_status != homework['status']:
                message = parse_status(homework)
                send_message(bot, message)
                tmp_status = homework['status']
            logger.info(
                f'Изменений нет, {RETRY_TIME} секунд и проверяем API')
            current_timestamp = response.get('current_date', current_timestamp)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if error_message != message:
                error_message = message
                send_message(bot, error_message)
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
