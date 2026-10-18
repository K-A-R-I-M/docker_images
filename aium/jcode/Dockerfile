FROM debian 

# --------Install Basics + Jcode--------------
RUN apt update; apt install -y \ 
    curl \
    bash \
    git

RUN curl -fsSL https://jcode.sh/install | bash; \
    mkdir -p /root/.jcode/skills 
    

# --------Add Skills--------------
# ----------------------
RUN git clone --depth 1 https://github.com/emilkowalski/skills.git /tmp/ek-skills; \
    mv /tmp/ek-skills/skills/* /root/.jcode/skills

# ----------------------
RUN git clone --depth 1 https://github.com/addyosmani/agent-skills.git /tmp/agent-skills; \
    mv /tmp/agent-skills/skills/* /root/.jcode/skills

# --------Add Configs--------------
COPY ./AGENTS.md /root/.jcode/
COPY ./config.toml /root/.jcode/

CMD [ "/root/.local/bin/jcode" ]