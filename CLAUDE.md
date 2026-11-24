# FallGuard (cours 420-5D7 Internet des objets, équipe de 4)

Bracelet de détection de chute pour résidences de personnes âgées. Réponds en français, de façon concise.
Ne confonds pas ce qui est DÉCIDÉ et ce qui a été seulement SUGGÉRÉ. Si une information manque, écris
« INCONNU » et pose la question. Dernière mise à jour : 11 nov. 2026.

## DÉCIDÉ (dit par l'utilisateur)
- 17 nov. : PAS de condition d'immobilité après une chute (« plus physique ») : chute = impact + (chute libre avant
  OU orientation changée ≥ 40°), puis préalerte de 15 s annulable (gardée). Essai « alerte immédiate sur choc ou
  chute libre seule, sans préalerte » fait puis RETIRÉ à la demande de l'utilisateur (17 nov.).
- Carte du bracelet : ESP32 DevKit pour le prototype de l'itération ; version PCB avec XIAO ESP32C3 (GPS retiré pour l'instant).
- Capteurs : MPU6050 (0x68), MAX30102 (0x57, BPM), OLED SSD1306 (0x3C), buzzer, un bouton latéral. Pas de LED.
- OLED : date + heure + BPM par défaut ; l'écran ne change qu'en cas de chute.
- Localisation par pièce : Wi-Fi RSSI (pas encodée dans le code pour l'instant).
- Itération 2 : l'utilisateur fait l'interface ALIVEcode ; les statistiques et les données froides viennent plus tard.
- Itération 3 : on utilise le Raspberry Pi (avec sa caméra) pour les gestes. Le programme tourne SUR LE PI (dit le 22 nov.).
- 22 nov. : gestes retenus = (1) « Signal for Help » (paume, pouce replié, puis doigts refermés) -> SOS ;
  (2) réponse « Ça va ? » pendant la préalerte (1 doigt = ça va / annule, 2 doigts = aide tout de suite) ;
  (3) geste validé seulement si le MPU6050 du bracelet a bougé en même temps (fusion caméra + bracelet) ;
  (4) « chut » (index sur la bouche) = buzzer coupé 5 min ; (5) main levée = appel non urgent.
  24 nov. (demandé par l'utilisateur) : « chut » ne coupe plus le buzzer, il met l'interrupteur détection
  sur OFF ; un autre geste le remet ON (choisi par Claude : pouce levé, au repos seulement).
  La date de remise (17 nov.) est passée ; nouvelle date / pénalité : INCONNU.
- Le bracelet n'a pas de caméra ; la caméra est celle du Pi.
- Les PCB (version XIAO) sont reçus (7 nov.) : l'utilisateur est satisfait du résultat, surtout de la taille.
- Trop tard pour ajouter un capteur de température sur le PCB (dit par l'utilisateur).
- Capteur « pour s'adapter au poignet » = capteur de pression à film mince MECCANIXITY FSR-400B, lot de 2 (commandé sur Amazon,
  livré le 26 sept.). Fiche vue sur Amazon : plage 20 g à 2 kg, longueur 21 mm, zone sensible d'environ 7,5 mm.
- Commande Amazon livrée le 26 sept. : 2 ESP32 DevKit (ELEGOO), 2 GY-NEO6MV2 (GPS), capteur de pression MECCANIXITY,
  5 modules de charge TP4056 (+ d'autres articles non vus).
- Un autre groupe a le même projet ; l'utilisateur n'a pas vu leur prototype (il croit qu'ils ont un capteur de
  température et une caméra sur le bracelet : non vérifié).

## ÉTAT DE LA REMISE ITÉRATION 2 (relu le 11 nov. 2026, 19 h, d'après le zip `iteration2.zip`)
- Dans le zip : `iteration2.py` (objet « watch », balises par pièce, stats par minute, historique, procédures par actions),
  `fallguard_xiao_serie_1/` (.ino + `secrets.h`), 3 captures, 1 vidéo d'écran (73 s), 2 vidéos MOV, 2 photos du montage.
- Vu sur les captures : projet ALIVEcode « FallWatch », 21 composants, objet IoT « myWatch-esp32 ». Le code dit que les SOS vont dans
  l'historique mais ne comptent pas dans `chutes_total` (règle écrite dans `iteration2.py`).
- À CORRIGER avant remise : (1) `fallguard_utils.py` absent du zip (version de l'équipe, avec `rappel_bracelet`, `simuler_chute`,
  lignes `W:`) ; (2) `secrets.h` contient un vrai mot de passe Wi-Fi : le retirer, mettre `secrets.h.exemple` ; (3) aucune capture
  des Procédures, des Déclencheurs ni du graphe de données froides ; dataset sans lignes.
- À SURVEILLER : en-tête du .ino périmé (parle du Pi, « rien testé ») ; `#define CARTE_XIAO_C3` actif alors que le montage photographié
  ressemble à un DevKit (INCONNU : carte réellement téléversée) ; `get_doc` échoue en silence (repli local) donc ajouter une ligne de
  journal qui prouve la lecture ; zip d'environ 100 Mo (limite INCONNU) ; `IMG_2252.MOV` flou.
- Date : remise le 10 nov. à 0 h 14, tardive jusqu'au 11 nov. à 0 h 14 : passée au moment de cette relecture. Pénalité INCONNUE.
- Le code n'a pas été exécuté par Claude (fichier manquant) ; vidéos vues seulement en images extraites.

## SUGGÉRÉ par Claude (pas encore décidé)
- Détection de chute en 3 phases (impact, attente 1 s, immobilité 3 s + chute libre ou changement d'orientation), préalerte de 15 s
  annulable par le bouton, SOS par appui long de 2 s. Valeurs de départ à ajuster par essais.
- Gestes pour l'itération 3 : pouce levé = arrêter/annuler l'alarme, main ouverte tenue 2 s = SOS, deux doigts = test de l'alarme.
  Le geste détecté s'affiche dans `/doc/geste` et dans le journal.
- Caméra du Pi fixe, face à la personne, à hauteur de poitrine/visage, à 50 cm–1 m, lumière devant, fond uni.
  Analyse sur place, aucune image enregistrée ni envoyée (vie privée, Loi 25).
- Pas de caméra sur le bracelet, pas de Pi par pièce.
- Capteur de pression : branchement sans changer le PCB, D2 (pastille U1.3, libre depuis le retrait de la LED, vraisemblablement
  GPIO4 = entrée analogique ; à vérifier) en pont diviseur 3V3 / capteur / point de lecture D2 / ~10 kΩ vers GND. Éviter D0
  (broche de démarrage). Seuils à régler par essais. Usages : `/doc/pression`, `/doc/porte`, alerte « bracelet lâche / non porté ».
  Montage à plat contre la peau, près de la fenêtre du MAX30102.
- Température sans changer le PCB : (1) capteur interne du MAX30102 ou du MPU6050 (température de la puce, pas du corps),
  (2) capteur I2C ajouté par fils (MAX30205 ou TMP117, disponibilité non vérifiée), (3) laisser pour plus tard. Rien choisi.
- Sangle : silicone 20 mm avec boucle (lavable) ou élastique à velcro (facile pour mains raides) ; boîtier imprimé en 3D
  avec supports de barrettes à ressort 20 mm. Éviter cuir, maillons métalliques, petites goupilles. Fenêtre du MAX30102
  légèrement bombée, sans lumière parasite ; sangle ni trop lâche ni trop serrée.
- Procédures Aliot (≥ 2 exigées) : `alerte_chute` (courriel « FallGuard : chute détectée »), `couper_alarme` (envoi d'action
  `arreter_alarme` à l'objet `fallguard`), optionnelle `bracelet_hors_ligne` (courriel).
- Déclencheurs Aliot (≥ 2 exigés) : base de données `/doc/chute` = true → `alerte_chute` ; connexion de l'objet `fallguard`
  Déconnecté → `bracelet_hors_ligne` ; optionnel `/doc/porte` = false → courriel « bracelet non porté ». Comparateurs et
  type de la valeur (true ou "true") : INCONNU, à vérifier dans l'interface. Le courriel part vers l'adresse du compte.
- Données froides / graphe : dataset avec colonnes `bpm`, `accel`, `rssi` (+ `pression`, `temp` si ajoutés), graphes BPM et
  accélération dans le temps ; compteur `/doc/chutes_total` et `/doc/bpm_moyen` pour les statistiques.

## Itération 2 (énoncé lu sur alivecode.ca, remise mardi 10 nov. 2026 à 0 h 14)
- Fichier exigé : `iteration2.py`. Aussi : captures, vidéo, photos du montage, code Arduino, code Python.
- Grille : base JSON (20), insertion/mise à jour (10), get_doc/lecture (15), fonctionnalités clés (15 : 2 procédures,
  2 déclencheurs, données froides/graphe), interface (30, au moins 10 composants contrôlés par la base), remise (10).
- L'énoncé dit « au moins 4 composants », la grille dit « 10 ». Viser 10.

## Itération 3 (énoncé lu sur alivecode.ca, remise mardi 17 nov. 2026 à 23 h 59, 4 %)
- Contrôler au moins un composant avec des gestes de la main, MediaPipe + la librairie de détection de mains créée en classe.
- Chaîne attendue : le Raspberry Pi détecte le geste, puis envoie la commande à l'Arduino/ESP32 (série, MQTT ou HTTP).
  Afficher le geste détecté à l'écran ou sur le tableau de bord. Noter les limites (éclairage, distance, fausses détections).
- À remettre : vidéo, photos du montage, code Arduino/ESP32, code Python. Grille : gestes (20), contrôle (25), créativité (20),
  code (25), vidéo/photos (10).
- Itération 4 = une IA, itération 5 = présentation finale.

## Conventions du cours Aliot (Aliot-0 à Aliot-4)
- Carte en USB, Python lit le port série (équivalent de `serre_utils.py`), aliot-py envoie à ALIVEcode.
- Champs du document : `update_doc({"/doc/champ": valeur})` (le préfixe `/doc/` est obligatoire).
- Composant « Contrôlé » = lié à un champ du document. Journal (`Mylog`) et buzzer (`Mybuzzer`) = non contrôlés,
  alimentés par `update_component(id, valeur)`.
- Boutons / interrupteur / curseur : `on_action_recv(action_id=..., callback=...)`.
- `get_doc("/doc/champ")` lit un champ. `aliot init`, `aliot new <nom>`, `aliot run <nom>` ; config.ini
  (obj_id, auth_token, main) : ne jamais le mettre sur GitHub.

## Conventions de CODE à suivre (relevées le 11 nov. 2026 dans les exemples du cours : Arduino, pyserial, Aliot-3, Aliot-4)
Source : pages « Les microcontrôleurs avec Arduino », « Communication pyserial / Programmation de la serre », Aliot-3
(update_doc, update_component, envoi de données de la serre), Aliot-4 (Lab 2, « code complet »). Certains blocs de code de ces
pages étaient coupés dans ce que j'ai pu lire : je ne décris que ce que j'ai vu. Le fichier `serre_utils.py` complet : non lu.

### Python (aliot-py)
- En-tête : `# Documentation: https://alivecode.ca/docs/aliot`. Imports : `import time`, `import serre_utils` (module maison),
  puis `from aliot.aliot_obj import AliotObj`.
- Au départ : `time.sleep(5)` avec le commentaire « Attente pour bien établir la communication avec le capteur ».
- Un seul objet créé depuis config.ini : `rasp_serre = AliotObj("rasp-serre")` (le nom = section de config.ini ; variable en
  snake_case : `capteur_serre`, `rasp_serre`, `buzzer`). Commentaire au-dessus : « Création de l'objet à partir du fichier de configuration ».
- Accès au matériel dans un module séparé (`serre_utils.py` / `Greenhouse_utils.py`) : fonctions `get_...()` et `set_...()`
  (`get_temperature_and_humidity()`, `get_luminosity()`, `get_led_state()`, `set_led(value)`). Valeurs récentes gardées dans des
  variables globales initialisées à `None` (`luminosity = None`), état privé avec `_` (`_led_state`) ; les getters renvoient
  `None, None` si une valeur manque ou est `math.isnan`. Ouverture : `serial.Serial('COM24', 9600)` puis `time.sleep(2)` ;
  `threading` importé pour la lecture série.
- Boucle principale : fonction `start()` avec `while True:` / `try:` ... `time.sleep(1)` / `except KeyboardInterrupt: break` ;
  enregistrée par `objet.on_start(callback=start)` puis `objet.run()` à la dernière ligne (commentaire « connects your object
  to the sever »). Les exemples sans boucle appellent seulement `run()` après les `on_action_recv` / `listen_doc`.
- Écriture dans la base : `objet.update_doc({"/doc/temperature": temp, ...})`, clés TOUJOURS préfixées `/doc/`, valeurs avec leur
  vrai type (nombre = nombre, pas de chaîne ; booléens `True`/`False` ; `datetime` accepté ; clés imbriquées `/doc/a/b/c` permises).
- Composants non contrôlés : `objet.update_component("Mybuzzer", 450)` (id personnalisé, fréquence en Hz) ; journaux via les Logs.
- Actions de l'interface : `objet.on_action_recv(action_id="allumer", callback=allumer_led)` (arguments nommés) ; la fonction reçoit
  un paramètre (`data` ou `value`) ; une action d'interrupteur reçoit True/False. Exemple Lab 2 : `set_led_cb(value)` appelle
  `serre_utils.set_led(value)` puis `update_doc({"/doc/light": value})`.
- Écouteur du document : `objet.listen_doc(["/doc/humidity"], callback=humidite_change)` ; la fonction reçoit `fields` et lit
  `fields['/doc/humidity']`.
- Style : commentaires en français au-dessus des blocs (« # Obtenir les données du capteur », « # Affichage », « # Envoi des données
  au serveur ALIVEcode »), f-strings pour `print` (`print(f"Temp: {temp} | Humidity: {hum}")`), noms de fonctions courts
  (`allumer`, `eteindre_led`, `set_led_cb`, `buzz`, `humidite_change`), indentation 4 espaces (2 dans certains utils).
  Exécution : `aliot run <nom-objet>`, `main` dans config.ini ; venv : `python -m venv venv_projet`, `pip install pyserial`.

### Arduino (C++)
- Broches en `const int` en haut du fichier, noms simples en minuscules/camelCase : `const int buzzer = 2;`, `const int buttonPin = 12;`,
  `const int ledPin = 3;`, `const int photoresistorPin = A0;` ; `#define DHTPIN 7` / `#define DHTTYPE DHT11` pour une bibliothèque ;
  `#include <DHT.h>` en tête.
- Structure : `void setup() { Serial.begin(9600); pinMode(x, OUTPUT); ... }` puis `void loop() { ... }`.
- Bouton : `pinMode(buttonPin, INPUT)` avec résistance externe de 10 kohm ; détection de front avec `buttonState` (ancien) et
  `currentButtonState` (courant) : `if (currentButtonState == LOW && buttonState == HIGH)` ; état du buzzer dans `buzzerState`.
- Buzzer : `tone(buzzer, 1500)` / `noTone(buzzer)` ou `digitalWrite(buzzer, HIGH/LOW)` avec `delay()`.
- Série vers Python : valeurs séparées par `:` (`Serial.print(temperature); Serial.print(":"); Serial.print(humidity); ...`), 9600 bauds,
  lecture une fois par tour de `loop()` ; messages de débogage courts (`Serial.println("button pressed")`).
- Style : commentaires en anglais dans les exemples Arduino (« // Read temperature and humidity from DHT11 sensor »), indentation
  2 ou 4 espaces, nom de fichier du type `Laboratoirex.ino`.

### Écarts connus entre NOTRE code et ces conventions (à décider, rien n'est corrigé)
- Nous envoyons à 115200 bauds (le cours : 9600) ; la ligne `D:...` a 7 champs (le cours : valeurs séparées par `:`, même idée).
- Notre bouton utilise `INPUT_PULLUP` (le PCB n'a pas de résistance de 10 kohm ; le cours : `INPUT` + résistance externe).
- Nos noms de variables/commentaires Arduino sont en français ; le cours : commentaires en anglais côté Arduino.
- `iteration2.py` contient plus de logique que les exemples (traiter_mesures, journal) : à garder si le prof n'impose pas le style.
- Le prof impose-t-il ce style ? INCONNU.

## Aliot-5 : procédures et déclencheurs (lu sur alivecode.ca)
- Procédure = onglet « Procédures » ; sous-procédures : « Envoi d'actions » (id d'action IoT + JSON optionnel, l'objet doit
  avoir `on_action_recv` pour cet id) et « Envoi de courriels » (objet + corps, envoyé au courriel du créateur du projet).
- Déclencheur = onglet « Déclencheurs » : « Changement dans la base de données » (`champ comparateur valeur` → procédure) ou
  « Changement d'état de connexion d'un objet IoT » (objet + Connecté/Déconnecté → procédure).
- Propositions pour FallGuard : voir la section SUGGÉRÉ ci-dessus (rien n'est encore créé dans ALIVEcode).

- Données froides (lu) : « Créer un dataset » (nom + description, nouveau ou existant), « Modifier le dataset » (ajouter ses
  colonnes, puis le dataset se remplit quand on change les champs de la base chaude ; ou import JSON/CSV), « Ajouter un graphe »
  (depuis le dataset). Le détail des colonnes/graphes est dans des captures non lisibles en texte : INCONNU.

- Capteur de pression, code ajouté le 7 nov. (testé seulement avec faux aliot + simulation, jamais sur une vraie carte) :
  `.ino` lisent `pressionPin` (XIAO : GPIO4/D2 ; DevKit : GPIO34) et envoient `D:...:type:pression` (brut 0–4095) ;
  `fallguard_utils.py` lit le 7e champ (optionnel) et simule un cycle de 120 s (bon, lâche 85–100 s, retiré 100–110 s) ;
  `iteration2.py` écrit `/doc/pression` (%), `/doc/serrage` (bon/lache/trop serre/non porte/inconnu) et `/doc/porte`
  (pression ≥ SEUIL_PORTE si le capteur répond, sinon doigt du MAX30102). Seuils 5 / 15 / 80 % INVENTÉS, à calibrer.
- « Watch.py » demandé par l'utilisateur : aucun fichier de ce nom dans le dossier (INCONNU) ; la simulation a été
  ajoutée à `fallguard_utils.py` (SIMULATION = True) et à `iteration2.py`.

## Fichiers (dossier serie/)
- `iteration2.py` : programme principal. `fallguard_utils.py` : série (SIMULATION = True pour tester sans carte).
- `fallguard_esp32_serie.ino` / `fallguard_xiao_serie.ino` : protocole série `D:bpm:accel:rssi:etat:doigt:type`,
  événements `E:...`, commandes `a` arrêter, `t` test, `o` SOS, `e`/`x` détection, `s`+octet seuil.
- `fallguard_balise/` : balise de pièce (ESP32 DevKit ou XIAO C3, réseau `FG_<pièce>`, canal 1 ; puissance réglée
  après `softAP`, nouvel essai si échec). Le bracelet (`*_serie_1`) ne scanne que le canal 1 (400 ms, abandon après 5 s,
  doublon de nom = plus fort gardé). Modifié le 17 nov. : compilé pour les 2 cartes, PAS testé sur carte.
- 17 nov. : `/doc/porte` ne changeait jamais dans le document (2e `update_doc` de la même seconde perdu, comme
  `derniere_chute`). Corrigé : porte / chute / en_ligne partent dans le même `update_doc` que les mesures
  (`champs_changes`). Pas encore testé sur ALIVEcode.
- 17 nov. (demandé par l'utilisateur) : scan des balises toutes les 5 s (`SCANS_VIDES_MAX` = 6, environ 30 s) et scan
  immédiat au début d'une préalerte/alerte ; ligne `W:...;!` -> la pièce est fixée sans attendre le 2e scan.
  `lire()` renvoie `("W", balises, urgent)`. Compilé (2 cartes), pas testé sur carte.
- 17 nov. : la pièce ne changeait pas. Corrigé dans `traiter_balises` : force lissée par balise (LISSAGE 0,5), changement
  si une balise dépasse la pièce actuelle de 3 dB (ECART_CHANGEMENT), balise absente -5 dB/scan, oubliée après 6 scans
  -> « Inconnue ». `/doc/piece` et `/doc/balises` partent avec les mesures (`a_envoyer`). Testé hors ligne seulement.
- Hors dossier (ancien design, à ignorer pour les itérations 2 et 3) : relais Pi par HTTP (`fallguard_pi_pont.py`),
  simulateur, vérification de chute par la pose (`fallguard_camera.py`, ne répond pas à l'itération 3).

- 22 nov. (itération 3) : `gestes.py` (caméra picamera2 ou webcam, `quickhands.HandDetector` du cours +
  MediaPipe Face Detection pour « chut » / main levée, posture tenue 1-2 s, pause 3 s) ; `iteration3.py` = copie
  de `iteration2.py` + gestes (action selon l'état du bracelet, refus si gyroscope < 25 deg/s dans les 5 s, sauf
  gestes urgents ; champs `/doc/geste`, `/doc/geste_action`, `/doc/appel`, `/doc/silence`). `.ino` _serie_1 :
  commandes v/h/n/m, champ `rot` (7e de `D:`), écran « Ca va ? » (compilé pour les 2 cartes, pas téléversé). `quickhands.py` : TODO 3-5 complétés
  (`infoOnHand`, `findDistance(p1, p2)` sur des points (x, y)), `fingersUp` garde la liste dans `self.fingers`.
  Testé hors ligne seulement (faux aliot, mains synthétiques) ; MediaPipe/caméra/carte : PAS testés. Seuils inventés.
- Examen pratique : vendredi 27 nov. 2026 (Arduino, pyserial dans VS Code, aliot-py + tableau de bord comme
  l'itération 2). Sur machine ; TOUT le site alivecode.ca permis (doc aliot ET pages du cours) ; Arduino + n'importe lequel des capteurs vus en
  cours (un ou plusieurs). Liste exacte des capteurs vus en cours : INCONNU (vu dans les pages : DHT11,
  photorésistance, bouton, LED, buzzer).

- 24 nov. (info.md, fait sur le Pi) : venv `venv3.11` (uv, mediapipe 0.10.x, numpy<2), caméra ov5647 lue par
  `camera_rpicam.py` (rpicam-vid), bracelet sur `/dev/ttyUSB0`, `iteration3.py` se connecte. Gauche/droite inversé :
  corrigé en retirant `cv2.flip` de `analyser()` (flipType=True gardé) ; image affichée sans miroir. Pas encore testé sur le Pi.
- 22 nov. : PROBLÈME PCB (XIAO) non réglé : la LED rouge du MPU6050 s'allume sur tous les connecteurs, mais le
  MAX30102 et l'OLED ne marchent pas. Cause INCONNUE (pistes : ordre VCC/GND des connecteurs différent de celui des
  modules, module abîmé, soudure). Sketch de diagnostic : `test_i2c_xiao/`. Résultat du scan : INCONNU.

## À FAIRE
- Itération 2 : statistiques, données froides, 2 procédures, 2 déclencheurs, données de départ, structure JSON plus riche,
  compteurs pour atteindre 10 composants contrôlés ; captures, vidéo, photos.
- Itération 3 : module gestes (caméra du Pi + MediaPipe) branché sur `iteration2.py` (champ `/doc/geste`, appel de
  `arreter_alarme()`, `declencher_sos()`, `tester_alarme()` de `fallguard_utils.py`).

## INCONNU / non vérifié
- Le professeur exige-t-il une température ? Qu'attend-il par « statistiques » ?
- Brochage réel du PCB reçu vs `connexions_v5.md` et `fallguard_xiao_serie.ino` (sérigraphie non lisible sur les photos).
- Le capteur de pression n'est pas encore lu dans le `.ino` ni dans `iteration2.py` ; champ `pression` non ajouté au protocole.
- Où tourne `iteration2.py` : PC ou Pi ? Modèle de la caméra (module du Pi ou webcam USB) et longueur du câble ?
- Le prof accepte-t-il l'ordinateur à la place du Pi ? Un code ESP32 compte-t-il comme « code Arduino » ?
- La librairie de détection de mains créée en classe n'a pas été vue.
- Les .ino n'ont passé qu'une vérification de syntaxe ; `iteration2.py` a été essayé avec un faux aliot, jamais
  avec le vrai ALIVEcode ni une vraie carte. MediaPipe sur Pi 4 : non testé.
- Valeurs attendues par le feu de circulation (GREEN/YELLOW/RED supposé) et format des valeurs du curseur/interrupteur.
- Le code de départ du cours (`serre_utils.py`) n'a pas pu être lu en entier.
- Date de validation du projet par le prof, noms des 4 membres et répartition des tâches.
