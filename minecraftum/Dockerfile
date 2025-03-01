FROM docker.io/library/openjdk:21

ENV RAM="8G"
ENV JAVA_HOME=/opt/java/openjdk

WORKDIR /app

COPY ./server.jar /app/server.jar
RUN chmod 777 /app/server.jar

COPY ./wrapper.sh /app/wrapper.sh
RUN chmod 777 /app/wrapper.sh

EXPOSE 25565

CMD bash ./wrapper.sh
