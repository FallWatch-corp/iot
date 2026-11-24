# gestes.py : FallGuard - itération 3, reconnaissance des gestes de la main
# (caméra du Raspberry Pi + MediaPipe, avec la bibliothèque du cours quickhands.HandDetector)
#
# HandDetector (quickhands.py) sert à : trouver la main (findHands : lmList, bbox, type),
# compter les doigts levés (fingersUp), mesurer une distance (findDistance : geste « chut »)
# et afficher les infos sur la main (infoOnHand). fingersUp suppose une main verticale ; pour
# reconnaître les gestes, on ajoute des mesures qui marchent aussi main penchée (doigts_tendus,
# position_pouce) : pouce levé (main de côté) et pouce replié dans la paume (signal d'aide).
#
# Gestes reconnus (nom interne -> ce que la personne fait) :
#   "signal_aide" : « Signal for Help » : paume vers la caméra, pouce replié dans la paume,
#                   PUIS doigts refermés sur le pouce (deux étapes, en moins de 3 s)
#   "un_doigt"    : index levé seul (tenu 1 s)
#   "deux_doigts" : index + majeur levés (tenu 1 s)
#   "pouce"       : pouce levé, autres doigts repliés (tenu 1 s)
#   "main_levee"  : main ouverte, 5 doigts, levée au-dessus des yeux (tenue 2 s)
#   "chut"        : index levé posé devant la bouche (tenu 1 s)
# Ce module ne fait que RECONNAÎTRE les gestes ; ce qu'ils déclenchent est décidé dans
# iteration3.py (selon l'état du bracelet).
#
# Vie privée (Loi 25) : les images sont analysées sur le Pi puis oubliées. Aucune image n'est
# enregistrée ni envoyée.
#
# Installation sur le Pi (Raspberry Pi OS Bookworm) :
#   sudo apt install python3-picamera2 python3-opencv     (module caméra du Pi)
#   pip install mediapipe        (dans un venv créé avec --system-site-packages pour picamera2)
# Une webcam USB marche aussi (OpenCV), si picamera2 est absent.
#
# Essai seul (sans bracelet ni ALIVEcode) :  python gestes.py
#
# TOUS LES SEUILS SONT DES VALEURS DE DÉPART, À RÉGLER PAR ESSAIS (les mesures sont affichées
# sur l'image quand AFFICHAGE = True).

import math
import os
import threading
import time

AFFICHAGE = True              # fenêtre avec l'image et le geste reconnu (False = Pi sans écran)
LARGEUR, HAUTEUR = 640, 480
INDEX_WEBCAM = 0              # webcam USB (si pas de module caméra du Pi)

NOMS = {"signal_aide": "Signal d'aide", "un_doigt": "1 doigt", "deux_doigts": "2 doigts",
        "pouce": "Pouce leve", "main_levee": "Main levee", "chut": "Chut"}
DUREES = {"un_doigt": 1.0, "deux_doigts": 1.0, "pouce": 1.0, "main_levee": 2.0, "chut": 1.0}
ETAPE_SIGNAL = 0.3            # s : chaque étape du signal d'aide doit être tenue au moins ce temps
DELAI_SIGNAL = 3.0            # s : temps maximum entre la paume (pouce replié) et le poing
PAUSE_APRES_GESTE = 3.0       # s : aucun nouveau geste juste après un geste reconnu
TOLERANCE_PERTE = 0.3         # s : la main peut « disparaître » ce temps sans casser le geste

# Seuils (en proportion de la taille de la paume : poignet -> base du majeur)
RAPPORT_DOIGT_TENDU = 1.15    # bout du doigt au moins 15 % plus loin du poignet que l'articulation
POUCE_SORTI = -0.1            # position du pouce sur l'axe index -> auriculaire (< = à côté de l'index)
POUCE_REPLIE = 0.4            # (> = sous le majeur / l'annulaire, donc replié dans la paume)
POUCE_PAUME = 0.25            # signal d'aide, étape 1 : pouce replié devant la paume (plus tolérant)
POUCE_HAUT = 0.3              # pouce levé : bout du pouce au-dessus de la base de l'index
DISTANCE_BOUCHE = 0.5         # chut : bout de l'index à moins de 0,5 largeur de visage de la bouche
HAUT_SANS_VISAGE = 0.4        # main levée sans visage vu : poignet dans les 40 % du haut de l'image


