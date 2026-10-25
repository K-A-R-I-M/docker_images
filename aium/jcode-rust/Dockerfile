FROM rust:slim-bookworm

ENV PATH="/root/.local/bin:${PATH}"

LABEL org.opencontainers.image.title="aium-jcode-rust" \
      org.opencontainers.image.description="Jcode CLI with preinstalled agent skills and shared configuration" \
      org.opencontainers.image.source="https://github.com/K-A-R-I-M/docker_images"

# --- OS packages -------------------------------------------------------------
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

# --- Jcode CLI ---------------------------------------------------------------
RUN curl -fsSL https://jcode.sh/install -o /tmp/jcode-install.sh \
    && bash /tmp/jcode-install.sh \
    && rm -f /tmp/jcode-install.sh 

# --- Configuration -----------------------------------------------------------
COPY --from=docker.io/k4rim/aium:jcode /root/.jcode/ /root/.jcode/
COPY --from=docker.io/k4rim/aium:jcode /root/AGENTS.md /root/AGENTS.md

WORKDIR /appum

CMD ["jcode"]