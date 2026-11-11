# iteration2.py : FallGuard - itération 2 (base de données ALIVEcode, Python, interface IoT)
#
# Même structure que le cours Aliot (serre connectée) :
#   - le bracelet (ESP32 / XIAO) envoie ses mesures en série (voir fallguard_utils.py) ;
#   - ce programme les envoie au DOCUMENT du projet avec update_doc (champs "/doc/...") ;
#   - le journal (composant "Mylog") et l'avertisseur ("Mybuzzer") sont alimentés avec
#     update_component ;
#   - les boutons, l'interrupteur et le curseur de l'interface appellent on_action_recv.
#
# Installation :  pip install aliot-py pyserial
# Dans le dossier : aliot init  puis  aliot new watch   (ou copier config.ini.exemple en
# config.ini et y coller obj_id et auth_token de l'objet).
# Lancer :  python iteration2.py        (ou : aliot run watch, qui lance watch/watch.py)
# Fermer le moniteur série de l'IDE Arduino avant de lancer.
#
# Documentation: https://alivecode.ca/docs/aliot
import datetime
import time

import fallguard_utils
from aliot.aliot_obj import AliotObj

fallguard = AliotObj("watch")          # nom de la section dans config.ini

FREQUENCE_ALARME = 450                       # Hz, pour le composant buzzer
FEU = {"repos": "GREEN", "prealerte": "YELLOW", "test": "YELLOW", "alerte": "RED",
       "non_porte": "YELLOW", "hors_ligne": "RED"}
STATUTS = {
    "repos": "Normal",
    "prealerte": "Chute probable : le resident peut annuler (15 s)",
    "alerte": "ALERTE : chute detectee",
    "test": "Test de l'alarme",
    "non_porte": "Bracelet NON PORTE : la chute ne peut pas etre detectee",
    "hors_ligne": "Bracelet HORS LIGNE : aucune donnee recue",
}

etat_precedent = {"etat": "repos"}
DELAI_HORS_LIGNE = 5                         # secondes sans mesure = bracelet hors ligne
DELAI_NON_PORTE = 30                         # secondes sans contact au poignet = non porté
liaison = {"en_ligne": False, "derniere_mesure": 0.0, "sans_contact_depuis": None}
# Localisation : la pièce change seulement si la même balise est la plus forte 2 scans de suite
# (évite que la pièce saute d'une valeur à l'autre près d'une porte).
SCANS_POUR_CHANGER = 2
localisation = {"piece": "Inconnue", "candidat": None, "compte": 0}
# Statistiques par minute (pour les DONNÉES FROIDES / graphes) : le dataset ALIVEcode se remplit
# quand ces champs changent, donc une ligne par minute au lieu d'une par seconde.
INTERVALLE_STATS = 60                        # secondes
cumul = {"debut": time.time(), "bpm": [], "accel_max": 0.0}


# Champs surveillés par les DÉCLENCHEURS ALIVEcode : on ne les écrit que quand leur valeur
# CHANGE (sinon un déclencheur « /doc/chute == true » pourrait envoyer un courriel chaque seconde).
derniers_envois = {}


def maj_si_change(champs):
    # Si l'objet n'est pas connecté, aliot JETTE l'envoi sans erreur : on ne mémorise la valeur
    # que si elle est vraiment partie, pour la renvoyer sinon.
    if not fallguard.connected_to_alivecode:
        return
    nouveaux = {c: v for c, v in champs.items() if derniers_envois.get(c) != v}
    if nouveaux:
        derniers_envois.update(nouveaux)
        fallguard.update_doc(nouveaux)


# ---------- Journal et alarme (update_component) ----------
def journal(texte):
    print(texte)
    fallguard.update_component("Mylog", texte)


# ---------- Actions de l'interface (on_action_recv) ----------
def arreter_alarme(data=None):
    fallguard_utils.arreter_alarme()
    journal("Arret de l'alarme demande depuis l'interface")


def rappel_bracelet(data=None):
    """Procédure ALIVEcode (déclencheur /doc/porte == false) : rappel sur le bracelet."""
    fallguard_utils.rappel_bracelet()
    journal("Rappel envoye au bracelet : mettez votre bracelet")


HISTORIQUE_MAX = 20                          # nombre de chutes gardées dans /doc/historique
statistiques = {"chutes_total": 0, "historique": []}
derniere_alerte = {"date": "", "piece": "", "type": ""}


