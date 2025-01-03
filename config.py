import logging

# Constants
DB_FILES = {
    'sf': 'docs/data/sf_events.json',
    'la': 'docs/data/la_events.json',
}
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
                    or "Selecting" in record.msg\
                    or "Skipping" in record.msg
        return True  # Allow all other levels to pass through (e.g., WARNING and ERROR)

def configure_logging(env):
    root_logger = logging.getLogger()
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)

    # Console handler for terminal output
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # Keep INFO level for console in both environments
    console_handler.addFilter(InfoFilter())

    # File handler with environment-specific log file
    log_file = "dev.log" if env == 'dev' else "scraping.log"
    file_handler = logging.FileHandler(log_file, mode='a')
    
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s - [%(filename)s:%(lineno)d]')

    handlers = [console_handler, file_handler]

    for handler in handlers:
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    
    # Set overall logging level
    root_logger.setLevel(logging.INFO)
