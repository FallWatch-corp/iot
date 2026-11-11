# reinitialiser_chutes.py : remet à zéro les données des chutes dans le document ALIVEcode.
# ARRÊTER d'abord iteration2.py / aliot run watch (un seul programme connecté à la fois),
# puis lancer depuis le dossier qui contient config.ini :  python reinitialiser_chutes.py
#
# Documentation: https://alivecode.ca/docs/aliot
from aliot.aliot_obj import AliotObj

fallguard = AliotObj("watch")          # même objet que iteration2.py (section de config.ini)


def start():
    fallguard.update_doc({
        "/doc/chutes_total": 0,
        "/doc/historique": [],
        "/doc/derniere_chute": "Aucune",
        "/doc/type_alerte": "-",
        "/doc/piece_chute": "-",
        "/doc/chute": False,
    })
    print("Donnees des chutes remises a zero :", fallguard.get_doc("/doc/chutes_total"),
          fallguard.get_doc("/doc/historique"))
    fallguard.stop()


fallguard.on_start(callback=start)
fallguard.run(retry=False)
