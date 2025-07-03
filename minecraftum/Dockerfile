FROM docker.io/library/openjdk:21

ENV JAVA_HOME=/opt/java/openjdk

WORKDIR /app

RUN chmod 777 /app/*

EXPOSE 25565

ENTRYPOINT ["java", "-Xms1G", "-Xmx12G", "-jar", "./paper.jar", "nogui"]