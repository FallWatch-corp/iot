# iteration3.py : FallGuard - itération 3 (gestes de la main : caméra du Raspberry Pi + MediaPipe)
# Reprend iteration2.py (base de données ALIVEcode, interface IoT) et ajoute gestes.py :
#   le Pi reconnaît un geste -> commande série vers le bracelet (ESP32/XIAO) -> buzzer / OLED,
#   et le geste s'affiche dans le document (/doc/geste) et dans le journal.
#   Chaque geste n'est accepté que si le poignet a bougé (gyroscope du MPU6050) en même temps :
#   la caméra voit une main, le bracelet confirme que c'est celle du résident.
#
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
# Lancer (sur le Pi) :  python iteration3.py
# Fermer le moniteur série de l'IDE Arduino avant de lancer.
#
# Documentation: https://alivecode.ca/docs/aliot
import datetime
import threading
import time

import fallguard_utils
import gestes
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
# Localisation (un scan toutes les 5 s) : la force de chaque balise est LISSÉE sur les derniers
# scans, puis on change de pièce dès qu'une autre balise dépasse celle de la pièce actuelle d'au
# moins ECART_CHANGEMENT dB. Réagit en 5-10 s, même quand deux balises ont presque la même force,
# sans sauter d'une pièce à l'autre près d'une porte.
# Scan immédiat d'une préalerte/alerte : la pièce est prise directement dans ce scan.
LISSAGE = 0.5                  # poids du nouveau scan (1 = pas de lissage)
ECART_CHANGEMENT = 3           # dB d'avance exigés pour quitter la pièce actuelle
BAISSE_ABSENTE = 5             # dB retirés à une balise à chaque scan où elle n'est pas captée
SCANS_ABSENTE_MAX = 6          # balise oubliée après 6 scans sans elle (environ 30 s) -> « Inconnue »
localisation = {"piece": "Inconnue", "forces": {}, "absences": {}}
# Champs à joindre au PROCHAIN envoi des mesures (un 2e update_doc dans la même seconde se perd)
a_envoyer = {}
verrou_envoi = threading.Lock()     # a_envoyer est aussi rempli par le fil de la caméra
# Statistiques par minute (pour les DONNÉES FROIDES / graphes) : le dataset ALIVEcode se remplit
# quand ces champs changent, donc une ligne par minute au lieu d'une par seconde.
INTERVALLE_STATS = 60                        # secondes
cumul = {"debut": time.time(), "bpm": [], "accel_max": 0.0}


# Champs surveillés par les DÉCLENCHEURS ALIVEcode : on ne les écrit que quand leur valeur
# CHANGE (sinon un déclencheur « /doc/chute == true » pourrait envoyer un courriel chaque seconde).
derniers_envois = {}


def champs_changes(champs):
    """Garde seulement les champs dont la valeur a changé depuis le dernier envoi, et les note
    comme envoyés. Si l'objet n'est pas connecté, aliot JETTE l'envoi sans erreur : on ne
    mémorise rien, pour les renvoyer plus tard."""
    if not fallguard.connected_to_alivecode:
        return {}
    nouveaux = {c: v for c, v in champs.items() if derniers_envois.get(c) != v}
    derniers_envois.update(nouveaux)
    return nouveaux


def maj_si_change(champs):
    nouveaux = champs_changes(champs)
    if nouveaux:
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


detection = {"active": True}


def alterner_detection(value):
    # L'interrupteur peut envoyer True/False, 1/0 ou du texte ("false") : bool("false") = True !
    if isinstance(value, str):
        active = value.strip().lower() in ("true", "1", "on", "oui")
    else:
        active = bool(value)
    print("Interrupteur detection recu :", repr(value), "->", active)
    detection["active"] = active
    fallguard_utils.set_detection(active)
    fallguard.update_doc({"/doc/detection_active": active})
    journal("Detection " + ("activee" if active else "coupee"))


# Gestes « chut » / pouce levé : même effet que l'interrupteur de l'interface
def couper_detection():
    alterner_detection(False)


