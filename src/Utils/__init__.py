# app/config.py

import configparser
import os
from src import ROOT_DIR

config = configparser.ConfigParser()
config_file = os.path.join(ROOT_DIR, 'config.ini')
config.read(config_file)


class Settings:
    def __init__(self):
        sections = config.sections()
        for section in sections:
            for key, value in config.items(section):
                setattr(self, key, value)


settings = Settings()
