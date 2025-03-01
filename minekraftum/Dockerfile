FROM docker.io/library/openjdk:21
ENV RAM="8G"
ENV JAVA_HOME=/opt/java/openjdk
WORKDIR /app
COPY ./server.jar /app/server.jar
COPY ./wrapper.sh /wrapper.sh
EXPOSE 25565
CMD ["/wrapper.sh"]