def activer_detection():
    alterner_detection(True)


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
    if d.get("rot") is not None:                   # rotation max du poignet (fusion des gestes)
        poignet["mesure"] = True
        poignet["recents"] = [(t, r) for t, r in poignet.get("recents", [])
                              if time.time() - t <= FENETRE_POIGNET] + [(time.time(), d["rot"])]
        if d["rot"] >= SEUIL_ROT_GESTE:
            poignet["dernier_mouvement"] = time.time()
    if not liaison["en_ligne"]:
        liaison["en_ligne"] = True
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
    if etat == "alerte" and etat_precedent["etat"] != "alerte":
        # Format « 11/11/2026 a 14h59 » : ALIVEcode transforme « 11/11/2026 14:59:34 » en date UTC.
        quand = datetime.datetime.now().strftime("%d/%m/%Y a %Hh%M")
        derniere_alerte.update(date=quand, piece=localisation["piece"], type=d["type"])
    mesures = {
        "/doc/bpm": d["bpm"],
        "/doc/accel": d["accel"],
        "/doc/rssi": d["rssi"],
        "/doc/niveau": etat,
        "/doc/statut": statut,
        "/doc/feu": FEU.get(affichage, "GREEN"),
    }
    # Dernière alerte : renvoyée avec les mesures de chaque seconde (un envoi séparé au moment de
    # l'alerte se perdait parmi les autres envois de la même seconde).
    if derniere_alerte["date"]:
        mesures["/doc/derniere_chute"] = derniere_alerte["date"]
        mesures["/doc/type_alerte"] = derniere_alerte["type"]
        mesures["/doc/piece_chute"] = derniere_alerte["piece"]
    if porte != liaison.get("porte"):
        liaison["porte"] = porte
        journal("Bracelet porte" if porte else "Bracelet NON PORTE (pas de contact depuis "
                + str(DELAI_NON_PORTE) + " s)")
    # Champs des déclencheurs (écrits seulement quand ils changent) : dans le MÊME envoi que les
    # mesures. Un 2e update_doc dans la même seconde se perdait (porte ne changeait jamais).
    mesures.update(champs_changes({"/doc/en_ligne": True, "/doc/porte": porte,
                                   "/doc/chute": etat == "alerte",
                                   "/doc/appel": time.time() < etat_gestes["appel_jusqua"],
                                   "/doc/silence": etat_gestes["silence"]}))
    if fallguard.connected_to_alivecode:       # pièce, balises du dernier scan, dernier geste
        with verrou_envoi:
            mesures.update(a_envoyer)
            a_envoyer.clear()
    fallguard.update_doc(mesures)
    cumuler_stats(d, porte)
    if etat != etat_precedent["etat"]:
        if etat == "prealerte":
            journal("Chute probable (" + localisation["piece"] + ") : annulation possible pendant 15 s")
        elif etat == "alerte":
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


def traiter_balises(balises, urgent=False):
    """Scan des balises {pièce: rssi}. urgent = scan immédiat d'une préalerte/alerte : la personne
    ne bouge plus, la balise la plus forte de CE scan donne la pièce de la chute."""
    forces, absences = localisation["forces"], localisation["absences"]
    for nom, rssi in balises.items():
        if nom in forces and not urgent:
            forces[nom] = round(LISSAGE * rssi + (1 - LISSAGE) * forces[nom], 1)
        else:
            forces[nom] = rssi
        absences[nom] = 0
    for nom in list(forces):                      # balises non captées : elles s'affaiblissent
        if nom not in balises:
            absences[nom] = absences.get(nom, 0) + 1
            forces[nom] -= BAISSE_ABSENTE
            if absences[nom] >= SCANS_ABSENTE_MAX:
                del forces[nom], absences[nom]
    actuelle = localisation["piece"]
    if urgent and balises:
        nouvelle = max(balises, key=balises.get)
    elif not forces:
        nouvelle = "Inconnue"
    else:
        meilleure = max(forces, key=forces.get)
        if actuelle not in forces or forces[meilleure] >= forces[actuelle] + ECART_CHANGEMENT:
            nouvelle = meilleure
        else:
            nouvelle = actuelle
    a_envoyer["/doc/balises"] = balises
    if nouvelle != actuelle:
        localisation["piece"] = nouvelle
        a_envoyer["/doc/piece"] = nouvelle
        journal("Resident localise : " + nouvelle + (" (scan d'alerte)" if urgent else ""))
    # Alerte déjà notée avec l'ancienne pièce (SOS : le scan arrive juste après) : on corrige
    if urgent and derniere_alerte["date"] and etat_precedent["etat"] == "alerte":
        derniere_alerte["piece"] = localisation["piece"]


def traiter_evenement(e):
    if e[0] == "annule":
        journal("Prealerte annulee par le resident (fausse alerte)")
    elif e[0] == "acquitte":
        journal("Alerte arretee avec le bouton du bracelet")
    elif e[0] == "silence" and len(e) > 1:
        etat_gestes["silence"] = e[1] == "debut"
        journal("Buzzer coupe pour 5 min (geste chut)" if etat_gestes["silence"]
                else "Fin du silence : le buzzer fonctionne de nouveau")


# ---------- Gestes (itération 3) ----------
# Fusion caméra + bracelet : un geste n'est accepté que si le gyroscope du bracelet a dépassé
# SEUIL_ROT_GESTE dans les FENETRE_POIGNET dernières secondes (lever la main fait tourner le
# poignet). Évite qu'une autre personne dans la pièce, ou la télé, commande le bracelet.
# Valeurs INVENTÉES, à régler par essais.
FUSION_POIGNET = True
SEUIL_ROT_GESTE = 25          # deg/s
FENETRE_POIGNET = 5           # s
DUREE_APPEL = 60              # s : /doc/appel reste vrai ce temps (déclencheur -> courriel)
poignet = {"dernier_mouvement": 0.0, "mesure": False}
etat_gestes = {"appel_jusqua": 0.0, "silence": False}


