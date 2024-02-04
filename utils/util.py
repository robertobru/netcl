import logging
import string
import random
import json
from pydantic import BaseModel
from typing import Union
import traceback


class MongoDbConfig(BaseModel):
    host: str
    port: int = 27017
    db: str = 'netcl',
    user: Union[str, None] = None
    password: Union[str, None] = None


class ConfigFile(BaseModel):
    mongodb: MongoDbConfig


def create_logger(name: str) -> logging.getLogger:
    # create logger
    _logger = logging.getLogger(name)
    _logger.setLevel(logging.DEBUG)
    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    # create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # add formatter to ch
    ch.setFormatter(formatter)
    # add ch to logger
    _logger.addHandler(ch)
    return _logger


logger = create_logger('utils')

with open("config.json", 'r') as stream:
    try:
        json_conf = json.load(stream)
    except json.JSONDecodeError as exc:
        logger.error("invalid JSON format in the config file")
        raise ValueError('configuration file problem')
    except FileNotFoundError:
        logger.error("config file not found")
        raise ValueError('configuration file problem')

    # Parsing the config file
    try:
        netcl_conf = ConfigFile.model_validate(json_conf)

    except Exception as exception:
        logger.error('exception in the configuration file parsing')
        logger.error(traceback.format_exc())
        raise ValueError('configuration file problem')


def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))
