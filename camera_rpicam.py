# camera_rpicam.py : lit la caméra du Pi via rpicam-vid (sans picamera2)
import subprocess
import cv2
import numpy as np


class CameraRpicam:
    def __init__(self, largeur=640, hauteur=480, fps=15):
        self.proc = subprocess.Popen(
            ["rpicam-vid", "-t", "0", "-n", "--codec", "mjpeg",
             "--width", str(largeur), "--height", str(hauteur),
             "--framerate", str(fps), "-o", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        self.tampon = b""

    def read(self):
        """Comme cv2.VideoCapture.read() : retourne (ok, image BGR)."""
        while True:
            debut = self.tampon.find(b"\xff\xd8")
            fin = self.tampon.find(b"\xff\xd9", debut + 2) if debut != -1 else -1
            if debut != -1 and fin != -1:
                jpg = self.tampon[debut:fin + 2]
                self.tampon = self.tampon[fin + 2:]
                image = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
                return image is not None, image
            morceau = self.proc.stdout.read(4096)
            if not morceau:
                return False, None
            self.tampon += morceau

    def release(self):
        self.proc.terminate()
