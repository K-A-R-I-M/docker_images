FROM docker.io/library/alpine AS build

WORKDIR /app/

RUN apk add --update --no-cache python3 py3-pip

COPY ./get_minecraft_server.py ./

RUN pip3 install requests

RUN python get_minecraft_server.py

FROM docker.io/library/openjdk:21

ENV RAM="8G"
ENV JAVA_HOME=/opt/java/openjdk

WORKDIR /app

COPY --from=build /app/*.jar ./server.jar
COPY ./* ./

RUN chmod 777 /app/*

# Accept EULA by setting EULA=true
RUN echo "eula=true" > eula.txt

EXPOSE 25565

CMD bash ./wrapper.sh
