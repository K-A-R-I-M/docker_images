#!/bin/bash
java -jar server.jar nogui
sed -i "s/eula=false/eula=true/g" /app/eula.txt
java -Xms 1G -Xmx $RAM -jar server.jar nogui