FROM python:3.9-slim as base

ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONFAULTHANDLER 1

# pipenv and build tools
FROM base AS python-deps
ARG BOT_NAME=adonis_blue

RUN pip install pipenv \
    && mkdir -p /build/${BOT_NAME}
COPY src/${BOT_NAME}/Pipfile /build/${BOT_NAME} 
COPY src/${BOT_NAME}/Pipfile.lock /build/${BOT_NAME}
COPY src/lib /build/lib
WORKDIR /build/${BOT_NAME}
RUN set -e \
    && PIPENV_VENV_IN_PROJECT=1 pipenv install

# runtime
FROM base AS runtime
ARG BOT_NAME=adonis_blue
ENV BOT_NAME=${BOT_NAME}

RUN useradd --create-home ${BOT_NAME}
WORKDIR /home/${BOT_NAME}
USER ${BOT_NAME}

COPY --from=python-deps /build/${BOT_NAME}/.venv /home/${BOT_NAME}/.venv
ENV PATH="/home/${BOT_NAME}/.venv/bin:$PATH"

COPY src/${BOT_NAME} .

ENTRYPOINT [ "/bin/sh", "-c", "/usr/bin/env ./${BOT_NAME}.py" ]
