# FallGuard : pont Raspberry Pi  <->  tableau de bord ALIVEcode (aliot-py) + vérification caméra
#
# Rôle du programme :
#   - Les bracelets (ESP32 et/ou XIAO) envoient leurs mesures au Pi par HTTP (POST /donnees,
#     toutes les 2 s). Le Pi les publie dans le DOCUMENT de chaque objet ALIVEcode (aliot-py).
#   - Les actions et réglages du tableau de bord (arrêter, tester, détection, seuil) sont
#     renvoyés au bracelet dans la réponse de sa prochaine requête.
#   - Cycle d'une chute :
#       prealerte (bracelet : 15 s pour annuler)  -> /annuler  = fausse alerte, rien d'autre
#                                                 -> /chute    = ALERTE : LED du Pi, vérification
#       par la caméra (fallguard_camera.py), statut mis à jour sur le tableau de bord.
#     LA CAMERA NE CANCELLE JAMAIS UNE ALERTE : elle précise seulement le niveau de confiance.
#   - Bracelet hors ligne ou non porté : signalé sur le tableau de bord.
#
# Installation (une seule fois) :
#   sudo apt install python3-flask
#   pip install aliot-py --break-system-packages        (ou dans un environnement virtuel)
#   (caméra, optionnel : voir fallguard_camera.py)
#
# Configuration : créer un fichier  config.ini  dans le MÊME dossier que ce script
# (voir config.ini.exemple). Lancer le script depuis ce dossier :
#   python3 fallguard_pi_pont.py          Arrêter : Ctrl + C
#
# NE JAMAIS mettre config.ini (il contient les jetons d'authentification) sur GitHub.

import subprocess
import threading
import time
from collections import deque
from configparser import ConfigParser
from time import strftime

from flask import Flask, jsonify, request

try:
    from gpiozero import LED
    led = LED(27)
except Exception:          # pas de GPIO (test sur un PC) : on continue sans LED
    led = None

from aliot.aliot_obj import AliotObj

try:
    from fallguard_camera import Verificateur
except Exception as erreur:
    print("Module camera absent :", erreur)
    Verificateur = None

# ---------- À adapter ----------
# clé utilisée par le bracelet dans sa requête  ->  nom de la section dans config.ini
OBJETS = {
    "esp32": "bracelet_esp32",
    "xiao": "bracelet_xiao",
}
SEUIL_PAR_DEFAUT = 2.5          # en g (impact)
DELAI_ANNULATION = 15           # secondes laissées au résident pour annuler (envoyé au bracelet)
DELAI_HORS_LIGNE = 10           # secondes sans donnée = bracelet considéré hors ligne
DELAI_NON_PORTE = 60            # secondes sans contact au poignet = bracelet considéré non porté
INTERVALLE_DOC = 2.0            # secondes minimum entre deux mises à jour du document
# --------------------------------

app = Flask(__name__)
verificateur = None

TEXTES_VERDICT = {
    "confirmee": "CHUTE CONFIRMEE par la camera (personne au sol)",
    "faux_positif_probable": "Chute signalee, personne DEBOUT sur la camera : a verifier rapidement",
    "personne_non_vue": "Chute signalee, personne non visible par la camera",
    "incertain": "Chute signalee, camera incertaine",
    "non_verifiee": "Chute signalee, camera indisponible",
}
TEXTES_ETAT = {
    "repos": "Normal",
    "prealerte": "Chute probable : annulation possible (15 s)",
    "test": "Test de l'alarme",
}


def prendre_photo():
    """Photo de secours quand la vérification par caméra n'est pas disponible."""
    nom = "chute_" + strftime("%Y%m%d_%H%M%S") + ".jpg"
    commandes = [
        ["rpicam-still", "-o", nom, "-t", "1000"],
        ["libcamera-still", "-o", nom, "-t", "1000"],
        ["libcamera-jpeg", "-o", nom, "-t", "1000"],
        ["raspistill", "-o", nom],
    ]
    for commande in commandes:
        try:
            subprocess.run(commande, check=True)
            print("Photo enregistree :", nom)
            return nom
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    print("Erreur : photo impossible (camera non detectee ?)")
    return None