def enregistrer_chute(data=None):
    """Procédure ALIVEcode (déclencheur /doc/chute == true) : compteur + historique.
    Lecture dans la base (get_doc), puis mise à jour (update_doc)."""
    try:
        total = fallguard.get_doc("/doc/chutes_total")
        historique = fallguard.get_doc("/doc/historique")
    except Exception:
        total, historique = None, None
    total = int(total) if total is not None else statistiques["chutes_total"]
    if not isinstance(historique, list):
        historique = statistiques["historique"]
    # Un SOS (appui long sur le bouton) n'est pas une chute : il va dans l'historique (type "sos")
    # mais n'augmente pas chutes_total.
    est_sos = derniere_alerte["type"] == "sos"
    if not est_sos:
        total += 1
    historique = (historique + [dict(derniere_alerte)])[-HISTORIQUE_MAX:]
    statistiques.update(chutes_total=total, historique=historique)
    fallguard.update_doc({"/doc/chutes_total": total, "/doc/historique": historique})
    if est_sos:
        journal("SOS enregistre dans l'historique (non compte comme chute, total : " + str(total) + ")")
    else:
        journal("Chute enregistree (total : " + str(total) + ")")


def simuler_chute(data=None):
    fallguard_utils.simuler_chute()
    journal("Chute SIMULEE demandee depuis l'interface (demo)")


def tester_alarme(data=None):
    fallguard_utils.tester_alarme()
    journal("Test de l'alarme demande depuis l'interface")
    fallguard.update_component("Mybuzzer", FREQUENCE_ALARME)


def alterner_detection(value):
    active = bool(value)
    fallguard_utils.set_detection(active)
    fallguard.update_doc({"/doc/detection_active": active})
    journal("Detection " + ("activee" if active else "coupee"))


def regler_seuil(value):
    seuil = float(value)
    fallguard_utils.set_seuil(seuil)
    fallguard.update_doc({"/doc/seuil_chute": seuil})
    journal("Seuil de chute regle a " + str(seuil) + " g")


fallguard.on_action_recv(action_id="arreter_alarme", callback=arreter_alarme)
fallguard.on_action_recv(action_id="tester_alarme", callback=tester_alarme)
fallguard.on_action_recv(action_id="alterner_detection", callback=alterner_detection)
fallguard.on_action_recv(action_id="regler_seuil", callback=regler_seuil)
fallguard.on_action_recv(action_id="simuler_chute", callback=simuler_chute)
# Actions appelées par les PROCÉDURES ALIVEcode (Envoi d'actions)
fallguard.on_action_recv(action_id="rappel_bracelet", callback=rappel_bracelet)
fallguard.on_action_recv(action_id="enregistrer_chute", callback=enregistrer_chute)


# ---------- Traitement de ce que le bracelet envoie ----------
def traiter_mesures(d):
    etat = d["etat"]
    liaison["derniere_mesure"] = time.time()
    if not liaison["en_ligne"]:
        liaison["en_ligne"] = True
        maj_si_change({"/doc/en_ligne": True})
        journal("Bracelet en ligne")
    # Porté : contact avec la peau, ou perte de contact depuis moins de DELAI_NON_PORTE s
    # (le capteur perd souvent le contact quelques secondes quand la personne bouge).
    if d["doigt"]:
        liaison["sans_contact_depuis"] = None
        porte = True
    else:
        if liaison["sans_contact_depuis"] is None:
            liaison["sans_contact_depuis"] = time.time()
        porte = time.time() - liaison["sans_contact_depuis"] < DELAI_NON_PORTE
    # Une alerte, une préalerte ou un test passe avant « non porté »
    affichage = "non_porte" if (etat == "repos" and not porte) else etat
    statut = STATUTS.get(affichage, affichage)
    if etat in ("prealerte", "alerte"):
        statut += " - piece : " + localisation["piece"]
    fallguard.update_doc({
        "/doc/bpm": d["bpm"],
        "/doc/accel": d["accel"],
        "/doc/rssi": d["rssi"],
        "/doc/niveau": etat,
        "/doc/statut": statut,
        "/doc/feu": FEU.get(affichage, "GREEN"),
    })
    if porte != liaison.get("porte"):
        liaison["porte"] = porte
        journal("Bracelet porte" if porte else "Bracelet NON PORTE (pas de contact depuis "
                + str(DELAI_NON_PORTE) + " s)")
    if etat == "alerte" and etat_precedent["etat"] != "alerte":
        quand = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        derniere_alerte.update(date=quand, piece=localisation["piece"], type=d["type"])
    maj_si_change({"/doc/porte": porte, "/doc/chute": etat == "alerte"})
    cumuler_stats(d, porte)
    if etat != etat_precedent["etat"]:
        if etat == "prealerte":
            journal("Chute probable (" + localisation["piece"] + ") : annulation possible pendant 15 s")
        elif etat == "alerte":
            quand = derniere_alerte["date"]
            fallguard.update_doc({"/doc/type_alerte": d["type"], "/doc/derniere_chute": quand,
                                  "/doc/piece_chute": localisation["piece"]})
            journal("ALERTE (" + d["type"] + ") dans : " + localisation["piece"])
            fallguard.update_component("Mybuzzer", FREQUENCE_ALARME)
        etat_precedent["etat"] = etat


