# fallguard_utils.py : communication série avec le bracelet (ESP32 DevKit ou XIAO ESP32C3)
# Même rôle que serre_utils.py dans le cours Aliot (serre connectée).
#
# Installation : pip install pyserial
#
# Protocole (voir fallguard_esp32_serie.ino) :
#   bracelet -> PC : "D:bpm:accel:rssi:etat:doigt:type:rot"   (mesures, 1 fois par seconde ;
#                    rot = rotation max du poignet en deg/s, pour vérifier les gestes)
#                    "E:alerte:chute" / "E:alerte:sos" / "E:annule" / "E:acquitte"  (événements)
#                    "W:Chambre,-48;Salon,-71"  (balises de pièce captées, toutes les 5 s ;
#                    ";!" à la fin = scan immédiat demandé par une préalerte ou une alerte)
#   PC -> bracelet : a = arrêter l'alarme, t = tester, o = SOS, c = simuler une chute, r = rappel,
#                    e = détection activée, x = détection
#                    coupée, s + 1 octet = seuil de chute en dixièmes de g.
#                    Gestes (itération 3) : v = ça va (annule la préalerte), h = aide (alerte
#                    tout de suite), n = appel non urgent, m = buzzer coupé 5 min (« chut »).
#
# SIMULATION = True : pas besoin de carte. Le module invente des mesures (normal -> chute
# probable -> alerte), pour construire et tester l'interface ALIVEcode.

import threading
import time

SIMULATION = False        # True = données simulées, aucune carte branchée
PORT = None               # ex. "COM5" ; None = détection automatique
VITESSE = 115200

ser = None
# Lignes de débogage du bracelet affichées dans le terminal (pour régler la détection de chute)
MOTS_DEBOGAGE = ("Impact", "Verification", "PREALERTE", "ALERTE", "Seuil", "Chute", "Prealerte",
                 "Alarme", "TEST", "Rappel", "Detection")
verrou = threading.Lock()

# ---------- état de la simulation ----------
_sim = {"etat": "repos", "debut": time.time(), "detection": True, "scan": time.time(),
        "piece": "Chambre"}


def trouver_port():
    from serial.tools import list_ports
    ports = list(list_ports.comports())
    marques = ("CP210", "CH340", "CH910", "USB SERIAL", "USB-SERIAL", "USB JTAG", "UART")
    for p in ports:
        if any(m in (p.description or "").upper() for m in marques):
            return p.device
    if ports:
        return ports[0].device
    raise IOError("Aucun port série trouvé : carte branchée ? (ou mettre SIMULATION = True)")


def ouvrir():
    """Ouvre le port série. L'ESP32 redémarre à l'ouverture : on attend 2 secondes."""
    global ser
    if SIMULATION:
        print("SIMULATION : aucune carte, données inventées")
        return
    import serial
    port = PORT or trouver_port()
    ser = serial.Serial(port, VITESSE, timeout=2)
    print("Port série ouvert :", port)
    time.sleep(2)
    ser.reset_input_buffer()


def _ecrire(octets):
    if SIMULATION:
        _commande_simulee(octets)
        return
    with verrou:
        ser.write(octets)


# ---------- commandes vers le bracelet ----------
def arreter_alarme():
    _ecrire(b"a")


def tester_alarme():
    _ecrire(b"t")


def declencher_sos():
    _ecrire(b"o")


def ca_va():
    """Préalerte : la personne répond « ça va » (1 doigt) -> préalerte annulée."""
    _ecrire(b"v")


def demander_aide():
    """Préalerte : la personne demande de l'aide (2 doigts) -> alerte tout de suite."""
    _ecrire(b"h")


def appel_non_urgent():
    """Main levée : 2 bips et « Appel envoyé » sur l'écran (au repos seulement)."""
    _ecrire(b"n")


def couper_son():
    """Geste « chut » : le buzzer se tait 5 min, l'alerte continue sur le tableau de bord."""
    _ecrire(b"m")


def rappel_bracelet():
    """Le bracelet fait 3 bips et affiche « Mettez votre bracelet » (s'il est au repos)."""
    _ecrire(b"r")


def simuler_chute():
    """Démo : le bracelet fait comme s'il avait confirmé une chute (préalerte puis alerte)."""
    _ecrire(b"c")


def set_detection(active):
    _ecrire(b"e" if active else b"x")


