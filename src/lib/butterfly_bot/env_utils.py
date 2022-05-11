import logging
import os

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def load_environment():
    load_dotenv()
    env_file_keys = [key for key in os.environ.keys() if key.endswith("_FILE")]

    for env_file_key in env_file_keys:
        # strip _FILE to get key name
        key = env_file_key[:-5]
        env_file = os.getenv(env_file_key)

        logger.info(f"loading environment var {key} from {env_file}")
        try:
            with open(env_file, "r") as f:
                os.environ[key] = f.read()
        except Exception as e:
            logger.exception(f"something went wrong: {e}")


load_environment()