def en_bool(valeur):
    """Le tableau de bord peut envoyer true/false ou 'true'/'false' : on accepte les deux."""
    if isinstance(valeur, str):
        return valeur.strip().lower() in ("true", "1", "on", "oui")
    return bool(valeur)


class Bracelet:
    """Un bracelet = un objet ALIVEcode (un AliotObj) + une file de commandes pour le bracelet."""

    def __init__(self, cle, nom_aliot):
        self.cle = cle
        self.nom_aliot = nom_aliot
        self.obj = AliotObj(nom_aliot)
        self.commandes = deque()
        self.verrou = threading.Lock()
        self.seuil = SEUIL_PAR_DEFAUT
        self.detection = True
        self.en_ligne = False
        self.derniere_donnee = 0.0
        self.dernier_envoi_doc = 0.0
        self.sans_contact_depuis = None
        self.porte = True
        self.journal = []
        self.etat = "repos"              # dernier état annoncé par le bracelet
        self.texte_alerte = ""           # texte de vérification de l'alerte en cours

        # Actions déclenchées par les boutons du tableau de bord (l'identifiant d'action du
        # bouton, dans l'éditeur d'interface, doit être le même que celui-ci)
        self.obj.on_action_recv("arreter_alarme", callback=self.action_arreter_alarme)
        self.obj.on_action_recv("tester_alarme", callback=self.action_tester_alarme)
        # Champs du document modifiés par l'interrupteur et le curseur du tableau de bord
        self.obj.listen_doc(["/document/seuil_chute", "/document/detection_active"],
                            callback=self.document_modifie)
        self.obj.on_start(callback=self.au_demarrage)

    # ----- Vers le tableau de bord -----
    def maj_doc(self, champs):
        """Envoie des champs au document de l'objet (ignoré tant que l'objet n'est pas connecté)."""
        try:
            self.obj.update_doc({"/document/" + nom: val for nom, val in champs.items()})
        except Exception as erreur:
            print("[" + self.cle + "] maj_doc impossible :", erreur)

    def ecrire_journal(self, texte):
        ligne = strftime("%d/%m/%Y %H:%M:%S") + " : " + texte
        print("[" + self.cle + "] " + ligne)
        self.journal = (self.journal + [ligne])[-10:]
        self.maj_doc({"journal": self.journal})

    def statut_courant(self):
        if not self.en_ligne:
            return "Bracelet hors ligne"
        if self.etat == "alerte":
            return self.texte_alerte or "ALERTE"
        if self.etat == "repos" and not self.porte:
            return "Bracelet non porte"
        return TEXTES_ETAT.get(self.etat, "Normal")

    # ----- Depuis le tableau de bord -----
    def au_demarrage(self):
        self.ecrire_journal("objet connecte a ALIVEcode")
        self.maj_doc({"seuil_chute": self.seuil, "detection_active": self.detection,
                      "chute": False, "en_ligne": self.en_ligne, "porte": self.porte,
                      "statut": self.statut_courant()})

    def action_arreter_alarme(self, valeur=None):
        with self.verrou:
            self.commandes.append("arreter_alarme")
        if led:
            led.off()
        self.texte_alerte = ""
        self.maj_doc({"chute": False})
        self.ecrire_journal("arret de l'alarme demande depuis le tableau de bord")

    def action_tester_alarme(self, valeur=None):
        with self.verrou:
            self.commandes.append("tester_alarme")
        self.ecrire_journal("test de l'alarme demande depuis le tableau de bord")

    def document_modifie(self, champs):
        if "/document/seuil_chute" in champs:
            try:
                self.seuil = max(1.2, min(4.0, float(champs["/document/seuil_chute"])))
            except (TypeError, ValueError):
                pass
        if "/document/detection_active" in champs:
            self.detection = en_bool(champs["/document/detection_active"])
        self.ecrire_journal("reglages : seuil=%.2f g, detection=%s" % (self.seuil, self.detection))

    # ----- Depuis le bracelet -----
    def donnees_recues(self, d):
        maintenant = time.time()
        self.derniere_donnee = maintenant
        nouvel_etat = d.get("etat", "repos")
        changement_etat = nouvel_etat != self.etat
        self.etat = nouvel_etat
        if nouvel_etat != "alerte":
            self.texte_alerte = ""

        # Bracelet porté ? (contact avec la peau depuis moins de DELAI_NON_PORTE secondes)
        if d.get("doigt", False):
            self.sans_contact_depuis = None
            nouveau_porte = True
        else:
            if self.sans_contact_depuis is None:
                self.sans_contact_depuis = maintenant
            nouveau_porte = (maintenant - self.sans_contact_depuis) < DELAI_NON_PORTE
        changement_porte = nouveau_porte != self.porte
        self.porte = nouveau_porte

        retour_en_ligne = not self.en_ligne
        if retour_en_ligne:
            self.en_ligne = True
            self.ecrire_journal("bracelet en ligne")
        if changement_porte:
            self.ecrire_journal("bracelet porte" if self.porte else "bracelet NON PORTE")
        if changement_etat and nouvel_etat == "prealerte":
            self.ecrire_journal("chute probable : le resident peut annuler")

        if (maintenant - self.dernier_envoi_doc >= INTERVALLE_DOC or changement_etat
                or changement_porte or retour_en_ligne):
            self.dernier_envoi_doc = maintenant
            self.maj_doc({
                "en_ligne": True,
                "bpm": int(d.get("bpm", 0)),
                "contact_capteur": bool(d.get("doigt", False)),
                "porte": self.porte,
                "accel": float(d.get("accel", 0)),
                "rssi": int(d.get("rssi", 0)),
                "chute": nouvel_etat == "alerte",
                "niveau": nouvel_etat,
                "statut": self.statut_courant(),
            })
        with self.verrou:
            a_envoyer = list(self.commandes)
            self.commandes.clear()
        return {"commandes": a_envoyer, "seuil": self.seuil, "detection": self.detection,
                "delai": DELAI_ANNULATION}

    def surveiller(self):
        if self.en_ligne and time.time() - self.derniere_donnee > DELAI_HORS_LIGNE:
            self.en_ligne = False
            self.maj_doc({"en_ligne": False, "bpm": 0, "statut": "Bracelet hors ligne",
                          "niveau": "hors_ligne"})
            self.ecrire_journal("bracelet HORS LIGNE")

    def lancer(self):
        threading.Thread(target=lambda: self.obj.run(retry=True), daemon=True).start()