def cumuler_stats(d, porte):
    """Accumule les mesures ; toutes les INTERVALLE_STATS secondes, écrit moyenne/min/max."""
    if porte and d["doigt"] and 30 <= d["bpm"] <= 220:    # BPM valides seulement
        cumul["bpm"].append(d["bpm"])
    cumul["accel_max"] = max(cumul["accel_max"], d["accel"])
    if time.time() - cumul["debut"] < INTERVALLE_STATS:
        return
    champs = {"/doc/accel_max": round(cumul["accel_max"], 2),
              "/doc/piece_stats": localisation["piece"]}
    if cumul["bpm"]:
        champs["/doc/bpm_moyen"] = round(sum(cumul["bpm"]) / len(cumul["bpm"]))
        champs["/doc/bpm_min"] = min(cumul["bpm"])
        champs["/doc/bpm_max"] = max(cumul["bpm"])
    fallguard.update_doc(champs)
    cumul.update(debut=time.time(), bpm=[], accel_max=0.0)


def verifier_liaison():
    """Plus de mesures depuis DELAI_HORS_LIGNE secondes : bracelet débranché ou éteint."""
    if liaison["en_ligne"] and time.time() - liaison["derniere_mesure"] > DELAI_HORS_LIGNE:
        liaison["en_ligne"] = False
        maj_si_change({"/doc/en_ligne": False})
        fallguard.update_doc({"/doc/bpm": 0,
                              "/doc/feu": FEU["hors_ligne"],
                              "/doc/statut": STATUTS["hors_ligne"]})
        journal("Bracelet HORS LIGNE (plus de donnees)")


def traiter_balises(balises):
    """Scan des balises {pièce: rssi} : la balise captée le plus fort donne la pièce."""
    meilleure = max(balises, key=balises.get) if balises else "Inconnue"
    if meilleure == localisation["candidat"]:
        localisation["compte"] += 1
    else:
        localisation["candidat"] = meilleure
        localisation["compte"] = 1
    champs = {"/doc/balises": balises}
    if meilleure != localisation["piece"] and localisation["compte"] >= SCANS_POUR_CHANGER:
        localisation["piece"] = meilleure
        champs["/doc/piece"] = meilleure
        journal("Resident localise : " + meilleure)
    fallguard.update_doc(champs)


def traiter_evenement(e):
    if e[0] == "annule":
        journal("Prealerte annulee par le resident (fausse alerte)")
    elif e[0] == "acquitte":
        journal("Alerte arretee avec le bouton du bracelet")


deja_demarre = {"oui": False}


def start():
    # aliot rappelle start() à CHAQUE reconnexion : on ne rouvre pas le port série
    # (déjà ouvert = erreur sous Windows) et on ne lance pas une 2e boucle de lecture.
    if deja_demarre["oui"]:
        derniers_envois.clear()          # renvoyer porte / chute / en_ligne après une coupure
        journal("Reconnecte a ALIVEcode")
        return
    deja_demarre["oui"] = True
    fallguard_utils.ouvrir()

    # Lecture dans la base de données (get_doc) : on reprend le seuil déjà enregistré
    try:
        seuil = fallguard.get_doc("/doc/seuil_chute")
        seuil = float(seuil) if seuil is not None else 2.5
    except Exception:
        seuil = 2.5
    fallguard_utils.set_seuil(seuil)
    maj_si_change({"/doc/en_ligne": False, "/doc/chute": False})
    fallguard.update_doc({"/doc/seuil_chute": seuil, "/doc/detection_active": True,
                         "/doc/feu": FEU["hors_ligne"],
                         "/doc/statut": STATUTS["hors_ligne"]})
    # Champs écrits seulement lors d'une alerte : on les crée dès le départ pour pouvoir les
    # choisir dans l'éditeur d'interface (sans effacer une vraie alerte déjà enregistrée).
    # Chaque champ est vérifié séparément (get_doc) : on ne crée que ceux qui manquent.
    valeurs_depart = {"/doc/derniere_chute": "Aucune", "/doc/type_alerte": "-",
                      "/doc/piece_chute": "-", "/doc/chutes_total": 0, "/doc/historique": []}
    for champ, valeur in valeurs_depart.items():
        try:
            deja = fallguard.get_doc(champ)
        except Exception:
            deja = None
        if not deja:
            fallguard.update_doc({champ: valeur})
        elif champ == "/doc/chutes_total":          # reprise des statistiques déjà enregistrées
            statistiques["chutes_total"] = int(deja)
        elif champ == "/doc/historique" and isinstance(deja, list):
            statistiques["historique"] = deja
    fallguard.update_doc({"/doc/piece": "Inconnue", "/doc/balises": {}})
    journal("Bracelet connecte, seuil de chute = " + str(seuil) + " g")

    while True:
        try:
            lu = fallguard_utils.lire()
            if lu is None:
                verifier_liaison()
                continue
            if lu[0] == "D":
                traiter_mesures(lu[1])
            elif lu[0] == "W":
                traiter_balises(lu[1])
            else:
                traiter_evenement(lu[1])
        except KeyboardInterrupt:
            break
    fallguard.stop()


fallguard.on_start(callback=start)
fallguard.run()