# ---------- Caméra ----------
class Camera:
    """Camera du Pi (picamera2), sinon rpicam-vid (sans picamera2), sinon webcam USB. Images en BGR."""

    def __init__(self):
        import cv2
        self.cv2 = cv2
        self.picam = None
        self.rpicam = None
        self.webcam = None
        try:
            from picamera2 import Picamera2
            self.picam = Picamera2()
            # "RGB888" de picamera2 = pixels dans l'ordre B, G, R (format d'OpenCV)
            config = self.picam.create_video_configuration(
                main={"size": (LARGEUR, HAUTEUR), "format": "RGB888"})
            self.picam.configure(config)
            self.picam.start()
            self.nom = "module camera du Pi"
            return
        except Exception:
            self.picam = None
        try:
            from camera_rpicam import CameraRpicam
            self.rpicam = CameraRpicam(LARGEUR, HAUTEUR)
            ok, image = self.rpicam.read()
            if not ok:
                raise IOError("rpicam-vid ne renvoie rien")
            self.nom = "module camera du Pi (rpicam-vid)"
            return
        except Exception:
            if self.rpicam is not None:
                self.rpicam.release()
            self.rpicam = None
        self.webcam = cv2.VideoCapture(INDEX_WEBCAM)
        self.webcam.set(cv2.CAP_PROP_FRAME_WIDTH, LARGEUR)
        self.webcam.set(cv2.CAP_PROP_FRAME_HEIGHT, HAUTEUR)
        if not self.webcam.isOpened():
            raise IOError("aucune camera (ni picamera2, ni rpicam-vid, ni webcam " + str(INDEX_WEBCAM) + ")")
        self.nom = "webcam USB"

    def lire(self):
        if self.picam is not None:
            return self.picam.capture_array("main")
        if self.rpicam is not None:
            ok, image = self.rpicam.read()
            return image if ok else None
        ok, image = self.webcam.read()
        return image if ok else None

    def fermer(self):
        if self.picam is not None:
            self.picam.stop()
        if self.rpicam is not None:
            self.rpicam.release()
        if self.webcam is not None:
            self.webcam.release()


# ---------- Mesures sur la main (21 points de MediaPipe, en pixels) ----------
def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def doigts_tendus(p):
    """[index, majeur, annulaire, auriculaire] : True = tendu. On compare la distance au poignet
    du bout du doigt et de son articulation du milieu (marche même main penchée)."""
    return [_dist(p[bout], p[0]) > RAPPORT_DOIGT_TENDU * _dist(p[art], p[0])
            for bout, art in ((8, 6), (12, 10), (16, 14), (20, 18))]


def position_pouce(p):
    """Position du bout du pouce sur l'axe base de l'index (0) -> base de l'auriculaire (1).
    Négatif = pouce sorti à côté de l'index ; vers 0,5 ou plus = pouce replié dans la paume."""
    ax, ay = p[17][0] - p[5][0], p[17][1] - p[5][1]
    n2 = ax * ax + ay * ay or 1.0
    return ((p[4][0] - p[5][0]) * ax + (p[4][1] - p[5][1]) * ay) / n2


