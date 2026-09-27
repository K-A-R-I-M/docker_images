FROM ghcr.io/anomalyco/opencode

RUN apk add --update --no-cache \
    uv \
    git

#---------uv config---------

# Add uv to PATH
ENV PATH="/root/.cargo/bin:/root/.local/bin:$PATH"

RUN uv tool install graphifyy
RUN graphify install --platform opencode
RUN git clone https://github.com/addyosmani/agent-skills.git /root/agent-skills
RUN mv /root/agent-skills/skills /root/.config/opencode/skills