import logging

# Constants
DB_FILE = 'docs/events_db.json'
MONTH_TO_NUM_DICT = {
    'jan': 1,
    'feb': 2,
    'mar': 3,
    'apr': 4,
    'may': 5,
    'jun': 6,
    'jul': 7,
    'aug': 8,
    'sep': 9,
    'oct': 10,
    'nov': 11,
    'dec': 12,
    
    'january': 1,
    'february': 2,
    'march': 3,
    'april': 4,
    'june': 6,
    'july': 7,
    'august': 8,
    'september': 9,
    'october': 10,
    'november': 11,
    'december': 12,
    
    'sept': 9,
}

def configure_logging(env):
    root_logger = logging.getLogger()
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    handlers = [console_handler]

    if env == 'prod':
        file_handler = logging.FileHandler("scraping.log", mode='a')
        file_handler.setLevel(logging.INFO)
        handlers.append(file_handler)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    for handler in handlers:
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
