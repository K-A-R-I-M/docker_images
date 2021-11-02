FROM openjdk:16
ENV RAM=1.2G
ENV JAVA_HOME=/opt/java/openjdk
COPY ./server.jar /usr/src/app/server.jar
WORKDIR /usr/src/app
EXPOSE 25565
RUN java -jar server.jar nogui
RUN sed -i "s/eula=false/eula=true/g" /usr/src/app/eula.txt
CMD ["java", "-Xmx1024M", "-Xms1024M", "-jar", "server.jar", "nogui"]
