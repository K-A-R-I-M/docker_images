FROM debian:bookworm-slim

ENV PATH="/root/.local/bin:${PATH}"

LABEL org.opencontainers.image.title="aium-jcode" \
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

# --- Skills: emilkowalski ----------------------------------------------------
ARG EK_SKILLS_REF=main
RUN mkdir -p /root/.jcode/skills \
    && git clone --depth 1 --single-branch --branch "${EK_SKILLS_REF}" \
        https://github.com/emilkowalski/skills.git /tmp/ek-skills \
    && cp -a /tmp/ek-skills/skills/. /root/.jcode/skills/ \
    && rm -rf /tmp/ek-skills

# --- Skills: addyosmani ------------------------------------------------------
ARG AGENT_SKILLS_REF=main
RUN mkdir -p /root/.jcode/skills \
    && git clone --depth 1 --single-branch --branch "${AGENT_SKILLS_REF}" \
        https://github.com/addyosmani/agent-skills.git /tmp/agent-skills \
    && cp -a /tmp/agent-skills/skills/. /root/.jcode/skills/ \
    && rm -rf /tmp/agent-skills

# --- Skills: ponytail --------------------------------------------------------
ARG PONYTAIL_REF=main
RUN mkdir -p /root/.jcode/skills \
    && git clone --depth 1 --single-branch --branch "${PONYTAIL_REF}" \
        https://github.com/DietrichGebert/ponytail.git /tmp/ponytail \
    && cp -a /tmp/ponytail/.openclaw/skills/ponytail /root/.jcode/skills/ponytail \
    && rm -rf /tmp/ponytail

# --- Skills: caveman ---------------------------------------------------------
ARG CAVEMAN_REF=main
RUN mkdir -p /root/.jcode/skills \
    && git clone --depth 1 --single-branch --branch "${CAVEMAN_REF}" \
        https://github.com/JuliusBrussee/caveman.git /tmp/caveman \
    && cp -a /tmp/caveman/skills/caveman /root/.jcode/skills/caveman \
    && rm -rf /tmp/caveman

# --- Skills: impeccable ---------------------------------------------------------
ARG IMPECCABLE_REF=main
RUN mkdir -p /root/.jcode/skills \
    && git clone --depth 1 --single-branch --branch "${IMPECCABLE_REF}" \
        https://github.com/pbakaus/impeccable /tmp/impeccable \
    && cp -a /tmp/impeccable/.agent/skills/impeccable /root/.jcode/skills/impeccable \
    && rm -rf /tmp/impeccable

# --- Configuration -----------------------------------------------------------
# Global jcode instructions live at ~/AGENTS.md (not ~/.jcode/AGENTS.md).
COPY ./AGENTS.md /root/AGENTS.md
COPY ./config.toml /root/.jcode/config.toml
# Add MCP servers (Figma, etc...)
COPY ./mcp.json /root/.jcode/mcp.json

WORKDIR /appum

CMD ["jcode"]
