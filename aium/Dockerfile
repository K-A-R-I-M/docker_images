FROM ghcr.io/anomalyco/opencode

# ----------------------

RUN apk add --update --no-cache \
    uv \
    git

#---------uv config---------

# Add uv to PATH
ENV PATH="/root/.cargo/bin:/root/.local/bin:$PATH"

# ----------------------

RUN uv tool install graphifyy
RUN graphify install --platform opencode

# ----------------------

RUN git clone --depth 1 https://github.com/emilkowalski/skills.git /tmp/ek-skills; \
    mv /tmp/ek-skills/skills/* /root/.config/opencode/skills

# ----------------------

RUN git clone --depth 1 https://github.com/addyosmani/agent-skills.git /tmp/agent-skills; \
    mv /tmp/agent-skills/skills/* /root/.config/opencode/skills

# ----------------------

COPY ./AGENTS.md /root/.config/opencode/
COPY ./opencode.json /root/.config/opencode/