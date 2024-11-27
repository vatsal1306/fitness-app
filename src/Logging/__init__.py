import logging
from logging.handlers import RotatingFileHandler
import os
from src.Utils import settings
from src.Utils.utils import Path

logger = logging.getLogger(__name__)
logger.setLevel(settings.level)

log_dirname = "Logs"
log_filename = settings.file
log_filepath = os.path.join(os.getcwd(), log_dirname, log_filename)

Path.create_dir_if_not_exists(log_dirname)
Path.create_file_if_not_exists(log_filepath)

formatter = logging.Formatter('%(filename)s | %(lineno)s | %(asctime)s | %(levelname)s | %(message)s')

file_handler = RotatingFileHandler(log_filepath)
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
stream_handler.setLevel(logging.INFO)

logger.addHandler(file_handler)
logger.addHandler(stream_handler)
