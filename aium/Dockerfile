FROM ghcr.io/anomalyco/opencode

RUN apk add --update --no-cache \
    uv

#---------uv config---------

# Add uv to PATH
ENV PATH="/root/.cargo/bin:/root/.local/bin:$PATH"

RUN uv tool install graphifyy
RUN graphify opencode install