bracelets = {}


def trouver(cle):
    return bracelets.get(cle)


def traiter_alerte(bracelet, type_alerte):
    """Alerte reçue : LED, vérification par la caméra, mise à jour du tableau de bord."""
    if led:
        led.on()
    est_sos = (type_alerte == "sos")
    bracelet.etat = "alerte"
    bracelet.texte_alerte = ("SOS demande par le resident : verification camera en cours" if est_sos
                             else "ALERTE : verification par la camera en cours")
    horodatage = strftime("%d/%m/%Y %H:%M:%S")
    if bracelet:
        bracelet.maj_doc({"chute": True, "niveau": "alerte", "type_alerte": type_alerte,
                          "derniere_chute": horodatage, "statut": bracelet.texte_alerte,
                          "verification": "en cours", "photo": ""})
        bracelet.ecrire_journal("SOS" if est_sos else "CHUTE (alerte envoyee)")

    if verificateur is not None and verificateur.disponible:
        resultat = verificateur.verifier()
    else:
        resultat = {"verdict": "non_verifiee", "angles": [], "photo": prendre_photo()}

    verdict = resultat["verdict"]
    if est_sos:
        texte = "SOS demande par le resident (verification camera : " + verdict + ")"
    else:
        texte = TEXTES_VERDICT.get(verdict, "Chute signalee")
    if bracelet.etat == "alerte":        # l'alerte n'a pas été arrêtée entre-temps
        bracelet.texte_alerte = texte
        bracelet.maj_doc({"verification": verdict, "photo": resultat.get("photo") or "",
                          "statut": texte})
    bracelet.ecrire_journal("verification : " + verdict)


