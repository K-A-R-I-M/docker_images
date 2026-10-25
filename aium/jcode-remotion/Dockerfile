FROM node:bookworm-slim

ENV PATH="/root/.local/bin:${PATH}"
ENV REMOTION_BROWSER_EXECUTABLE=/usr/bin/chromium

LABEL org.opencontainers.image.title="aium-jcode-remotion" \
      org.opencontainers.image.description="Jcode CLI with Remotion, Chromium and historical motion-design skill" \
      org.opencontainers.image.source="https://github.com/K-A-R-I-M/docker_images"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        chromium \
        ca-certificates \
        bash \
        curl \
        git \
        fonts-dejavu-core \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# --- Remotion CLI ---------------------------------------------------------------
RUN npm install -g @remotion/cli

# --- Jcode CLI ---------------------------------------------------------------
RUN curl -fsSL https://jcode.sh/install -o /tmp/jcode-install.sh \
    && bash /tmp/jcode-install.sh \
    && rm -f /tmp/jcode-install.sh

# --- Configuration -----------------------------------------------------------
COPY --from=docker.io/k4rim/aium:jcode /root/.jcode/ /root/.jcode/
COPY --from=docker.io/k4rim/aium:jcode /root/AGENTS.md /root/AGENTS.md

# --- Skills: historical motion design ----------------------------------------
COPY ./motion-design /root/.jcode/skills/motion-design

WORKDIR /appum

CMD ["jcode"]
