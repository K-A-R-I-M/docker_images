FROM openjdk:16
ENV RAM=1.2G
ENV JAVA_HOME=/opt/java/openjdk 
ENV PATH=/opt/java/openjdk/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/src/app
COPY ./server.jar /usr/src/app/server.jar
WORKDIR /usr/src/app
EXPOSE 25565
RUN java -jar server.jar nogui
RUN sed -i "s/eula=false/eula=true/g" /usr/src/app/eula.txt
CMD ["java", "-Xmx1024M", "-Xms1024M", "-jar", "server.jar", "nogui"]