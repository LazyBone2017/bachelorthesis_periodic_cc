# Dockerfile for the PULSE testbed

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# install system dependencies for network setup, matplotlib GUI, and C extensions
RUN apt-get update && apt-get install -y \
        build-essential \
        python3-dev \
        libffi-dev \
        libssl-dev \
        iproute2 \
        net-tools \
        python3-tk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY . /workspace

RUN pip install --upgrade pip setuptools wheel \
 && pip install -e . \
 && if [ -f requirements.txt ]; then pip install -r requirements.txt; fi

CMD ["bash"]
