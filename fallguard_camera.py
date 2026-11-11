# FallGuard : vérification d'une chute par la caméra du Raspberry Pi (picamera2 + MediaPipe Pose)
#
# Principe :
#   - La caméra tourne en basse résolution et garde les dernières secondes d'images EN MEMOIRE
#     SEULEMENT (rien n'est écrit sur le disque tant qu'aucune alerte n'est déclenchée).
#   - Quand le bracelet déclenche une alerte, verifier() analyse les images autour de l'alerte :
#     l'angle du torse (épaules -> hanches) dit si la personne est couchée ou debout.
#   - La caméra ne CANCELLE JAMAIS une alerte : elle ne fait qu'ajouter une information
#     (chute confirmée / personne debout / personne non vue / caméra indisponible).
#
# Installation sur le Pi (64 bits recommandé) - NON TESTE, a verifier sur ton Pi :
#   sudo apt install python3-picamera2
#   pip install mediapipe --break-system-packages
# Si picamera2 ou mediapipe manquent, disponible vaut False et le pont utilise l'ancienne photo.
#
# Verdicts retournés : "confirmee", "faux_positif_probable", "personne_non_vue",
#                      "incertain", "non_verifiee"

import math
import threading
import time
from collections import deque
from time import strftime

ANGLE_COUCHE = 60        # degrés : torse plus incliné que cela par rapport à la verticale = couché
ANGLE_DEBOUT = 40        # degrés : torse moins incliné que cela = debout
PART_MAJORITE = 0.6      # part des images qui doivent être d'accord
MIN_IMAGES_VALIDES = 2   # sous ce nombre, on ne peut pas conclure


class Verificateur:
    def __init__(self, largeur=640, hauteur=480, images_par_seconde=2, secondes_memoire=8):
        self.disponible = False
        self.images_par_seconde = images_par_seconde
        self.frames = deque(maxlen=images_par_seconde * secondes_memoire)  # (instant, image)
        self.verrou = threading.Lock()
        self.arret = False
        try:
            from picamera2 import Picamera2
            import mediapipe as mp
            import cv2
        except Exception as erreur:
            print("Camera: picamera2/mediapipe indisponibles (" + str(erreur) + ")")
            return
        try:
            self.cv2 = cv2
            # model_complexity=0 : modèle léger (plus adapté au Pi 4)
            self.pose = mp.solutions.pose.Pose(static_image_mode=True, model_complexity=0,
                                               min_detection_confidence=0.5)
            self.camera = Picamera2()
            # Le format "RGB888" de picamera2 donne des pixels dans l'ordre B, G, R
            # (donc directement utilisables par OpenCV ; on inverse pour MediaPipe).
            configuration = self.camera.create_video_configuration(
                main={"size": (largeur, hauteur), "format": "RGB888"})
            self.camera.configure(configuration)
            self.camera.start()
        except Exception as erreur:
            print("Camera: initialisation impossible (" + str(erreur) + ")")
            return
        self.disponible = True
        threading.Thread(target=self._capturer, daemon=True).start()
        print("Camera: prete (images gardees en memoire seulement)")

    def _capturer(self):
        pause = 1.0 / self.images_par_seconde
        while not self.arret:
            try:
                image = self.camera.capture_array("main")
                with self.verrou:
                    self.frames.append((time.time(), image))
            except Exception as erreur:
                print("Camera: capture impossible :", erreur)
                time.sleep(1)
            time.sleep(pause)

    def _angle_torse(self, image_bgr):
        """Angle du torse par rapport à la verticale (0 = debout, 90 = couché). None si personne."""
        resultat = self.pose.process(image_bgr[:, :, ::-1])      # BGR -> RGB
        if not resultat.pose_landmarks:
            return None
        points = resultat.pose_landmarks.landmark
        epaules = (points[11], points[12])
        hanches = (points[23], points[24])
        if min(p.visibility for p in epaules + hanches) < 0.4:
            return None
        hauteur, largeur = image_bgr.shape[:2]
        ex = (epaules[0].x + epaules[1].x) / 2 * largeur
        ey = (epaules[0].y + epaules[1].y) / 2 * hauteur
        hx = (hanches[0].x + hanches[1].x) / 2 * largeur
        hy = (hanches[0].y + hanches[1].y) / 2 * hauteur
        return math.degrees(math.atan2(abs(ex - hx), abs(ey - hy)))

    def verifier(self, secondes_avant=2, secondes_apres=4):
        """Attend un peu, puis analyse les images autour de l'alerte.
        Retourne un dict : verdict, angles, photo (nom du fichier ou None)."""
        if not self.disponible:
            return {"verdict": "non_verifiee", "angles": [], "photo": None}
        debut = time.time()
        time.sleep(secondes_apres)
        with self.verrou:
            images = [(t, f) for (t, f) in self.frames if t >= debut - secondes_avant]
        if not images:
            return {"verdict": "non_verifiee", "angles": [], "photo": None}

        angles = []
        for (_, image) in images:
            angle = self._angle_torse(image)
            if angle is not None:
                angles.append(round(angle))

        photo = "chute_" + strftime("%Y%m%d_%H%M%S") + ".jpg"
        try:
            self.cv2.imwrite(photo, images[-1][1])
        except Exception as erreur:
            print("Camera: photo impossible :", erreur)
            photo = None

        if len(angles) < MIN_IMAGES_VALIDES:
            verdict = "personne_non_vue"
        else:
            couches = sum(1 for a in angles if a > ANGLE_COUCHE)
            debout = sum(1 for a in angles if a < ANGLE_DEBOUT)
            if couches >= PART_MAJORITE * len(angles):
                verdict = "confirmee"
            elif debout >= PART_MAJORITE * len(angles):
                verdict = "faux_positif_probable"
            else:
                verdict = "incertain"
        print("Camera: angles du torse =", angles, "->", verdict)
        return {"verdict": verdict, "angles": angles, "photo": photo}

    def fermer(self):
        self.arret = True
        if self.disponible:
            try:
                self.camera.stop()
            except Exception:
                pass