# ---------------- Routes HTTP (appelées par les bracelets) ----------------
@app.route("/donnees", methods=["POST"])
def donnees():
    d = request.get_json(silent=True) or {}
    bracelet = trouver(d.get("objet"))
    if bracelet is None:
        return jsonify({"erreur": "objet inconnu"}), 404
    return jsonify(bracelet.donnees_recues(d))


@app.route("/chute")
def chute():
    cle = request.args.get("objet", "esp32")
    type_alerte = request.args.get("type", "chute")
    print("Alerte recue de", cle, "(" + type_alerte + ")")
    bracelet = trouver(cle)
    if bracelet is None:
        if led:
            led.on()
        threading.Thread(target=prendre_photo).start()
        return "objet inconnu, photo en cours"
    threading.Thread(target=traiter_alerte, args=(bracelet, type_alerte)).start()
    return "alerte recue"


@app.route("/annuler")
def annuler():
    """Le résident a annulé pendant la préalerte : fausse alerte, aucune escalade."""
    bracelet = trouver(request.args.get("objet", "esp32"))
    if bracelet:
        bracelet.etat = "repos"
        bracelet.maj_doc({"chute": False, "niveau": "repos", "statut": "Normal"})
        bracelet.ecrire_journal("prealerte ANNULEE par le resident (fausse alerte)")
    return "annulee"


@app.route("/acquitter")
def acquitter():
    cle = request.args.get("objet", "esp32")
    if led:
        led.off()
    bracelet = trouver(cle)
    if bracelet:
        bracelet.etat = "repos"
        bracelet.texte_alerte = ""
        bracelet.maj_doc({"chute": False, "niveau": "repos", "statut": "Normal"})
        bracelet.ecrire_journal("alerte acquittee sur le bracelet")
    print("Alerte acquittee")
    return "alerte acquittee"


@app.route("/etat")
def etat():
    """Pour tester dans un navigateur : http://ADRESSE_DU_PI:5000/etat"""
    return jsonify({cle: {"en_ligne": b.en_ligne, "etat": b.etat, "porte": b.porte,
                          "seuil": b.seuil, "detection": b.detection,
                          "commandes_en_attente": list(b.commandes)}
                    for cle, b in bracelets.items()})


def boucle_surveillance():
    while True:
        time.sleep(2)
        for bracelet in bracelets.values():
            bracelet.surveiller()


def demarrer():
    global verificateur
    config = ConfigParser()
    if not config.read("config.ini"):
        print("Erreur : config.ini introuvable (voir config.ini.exemple). "
              "Lance le script depuis le dossier qui contient config.ini.")
        raise SystemExit(1)
    if Verificateur is not None:
        verificateur = Verificateur()
    for cle, nom_aliot in OBJETS.items():
        if config.has_section(nom_aliot):
            bracelets[cle] = Bracelet(cle, nom_aliot)
            bracelets[cle].lancer()
            print("Objet ALIVEcode", nom_aliot, "lance pour le bracelet", cle)
        else:
            print("Section [" + nom_aliot + "] absente de config.ini : bracelet", cle, "ignore")
    if not bracelets:
        print("Erreur : aucun objet configure dans config.ini")
        raise SystemExit(1)
    threading.Thread(target=boucle_surveillance, daemon=True).start()


if __name__ == "__main__":
    demarrer()
    print("FallGuard Pi : en attente des bracelets (Ctrl+C pour quitter).")
    app.run(host="0.0.0.0", port=5000, threaded=True)