def classer_posture(p, visage):
    """Posture de la main sur UNE image. p = 21 points (x, y) en pixels ; visage = None ou
    {"bouche": (x, y), "yeux_y": y, "largeur": l}. Retourne (posture ou None, mesures)."""
    paume = _dist(p[0], p[9]) or 1.0
    tendus = doigts_tendus(p)
    n = sum(tendus)
    pouce = position_pouce(p)
    mesures = {"doigts": n, "pouce": round(pouce, 2)}
    pouce_sorti = pouce < POUCE_SORTI
    pouce_replie = pouce > POUCE_REPLIE

    if n == 0:
        if pouce_sorti and p[4][1] < p[5][1] - POUCE_HAUT * paume:
            return "pouce", mesures
        if not pouce_sorti:
            # Étape 2 du signal d'aide : tout poing dont le pouce ne sort pas sur le côté.
            # Le pouce caché sous les doigts est mal placé par MediaPipe : on n'exige plus
            # qu'il soit « bien replié » (il ne compte que juste après l'étape 1).
            return "poing_pouce_dedans", mesures
        return None, mesures
    if n >= 3 and pouce > POUCE_PAUME:
        # Étape 1 : paume ouverte, pouce replié (3 doigts tendus suffisent : avec le pouce
        # replié, l'auriculaire ou l'annulaire est parfois vu plié)
        return "paume_pouce_replie", mesures
    if tendus == [True, False, False, False]:
        distance = visage and visage.get("distance_index", _dist(p[8], visage["bouche"]))
        if visage and distance < DISTANCE_BOUCHE * visage["largeur"]:
            return "chut", mesures
        return "un_doigt", mesures
    if tendus == [True, True, False, False]:
        return "deux_doigts", mesures
    if n == 4 and pouce_sorti:
        haut = visage["yeux_y"] if visage else HAUT_SANS_VISAGE * HAUTEUR
        if p[0][1] < haut:
            return "main_levee", mesures
        return "main_ouverte", mesures
    return None, mesures


# ---------- Stabilisation : une posture doit être TENUE pour devenir un geste ----------
class Stabilisateur:
    def __init__(self):
        self.candidat = None          # posture actuelle
        self.debut = 0.0              # depuis quand
        self.derniere_vue = 0.0
        self.deja_emis = False        # la posture actuelle a déjà donné un geste
        self.fin_pause = 0.0
        self.etape1 = 0.0             # dernière fois que la paume (pouce replié) a été tenue

    def image(self, posture, t):
        """Ajoute la posture d'une image. Retourne le nom du geste reconnu, ou None."""
        if posture is None and t - self.derniere_vue < TOLERANCE_PERTE:
            posture = self.candidat                       # main perdue un instant : on garde
        elif posture is not None:
            self.derniere_vue = t
        if posture != self.candidat:
            self.candidat, self.debut, self.deja_emis = posture, t, False
        tenu = t - self.debut
        if posture is None or self.deja_emis or t < self.fin_pause:
            return None
        if posture == "paume_pouce_replie" and tenu >= ETAPE_SIGNAL:
            self.etape1 = t
            return None
        if posture == "poing_pouce_dedans":
            if tenu >= ETAPE_SIGNAL and self.etape1 and t - self.etape1 <= DELAI_SIGNAL:
                self.etape1 = 0.0
                return self._emettre("signal_aide", t)
            return None
        if posture in DUREES and tenu >= DUREES[posture]:
            return self._emettre(posture, t)
        return None

    def _emettre(self, geste, t):
        self.deja_emis = True
        self.fin_pause = t + PAUSE_APRES_GESTE
        return geste


