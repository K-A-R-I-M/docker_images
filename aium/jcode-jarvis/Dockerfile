# syntax=docker/dockerfile:1

ARG WHISPER_CPP_REF=v1.9.5
ARG PIPER_VERSION=1.8.0

FROM debian:bookworm-slim AS whisper-builder
ARG WHISPER_CPP_REF
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential cmake git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch "${WHISPER_CPP_REF}" https://github.com/ggml-org/whisper.cpp /src
RUN cmake -S /src -B /build \
        -DCMAKE_BUILD_TYPE=Release \
        -DBUILD_SHARED_LIBS=OFF \
        -DGGML_NATIVE=OFF \
        -DWHISPER_BUILD_TESTS=OFF \
        -DWHISPER_BUILD_EXAMPLES=ON
RUN cmake --build /build -j"$(nproc)" --target whisper-server whisper-cli

FROM python:3.11-slim-bookworm AS piper-builder
ARG PIPER_VERSION
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --prefix=/opt/piper "piper-tts[http]==${PIPER_VERSION}"
RUN mkdir -p /opt/piper/voices
RUN set -eux; \
    cd /opt/piper/voices; \
    curl -fsSL --retry 3 -o en_US-lessac-medium.onnx \
        https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx; \
    curl -fsSL --retry 3 -o en_US-lessac-medium.onnx.json \
        https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json; \
    curl -fsSL --retry 3 -o fr_FR-siwis-medium.onnx \
        https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx; \
    curl -fsSL --retry 3 -o fr_FR-siwis-medium.onnx.json \
        https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx.json; \
    echo "5efe09e69902187827af646e1a6e9d269dee769f9877d17b16b1b46eeaaf019f  en_US-lessac-medium.onnx" | sha256sum -c -; \
    echo "efe19c417bed055f2d69908248c6ba650fa135bc868b0e6abb3da181dab690a0  en_US-lessac-medium.onnx.json" | sha256sum -c -; \
    echo "641d1ab097da2b81128c076810edb052b385decc8be3381814802a64a73baf99  fr_FR-siwis-medium.onnx" | sha256sum -c -; \
    echo "39479916c2db192b5ac9764daddd0c744d83e023ad890c6976c0633ae4df8959  fr_FR-siwis-medium.onnx.json" | sha256sum -c -

FROM debian:bookworm-slim

ARG JCODE_VERSION=v0.99.1

ENV PATH="/root/.local/bin:/opt/piper/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/opt/piper/lib/python3.11/site-packages" \
    JCODE_VERSION="${JCODE_VERSION}" \
    JCODE_NO_TELEMETRY=1 \
    DO_NOT_TRACK=1 \
    OMP_NUM_THREADS=4 \
    JARVIS_DATA=/data \
    JARVIS_PROFILE=standard \
    JARVIS_WHISPER_URL=http://127.0.0.1:8178 \
    JARVIS_PIPER_URL=http://127.0.0.1:5000 \
    JARVIS_WHISPER_BIN=/opt/whisper/whisper-server \
    JARVIS_WHISPER_CLI=/opt/whisper/whisper-cli \
    JARVIS_WHISPER_THREADS=4 \
    JARVIS_PIPER_VOICES=/opt/piper/voices \
    JARVIS_VOICE_EN=/opt/piper/voices/en_US-lessac-medium.onnx \
    JARVIS_VOICE_FR=/opt/piper/voices/fr_FR-siwis-medium.onnx \
    JARVIS_VOICE_EN_NAME=en_US-lessac-medium \
    JARVIS_VOICE_FR_NAME=fr_FR-siwis-medium

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        git \
        python3 \
        tar \
        gzip \
        alsa-utils \
        libstdc++6 \
        libgomp1 \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://jcode.sh/install -o /tmp/jcode-install.sh \
    && bash /tmp/jcode-install.sh \
    && rm -f /tmp/jcode-install.sh

RUN mkdir -p /opt/whisper
COPY --from=whisper-builder /build/bin/whisper-server /opt/whisper/whisper-server
COPY --from=whisper-builder /build/bin/whisper-cli /opt/whisper/whisper-cli
RUN chmod +x /opt/whisper/whisper-server /opt/whisper/whisper-cli
RUN set -eux; \
    mkdir -p /opt/whisper/models; \
    cd /opt/whisper/models; \
    curl -fsSL --retry 3 -o ggml-base-q5_1.bin \
        https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base-q5_1.bin; \
    curl -fsSL --retry 3 -o ggml-tiny-q5_1.bin \
        https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny-q5_1.bin; \
    curl -fsSL --retry 3 -o ggml-silero-v6.2.0.bin \
        https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v6.2.0.bin; \
    echo "422f1ae452ade6f30a004d7e5c6a43195e4433bc370bf23fac9cc591f01a8898  ggml-base-q5_1.bin" | sha256sum -c -; \
    echo "818710568da3ca15689e31a743197b520007872ff9576237bda97bd1b469c3d7  ggml-tiny-q5_1.bin" | sha256sum -c -; \
    echo "2aa269b785eeb53a82983a20501ddf7c1d9c48e33ab63a41391ac6c9f7fb6987  ggml-silero-v6.2.0.bin" | sha256sum -c -

COPY --from=piper-builder /opt/piper /opt/piper

WORKDIR /opt/jarvis
COPY jarvis.py index.html styles.css AGENTS.md config.toml brain.toml pricing.json NOTICE ./
COPY app ./app
COPY js ./js
COPY vendor ./vendor

RUN mkdir -p /root/.jcode /data \
    && cp /opt/jarvis/AGENTS.md /root/AGENTS.md \
    && cp /opt/jarvis/config.toml /root/.jcode/config.toml \
    && chmod 700 /data

VOLUME ["/data"]
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:8765/api/health?strict=1" || exit 1

CMD ["python3", "/opt/jarvis/jarvis.py", "--host", "0.0.0.0", "--port", "8765"]
