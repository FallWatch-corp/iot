# Documentation: https://alivecode.ca/docs/aliot
from aliot.aliot_obj import AliotObj

# Création de l'objet à partir du fichier de configuration
watch = AliotObj("watch")


def start():
    # Écrivez le code que vous voulez exécuter une fois que l'objet
    # est connecté au serveur
    pass


# Appel de la fonction start une fois que l'objet se connecte au serveur
watch.on_start(callback=start)

# Connection de l'objet au serveur ALIVEcode
watch.run()