# ---------- Détecteur complet (caméra -> MediaPipe -> geste) ----------
class DetecteurGestes:
    """quand_geste(nom) est appelée à chaque geste reconnu (depuis le fil de la caméra)."""

    def __init__(self, quand_geste, afficher=AFFICHAGE):
        self.quand_geste = quand_geste
        # Pas d'écran (Pi lancé par SSH) : pas de fenêtre
        self.afficher = afficher and (os.name == "nt" or bool(os.environ.get("DISPLAY")))
        self.disponible = False
        self.arret = False
        self.dernier_geste = "Aucun"
        self.stabilisateur = Stabilisateur()
        try:
            import cv2
            import mediapipe as mp
            from quickhands import HandDetector
            self.cv2 = cv2
            # Bibliothèque du cours : une seule main (celle du résident)
            self.detecteur = HandDetector(maxHands=1, detectionCon=0.6, minTrackCon=0.5)
            self.visages = mp.solutions.face_detection.FaceDetection(model_selection=0,
                                                                    min_detection_confidence=0.5)
            self.camera = Camera()
        except Exception as erreur:
            print("Gestes : camera ou MediaPipe indisponible (" + str(erreur) + ")")
            return
        self.disponible = True
        print("Gestes : prets (" + self.camera.nom + ", images analysees sur place seulement)")

    def demarrer(self):
        if self.disponible:
            threading.Thread(target=self.boucle, daemon=True).start()

    def _visage(self, rgb, l, h):
        r = self.visages.process(rgb)
        if not r.detections:
            return None
        d = r.detections[0].location_data
        k = d.relative_keypoints              # 0, 1 = yeux ; 3 = centre de la bouche
        return {"bouche": (k[3].x * l, k[3].y * h),
                "yeux_y": (k[0].y + k[1].y) / 2 * h,
                "largeur": d.relative_bounding_box.width * l}

    def analyser(self, image):
        """Une image BGR -> (image, posture, mesures, main myHand ou None)."""
        # Pas d'effet miroir (pas de cv2.flip) : MediaPipe suppose une image en miroir et
        # flipType=True de quickhands corrige déjà son étiquette pour une image NON inversée.
        # Avec cv2.flip EN PLUS, Left/Right était inversé deux fois (donc faux), et le test
        # du pouce de fingersUp aussi. Les gestes, eux, ne dépendent pas de la main.
        h, l = image.shape[:2]
        if self.afficher:
            allHands, image = self.detecteur.findHands(image, draw=True, flipType=True)
        else:
            allHands = self.detecteur.findHands(image, draw=False, flipType=True)
        if not allHands:
            return image, None, {}, None
        myHand = allHands[0]
        p = [(x, y) for id, x, y in myHand["lmList"]]      # lmList : [id, x, y]
        nbLeves = self.detecteur.fingersUp(myHand)          # nombre (liste dans detecteur.fingers)
        tendus = doigts_tendus(p)
        # Le visage ne sert qu'à « chut » (index seul) et « main levée » (main ouverte) :
        # on ne le cherche que dans ces cas, pour garder des images par seconde sur le Pi.
        visage = None
        if tendus == [True, False, False, False] or all(tendus):
            rgb = self.cv2.cvtColor(image, self.cv2.COLOR_BGR2RGB)
            visage = self._visage(rgb, l, h)
        if visage and tendus == [True, False, False, False]:
            # Distance bout de l'index (repère 8) -> bouche, avec la bibliothèque du cours
            if self.afficher:
                distance, info, image = self.detecteur.findDistance(p[8], visage["bouche"], image)
            else:
                distance, info = self.detecteur.findDistance(p[8], visage["bouche"])
            visage["distance_index"] = distance
        posture, mesures = classer_posture(p, visage)
        mesures["fingersUp"] = nbLeves
        return image, posture, mesures, myHand

    def boucle(self):
        cv2 = self.cv2
        images, debut_ips, ips = 0, time.time(), 0.0
        while not self.arret:
            image = self.camera.lire()
            if image is None:
                time.sleep(0.1)
                continue
            image, posture, mesures, myHand = self.analyser(image)
            geste = self.stabilisateur.image(posture, time.time())
            if geste:
                self.dernier_geste = NOMS[geste]
                print("Geste reconnu :", NOMS[geste])
                try:
                    self.quand_geste(geste)
                except Exception as erreur:
                    print("Gestes : erreur dans l'action du geste :", erreur)
            images += 1
            if time.time() - debut_ips >= 2:
                ips, images, debut_ips = images / (time.time() - debut_ips), 0, time.time()
            if self.afficher:
                if myHand is not None:
                    self.detecteur.infoOnHand(image, myHand, [str(posture)])
                cv2.putText(image, "Posture : " + str(posture), (10, 25),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.putText(image, "Dernier geste : " + self.dernier_geste, (10, 55),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(image, str(mesures) + "  " + str(round(ips, 1)) + " img/s",
                            (10, HAUTEUR - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                cv2.imshow("FallGuard - gestes (q = fermer)", image)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    self.afficher = False
                    cv2.destroyAllWindows()
        self.camera.fermer()


if __name__ == "__main__":
    # Essai seul : affiche les gestes reconnus, aucune commande envoyée
    detecteur = DetecteurGestes(lambda nom: None)
    if detecteur.disponible:
        try:
            detecteur.boucle()
        except KeyboardInterrupt:
            pass
