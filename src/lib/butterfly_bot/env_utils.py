import logging
import os

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def load_environment():
    load_dotenv()
    env_files = [os.getenv(key) for key in os.environ.keys() if key.endswith("_FILE")]

    for env_file in env_files:
        # strip _FILE to get key name
        key = env_file[:-5]

        logger.info(f"loading environment var {key} from {env_file}")
        try:
            with open(env_file, "r") as f:
                os.environ[key] = f.read()
        except Exception as e:
            logger.exception(f"something went wrong: {e}")


load_environment()
