#!/bin/bash
sed -i "s/eula=false/eula=true/g" /usr/src/app/eula.txt
java -Xmx1024M -Xms1024M -jar server.jar nogui