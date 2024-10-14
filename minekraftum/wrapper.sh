#!/bin/bash
sed -i "s/eula=false/eula=true/g" /app/eula.txt
java -Xmx1024M -Xms1024M -jar server.jar nogui