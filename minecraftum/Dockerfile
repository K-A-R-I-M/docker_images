FROM docker.io/azul/zulu-openjdk:21-latest

ENV JAVA_HOME=/opt/java/openjdk

WORKDIR /app

RUN chmod 777 /app/

EXPOSE 25565

ENTRYPOINT ["java", "-Xms1G", "-Xmx4G", "-jar", "./paper.jar", "nogui"]