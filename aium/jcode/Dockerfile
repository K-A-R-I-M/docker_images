FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

# -------- Install basics + Jcode --------
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://jcode.sh/install -o /tmp/jcode-install.sh \
    && bash /tmp/jcode-install.sh \
    && rm -f /tmp/jcode-install.sh
ENV PATH="/root/.local/bin:${PATH}"

# -------- Add skills --------
RUN mkdir -p /root/.jcode/skills \
    && git clone --depth 1 https://github.com/emilkowalski/skills.git /tmp/ek-skills \
    && mv /tmp/ek-skills/skills/* /root/.jcode/skills/ \
    && git clone --depth 1 https://github.com/addyosmani/agent-skills.git /tmp/agent-skills \
    && mv /tmp/agent-skills/skills/* /root/.jcode/skills/ \
    && rm -rf /tmp/ek-skills /tmp/agent-skills

# -------- Add configs --------
# Global jcode instructions live at ~/AGENTS.md (not ~/.jcode/AGENTS.md).
COPY ./AGENTS.md /root/AGENTS.md
COPY ./config.toml /root/.jcode/

CMD ["jcode"]
