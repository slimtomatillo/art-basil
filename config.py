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

class InfoFilter(logging.Filter):
    def filter(self, record):
        # Only allow specific info messages based on keywords or conditions
        if record.levelno == logging.INFO:
            # Customize conditions here; for example, showing only logs that contain certain keywords
            return  "Starting" in record.msg\
                    or "Database" in record.msg\
                    or "Scraping took" in record.msg\
                    or "Finished" in record.msg\
                    or "Only scraping" in record.msg\
                    or "Skipping" in record.msg
        return True  # Allow all other levels to pass through (e.g., WARNING and ERROR)

def configure_logging(env):
    root_logger = logging.getLogger()
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)

    # Console handler for terminal output
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # Set to INFO level
    console_handler.addFilter(InfoFilter())  # Add the custom filter to show selective info logs

    # File handler for logging all messages to file
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
