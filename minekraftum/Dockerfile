FROM docker.io/library/openjdk:21
ENV RAM=1.2G
ENV JAVA_HOME=/opt/java/openjdk
WORKDIR /usr/src/app
COPY ./server.jar ./
EXPOSE 25565
RUN java -jar server.jar nogui
RUN sed -i "s/eula=false/eula=true/g" /usr/src/app/eula.txt
CMD ["java", "-Xmx1024M", "-Xms1024M", "-jar", "server.jar", "nogui"]
