import cv2
from matplotlib.transforms import Bbox
import mediapipe as mp
import math

class HandDetector:
    """
    Finds Hands using the mediapipe library. Exports the landmarks
    in pixel format. Adds extra functionalities like finding how
    many fingers are up or the distance between two fingers. Also
    provides bounding box info of the hand found.
    """

    def __init__(self, mode=False, maxHands=2, detectionCon=0.5, minTrackCon=0.5):
        """
        :param mode: In static mode, detection is done on each image: slower
        :param maxHands: Maximum number of hands to detect
        :param detectionCon: Minimum Detection Confidence Threshold
        :param minTrackCon: Minimum Tracking Confidence Threshold
        """
        self.mode = mode
        self.maxHands = maxHands
        self.detectionCon = detectionCon
        self.minTrackCon = minTrackCon

        self.mpHands = mp.solutions.hands
        self.hands = self.mpHands.Hands(static_image_mode=self.mode, max_num_hands=self.maxHands,
                                        min_detection_confidence=self.detectionCon,
                                        min_tracking_confidence=self.minTrackCon)
        self.mpDraw = mp.solutions.drawing_utils
        self.tipIds = [4, 8, 12, 16, 20]
        self.fingers = []
        self.lmList = []

    def findHands(self, img, draw=True, flipType=True):
        """
        Finds hands in a BGR image.
        :param img: Image to find the hands in.
        :param draw: Flag to draw the output on the image.
        :return: Image with or without drawings
        """
        mp_draw=mp.solutions.drawing_utils
        mp_hand=mp.solutions.hands
        mp_styles = mp.solutions.drawing_styles

        imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self.results = self.hands.process(imgRGB)
        allHands = []
        h, w, c = img.shape
        if self.results.multi_hand_landmarks:
            for handType, handLms in zip(self.results.multi_handedness, self.results.multi_hand_landmarks):
                myHand = {}
                ## lmList
                lmList = []
                mylmList = []
                xList = []
                yList = []
                for id, lm in enumerate(handLms.landmark):
                    px, py, pz = int(lm.x * w), int(lm.y * h), int(lm.z * w)
                    mylmList.append([px, py, pz])
                    xList.append(px)
                    yList.append(py)
                    h,w,c=img.shape
                    cx,cy= int(lm.x*w), int(lm.y*h)
                    lmList.append([id,cx,cy])
                
                ##TODO à compléter 1:  utiliser mp_draw.draw_landmarks pour dessiner les points sur la main.
                mp_draw.draw_landmarks(img, handLms, mp_hand.HAND_CONNECTIONS)
                ## bbox
                xmin, xmax = min(xList), max(xList)
                ymin, ymax = min(yList), max(yList)
                boxW, boxH = xmax - xmin, ymax - ymin
                bbox = xmin, ymin, boxW, boxH
                cx, cy = bbox[0] + (bbox[2] // 2), \
                         bbox[1] + (bbox[3] // 2)

                myHand["lmList"] = lmList
                myHand["mylmList"] = mylmList
                myHand["bbox"] = bbox
                myHand["center"] = (cx, cy)

                if flipType:
                    if handType.classification[0].label == "Right":
                        myHand["type"] = "Left"
                    else:
                        myHand["type"] = "Right"
                else:
                    myHand["type"] = handType.classification[0].label
                allHands.append(myHand)

                ## draw
                if draw:
                    self.mpDraw.draw_landmarks(img, handLms,
                                               self.mpHands.HAND_CONNECTIONS)
                    cv2.rectangle(img, (bbox[0] - 20, bbox[1] - 20),
                                  (bbox[0] + bbox[2] + 20, bbox[1] + bbox[3] + 20),
                                  (255, 0, 255), 2)
                    cv2.putText(img, myHand["type"], (bbox[0] - 30, bbox[1] - 30), cv2.FONT_HERSHEY_PLAIN,
                                2, (255, 0, 255), 2)
        if draw:
            return allHands, img
        else:
            return allHands

    #TODO à compléter 2
    def fingersUp(self, myHand):
        """
        Finds how many fingers are open and returns in a list.
        Considers left and right hands separately
        :return: List of which fingers are up
        """
        self.lmList = myHand["lmList"]   # éléments : [id, x, y]
        finUp = []

        # Pouce : on compare x (indice 1), sens inversé selon la main
        if myHand["type"] == "Right":
            finUp.append(1 if self.lmList[self.tipIds[0]][1] > self.lmList[self.tipIds[0] - 1][1] else 0)
        else:
            finUp.append(1 if self.lmList[self.tipIds[0]][1] < self.lmList[self.tipIds[0] - 1][1] else 0)

        # 4 autres doigts : on compare y (indice 2), bout plus haut = y plus petit
        for i in range(1, 5):
            finUp.append(1 if self.lmList[self.tipIds[i]][2] < self.lmList[self.tipIds[i] - 2][2] else 0)

        self.fingers = finUp             # liste [pouce, index, majeur, annulaire, auriculaire]
        return finUp.count(1)
            
            
    #TODO à compléter 3 et 4
    def infoOnHand(self,
               img,
               hand,
               textToShow: list=None):
        """
        Affiche un cadre d'informations au-dessus de la main : le type de main ("Left" / "Right")
        puis chaque ligne de textToShow.
        :param img: Image où dessiner
        :param hand: Dictionnaire myHand renvoyé par findHands
        :param textToShow: Lignes de texte à afficher (optionnel)
        :return: Image avec le cadre
        """
        x, y, w, h = hand["bbox"]                  # (xmin, ymin, largeur, hauteur)
        if hand["type"] == 'Right':
            couleur = (255, 0, 255)
        else:
            couleur = (255, 128, 0)
        lignes = [hand["type"]] + (textToShow or [])
        hauteurCadre = 25 * len(lignes) + 10
        # Cadre plein juste au-dessus du rectangle de findHands (marge de 20 px)
        cv2.rectangle(img, (x - 20, y - 20 - hauteurCadre), (x + w + 20, y - 20),
                      couleur, cv2.FILLED)
        for i, texte in enumerate(lignes):
            cv2.putText(img, str(texte), (x - 15, y - 20 - hauteurCadre + 25 * (i + 1)),
                        cv2.FONT_HERSHEY_PLAIN, 1.5, (255, 255, 255), 2)
        return img

    #TODO à compléter 5.1 et 5.2
    def findDistance(self, p1, p2, img=None):
        """
        Distance en pixels entre deux points (x, y).
        Avec lmList, passer seulement x et y : lmList[8][1:] (l'indice 0 est l'id).
        :param p1: Point 1 (x, y)
        :param p2: Point 2 (x, y)
        :param img: Image où dessiner le segment (optionnel)
        :return: distance, info (x1, y1, x2, y2, cx, cy) et l'image si img est donnée
        """
        x1, y1 = int(p1[0]), int(p1[1])
        x2, y2 = int(p2[0]), int(p2[1])
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        length = math.hypot(x2 - x1, y2 - y1)
        info = (x1, y1, x2, y2, cx, cy)
        if img is not None:
            cv2.circle(img, (x1, y1), 10, (255, 0, 255), cv2.FILLED)
            cv2.circle(img, (x2, y2), 10, (255, 0, 255), cv2.FILLED)
            cv2.line(img, (x1, y1), (x2, y2), (255, 0, 255), 3)
            cv2.circle(img, (cx, cy), 10, (255, 0, 255), cv2.FILLED)
            return length, info, img
        return length, info
