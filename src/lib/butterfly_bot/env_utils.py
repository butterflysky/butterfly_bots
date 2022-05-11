import os

import contextib
from dotenv import load_dotenv


def load_environment():
    load_dotenv()
    env_files = [key for key in os.environ.key() if key.endswith("_FILE")]

    with contextib.suppress(Exception):
        for env_file in env_files:
            # strip _FILE to get key name
            key = env_file[:-5]
            with open(env_file, "r") as f:
                os.environ[key] = f.read()


load_environment()