def set_seuil(seuil_g):
    """Seuil de chute en g (entre 1,2 et 4,0)."""
    valeur = int(round(max(1.2, min(4.0, float(seuil_g))) * 10))
    _ecrire(b"s" + bytes([valeur]))


# ---------- lecture ----------
def lire():
    """Lit une ligne du bracelet. Retourne ("D", dict) pour des mesures, ("E", liste) pour un
    événement, ("W", {pièce: rssi}, urgent) pour un scan des balises (urgent = scan immédiat
    d'une préalerte/alerte), ou None si rien d'exploitable
    (délai dépassé, ligne de débogage...)."""
    if SIMULATION:
        time.sleep(1)
        return _lire_simulee()
    ligne = ser.readline().decode("utf-8", errors="ignore").strip()
    try:
        if ligne.startswith("D:"):
            p = ligne[2:].split(":")
            return "D", {"bpm": int(p[0]), "accel": float(p[1]), "rssi": int(p[2]),
                         "etat": p[3], "doigt": p[4] == "1", "type": p[5],
                         "rot": float(p[6]) if len(p) > 6 else None}
        if ligne.startswith("E:"):
            return "E", ligne[2:].split(":")
        if ligne.startswith(MOTS_DEBOGAGE):
            print("  [bracelet] " + ligne)       # détails de la détection de chute
            return None
        if ligne.startswith("W:"):
            balises = {}
            urgent = False
            for morceau in ligne[2:].split(";"):
                if morceau.strip() == "!":
                    urgent = True
                elif "," in morceau:
                    nom, rssi = morceau.rsplit(",", 1)
                    balises[nom.strip()] = int(rssi)
            return "W", balises, urgent
    except (IndexError, ValueError):
        pass
    return None


# ---------- simulation ----------
def _commande_simulee(octets):
    if octets == b"a" and _sim["etat"] != "repos":
        _sim.update(etat="repos", debut=time.time())
    elif octets == b"t":
        _sim.update(etat="test", debut=time.time())
    elif octets == b"o" and _sim["etat"] == "repos":
        _sim.update(etat="alerte", debut=time.time())
        _file_evenements.append(["alerte", "sos"])
    elif octets == b"c" and _sim["etat"] == "repos" and _sim["detection"]:
        _sim.update(etat="prealerte", debut=time.time())
    elif octets == b"v" and _sim["etat"] == "prealerte":
        _sim.update(etat="repos", debut=time.time())
        _file_evenements.append(["annule"])
    elif octets == b"h" and _sim["etat"] == "prealerte":
        _sim.update(etat="alerte", debut=time.time())
        _file_evenements.append(["alerte", "chute"])
    elif octets == b"m":
        _file_evenements.append(["silence", "debut"])
    elif octets == b"e":
        _sim["detection"] = True
    elif octets == b"x":
        _sim["detection"] = False


_file_evenements = []


def _lire_simulee():
    import random
    ecoule = time.time() - _sim["debut"]
    etat = _sim["etat"]
    ancien = etat
    if etat == "repos" and _sim["detection"] and ecoule > 30:
        etat = "prealerte"
    elif etat == "prealerte" and ecoule > 15:
        etat = "alerte"
        _file_evenements.append(["alerte", "chute"])
    elif etat == "alerte" and ecoule > 15:
        etat = "repos"
        _file_evenements.append(["acquitte"])
    elif etat == "test" and ecoule > 5:
        etat = "repos"
    if etat != ancien:
        _sim.update(etat=etat, debut=time.time())
    if _file_evenements:
        return "E", _file_evenements.pop(0)
    if time.time() - _sim["scan"] >= 5:           # scan des balises toutes les 5 s
        _sim["scan"] = time.time()
        if random.random() < 0.2:                 # de temps en temps, le résident change de pièce
            _sim["piece"] = random.choice(["Chambre", "Salon", "Salle de bain", "Cuisine"])
        balises = {p: random.randint(-90, -75) for p in ["Chambre", "Salon", "Salle de bain", "Cuisine"]}
        balises[_sim["piece"]] = random.randint(-55, -40)
        return "W", balises, False
    calme = etat == "repos"
    return "D", {"bpm": random.randint(68, 78) if calme else random.randint(95, 120),
                 "accel": round(random.uniform(0.97, 1.03), 2) if calme else round(random.uniform(0.3, 2.8), 2),
                 "rssi": random.randint(-70, -55), "etat": etat, "doigt": True,
                 "type": "chute" if etat == "alerte" else "-",
                 "rot": round(random.uniform(0, 120), 0)}
