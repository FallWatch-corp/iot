# info.md — changements faits sur le Raspberry Pi (24 nov. 2026)

Pour Claude Code : applique ou vérifie ces changements dans le projet `~/iot`.
Aucun secret ici (`config.ini`, `auth_token`, `obj_id`, mots de passe Wi-Fi : ne jamais les copier, ni dans le dépôt, ni dans un message).

Légende : [FAIT ET VU] = affiché dans la console de l'utilisateur · [SUGGÉRÉ] = proposé, pas encore confirmé · [INCONNU] = je ne sais pas.

## 1. Matériel et système

- [FAIT ET VU] Raspberry Pi 4 Model B Rev 1.5, système 64 bits (aarch64), Python système 3.13.
- [FAIT ET VU] Caméra : module Raspberry Pi à nappe, capteur `ov5647` (libcamera 0.7.2). Détectée par `rpicam-hello --list-cameras` après vérification du branchement.
- [FAIT ET VU] Carte ESP32 reconnue en USB (CP210x), port série `/dev/ttyUSB0`.
- [FAIT ET VU] `iteration3.py` se lance : connexion ALIVEcode (objet `watch`), port série ouvert, bracelet connecté, seuil de chute 2,5 g.

## 2. Environnement Python à utiliser

- [FAIT ET VU] Le venv de travail est **`~/iot/venv3.11`** (Python 3.11, créé avec `uv`). Toujours l'activer : `source ~/iot/venv3.11/bin/activate`.
- [FAIT ET VU] Pourquoi : le paquet `mediapipe` 1.x (Python 3.13) plante avec « Illegal instruction » (compilé avec les instructions AES, absentes de ce processeur). `mediapipe-rpi4` n'a pas de roue utilisable (3.8, 3.9, 3.10 testés). Les anciennes versions `mediapipe` 0.10.x ont des roues ARM64 (0.10.9, 0.10.14 et 0.10.18 se sont installées ; 0.10.20 et 0.10.21 non).
- [INCONNU] Quelle version 0.10.x est installée en dernier dans `venv3.11` (installées à la suite : 0.10.14, 0.10.18, 0.10.9). Vérifier : `python -c "import mediapipe as mp; print(mp.__version__)"`.
- [FAIT ET VU] Dans `venv3.11`, MediaPipe se charge sans erreur (« Created TensorFlow Lite XNNPACK delegate for CPU »). `mp.solutions` existe (le code utilise `mp.solutions.face_detection`).
- [SUGGÉRÉ] Garder `numpy<2` dans ce venv (ancienne version de MediaPipe). Si `import cv2` se plaint de NumPy 2, faire `uv pip install "numpy<2"`.
- Installer avec `uv pip install ...` (les venv créés par `uv` n'ont pas de `pip`, et `pip` appelle sinon le pip du système, bloqué par PEP 668).
- [SUGGÉRÉ] Les autres venv (`venv310`, `venv39`, `venv3.12`, `venv3.8`, `venv3.7`) ne servent plus ; `venv310` contient un `mediapipe-rpi4` vide et NumPy 2.2.6. Peuvent être supprimés (jamais `venv3.11` ni l'ancien `venv`).

## 3. Configuration ALIVEcode

- [FAIT ET VU] `config.ini` se trouvait dans `~/iot/watch/`. Il a été copié dans `~/iot/config.ini` pour lancer `iteration3.py` depuis `~/iot` (`aliot-py` le cherche dans le dossier courant).
- [SUGGÉRÉ] Vérifier que `config.ini` est dans `.gitignore` avant tout `git push`.
- Lancer depuis le dossier qui contient `config.ini` : `cd ~/iot && python iteration3.py`. `aliot run watch/watch` échoue (cherche `../config.ini`).

## 4. Caméra : nouveau fichier `camera_rpicam.py` (dans `~/iot`)

- [FAIT ET VU] `picamera2` n'est installé que pour le Python 3.13 du système, donc invisible dans `venv3.11`. Test réussi : photo 640×480 enregistrée (`True (480, 640, 3)`).
- Solution : `camera_rpicam.py` définit `CameraRpicam(largeur, hauteur, fps)` qui lance `rpicam-vid -t 0 -n --codec mjpeg ... -o -` en sous-processus et décode les images JPEG avec OpenCV. API : `read()` → `(ok, image BGR)`, `release()`.
- [INCONNU] Latence réelle et images par seconde sur le Pi (non mesurées). Le tampon peut prendre du retard si l'analyse est plus lente que la caméra.

## 5. Changements dans `gestes.py`

1. [FAIT ET VU] Classe `Camera` remplacée (sauvegarde : `gestes.py.bak`). Ordre d'essai : `picamera2` → `CameraRpicam` (rpicam-vid) → webcam USB (`INDEX_WEBCAM`). Mêmes méthodes `lire()` / `fermer()` et même attribut `.nom` (« module camera du Pi (rpicam-vid) » pour le deuxième cas). Le reste du fichier n'a pas été modifié. Résultat : la caméra s'affiche.
2. [SUGGÉRÉ, pas encore confirmé] Les types de main (gauche/droite) étaient inversés. Cause probable : l'image est inversée par `cv2.flip(image, 1)` **et** `findHands(..., flipType=True)` inverse le type une deuxième fois. Essai proposé : remplacer `flipType=True` par `flipType=False` aux deux appels de `findHands` dans `analyser()` (sauvegarde : `gestes.py.bak2`). [INCONNU] si ça corrige : le code de `quickhands` (bibliothèque du cours) n'a pas été lu, et d'autres parties de `gestes.py` peuvent compenser (chercher `"type"`, `Left`, `Right`, `gauche`, `droite`).

## 6. À FAIRE (pour Claude Code)

- Confirmer que `flipType=False` corrige gauche/droite ; sinon chercher où le type est utilisé et corriger à cet endroit (une seule inversion au total).
- Mesurer les images par seconde de `gestes.py` avec `CameraRpicam`.
- Vérifier la détection des gestes de bout en bout et leur envoi vers ALIVEcode (l'itération 3 est due le 24 nov. 2026 à 23 h 59).
- Garder la liste des dépendances à jour (par exemple `requirements.txt` avec : `numpy<2`, `mediapipe==<version>`, `opencv-python`, `pyserial`, `aliot-py`). [INCONNU] la version exacte de `mediapipe` à fixer.
- Ne pas ajouter `sudo pip` : toujours `uv pip` dans `venv3.11`.