def poignet_a_bouge():
    """True / False, ou None si on ne peut pas vérifier (bracelet hors ligne, ancien programme)."""
    if not FUSION_POIGNET:
        return True
    if not liaison["en_ligne"] or not poignet["mesure"]:
        return None
    return time.time() - poignet["dernier_mouvement"] <= FENETRE_POIGNET


def choisir_action(geste, etat):
    """(texte de l'action, fonction, urgent) selon le geste ET l'état du bracelet, ou None.
    Urgent = jamais refusé par la vérification du poignet (rater un appel à l'aide est pire
    qu'une fausse alerte)."""
    if geste == "signal_aide":
        if etat == "prealerte":
            return "Aide demandee (signal d'aide)", fallguard_utils.demander_aide, True
        if etat in ("repos", "test"):
            return "SOS (signal d'aide)", fallguard_utils.declencher_sos, True
    elif geste in ("un_doigt", "pouce") and etat == "prealerte":
        return "Ca va : prealerte annulee", fallguard_utils.ca_va, False
    elif geste == "pouce" and etat in ("alerte", "test"):
        return "Alarme arretee", fallguard_utils.arreter_alarme, False
    elif geste == "deux_doigts" and etat == "prealerte":
        return "Aide demandee : alerte tout de suite", fallguard_utils.demander_aide, True
    elif geste == "deux_doigts" and etat == "repos":
        return "Test de l'alarme", fallguard_utils.tester_alarme, False
    elif geste == "main_levee" and etat == "repos":
        return "Appel non urgent envoye", appel_non_urgent, False
    # « chut » = détection OFF, pouce levé = détection ON (seulement au repos : pendant une
    # préalerte / alerte, le pouce annule ou arrête l'alarme, voir plus haut)
    elif geste == "chut" and etat == "repos":
        if not detection["active"]:
            return "Detection deja coupee", lambda: None, False
        return "Detection coupee (interrupteur OFF)", couper_detection, False
    elif geste == "pouce" and etat == "repos":
        if detection["active"]:
            return "Detection deja active", lambda: None, False
        return "Detection activee (interrupteur ON)", activer_detection, False
    return None


def appel_non_urgent():
    fallguard_utils.appel_non_urgent()
    etat_gestes["appel_jusqua"] = time.time() + DUREE_APPEL


def quand_geste(geste):
    """Appelée par gestes.py (fil de la caméra) à chaque geste reconnu."""
    nom = gestes.NOMS[geste]
    etat = etat_precedent["etat"]
    choix = choisir_action(geste, etat)
    if choix is None:
        resultat = "aucune action (etat : " + etat + ")"
    else:
        texte, fonction, urgent = choix
        bouge = poignet_a_bouge()
        if bouge is False and not urgent:
            rot_max = max([r for t, r in poignet.get("recents", [])] or [0])
            resultat = ("REFUSE : le bracelet n'a pas bouge (rotation max " + str(int(rot_max))
                        + " deg/s en " + str(FENETRE_POIGNET) + " s, seuil "
                        + str(SEUIL_ROT_GESTE) + ")")
        else:
            fonction()
            resultat = texte
            if bouge is None:
                resultat += " (non verifie par le bracelet)"
            elif bouge is False:
                resultat += " (urgent : accepte sans mouvement du bracelet)"
    with verrou_envoi:
        a_envoyer["/doc/geste"] = nom
        a_envoyer["/doc/geste_action"] = resultat
    journal("Geste " + nom + " : " + resultat)


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
    maj_si_change({"/doc/en_ligne": False, "/doc/chute": False, "/doc/appel": False,
                   "/doc/silence": False})
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
    localisation.update(piece="Inconnue", forces={}, absences={})
    fallguard.update_doc({"/doc/piece": "Inconnue", "/doc/balises": {},
                          "/doc/geste": "Aucun", "/doc/geste_action": "-"})
    journal("Bracelet connecte, seuil de chute = " + str(seuil) + " g")

    # Gestes : la caméra tourne dans son propre fil et appelle quand_geste()
    detecteur = gestes.DetecteurGestes(quand_geste)
    if detecteur.disponible:
        detecteur.demarrer()
        journal("Camera prete : gestes actifs")
    else:
        journal("Camera indisponible : gestes desactives (le bracelet fonctionne quand meme)")

    while True:
        try:
            lu = fallguard_utils.lire()
            if lu is None:
                verifier_liaison()
                continue
            if lu[0] == "D":
                traiter_mesures(lu[1])
            elif lu[0] == "W":
                traiter_balises(lu[1], lu[2])
            else:
                traiter_evenement(lu[1])
        except KeyboardInterrupt:
            break
    fallguard.stop()


fallguard.on_start(callback=start)
fallguard.run()
