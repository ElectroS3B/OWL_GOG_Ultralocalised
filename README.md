Here you will find a modified version of the OWL software developed by Guy Coleman: https://github.com/geezacoleman/OpenWeedLocator/tree/main

This version allows for weed detection in an onion field (using the GOG module). A trained model is included for this purpose, and it can be further refined. 
You will also find a program that allows you to connect to a Flask server on the Raspberry Pi from a web page on a PC or smartphone on the same network, enabling you to remotely modify the config.ini file (configOWL.py).
Many thanks to Guy Coleman for the fantastic work he has done developing OWL.


In the Hailo folder of the Hailo branch, you will find a modified OWL that allows you to use Guy Coleman's dashboard with the hailo8 module (ai hat + hailo8 on a Raspberry Pi 5; I'm using the 26-top version). In the model folder, you will find a trained model that can detect weeds in an onion crop.
