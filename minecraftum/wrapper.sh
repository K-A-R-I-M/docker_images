#!/bin/bash
java -jar ./server.jar nogui
sed -i "s/eula=false/eula=true/g" ./eula.txt
java -Xms1G -Xmx$RAM -jar ./server.jar nogui