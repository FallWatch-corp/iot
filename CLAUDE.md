# FallGuard (cours 420-5D7 Internet des objets, équipe de 4)

Bracelet de détection de chute pour résidences de personnes âgées. Réponds en français, de façon concise.
Ne confonds pas ce qui est DÉCIDÉ et ce qui a été seulement SUGGÉRÉ. Si une information manque, écris
« INCONNU » et pose la question. Dernière mise à jour : 11 nov. 2026.

## DÉCIDÉ (dit par l'utilisateur)
- Carte du bracelet : ESP32 DevKit pour le prototype de l'itération ; version PCB avec XIAO ESP32C3 (GPS retiré pour l'instant).
- Capteurs : MPU6050 (0x68), MAX30102 (0x57, BPM), OLED SSD1306 (0x3C), buzzer, un bouton latéral. Pas de LED.
- OLED : date + heure + BPM par défaut ; l'écran ne change qu'en cas de chute.
- Localisation par pièce : Wi-Fi RSSI avec des balises ESP32 (codée, voir Fichiers ; pas encore testée avec les balises).
- Itération 2 : l'utilisateur fait l'interface ALIVEcode ; les statistiques et les données froides viennent plus tard.
- Itération 3 : on utilise le Raspberry Pi (avec sa caméra) pour les gestes.
- Le bracelet n'a pas de caméra ; la caméra est celle du Pi.
- Les PCB (version XIAO) sont reçus (7 nov.) : l'utilisateur est satisfait du résultat, surtout de la taille.
- Trop tard pour ajouter un capteur de température sur le PCB (dit par l'utilisateur).
- Capteur « pour s'adapter au poignet » = capteur de pression à film mince MECCANIXITY FSR-400B, lot de 2 (commandé sur Amazon,
  livré le 26 sept.). Fiche vue sur Amazon : plage 20 g à 2 kg, longueur 21 mm, zone sensible d'environ 7,5 mm.
- Commande Amazon livrée le 26 sept. : 2 ESP32 DevKit (ELEGOO), 2 GY-NEO6MV2 (GPS), capteur de pression MECCANIXITY,
  5 modules de charge TP4056 (+ d'autres articles non vus).
- 10 nov. : l'itération 2 répond aux attentes. Capteur de pression REPORTÉ à l'itération 3 (après test du PCB et du
  boîtier). Le XIAO doit fonctionner comme l'ESP32 DevKit (même code, mêmes commandes).
- Procédure par envoi d'action retenue : `enregistrer_chute` seulement (déclencheur `/doc/chute` = true).
  `rappel_bracelet` est codé mais NON retenu. Les autres procédures créées dans ALIVEcode (courriels) : contenu INCONNU.
- 11 nov. : on garde le style actuel du code (115 200 bauds, INPUT_PULLUP, commentaires en français) malgré les écarts
  avec les exemples du cours.
- Un autre groupe a le même projet ; l'utilisateur n'a pas vu leur prototype (il croit qu'ils ont un capteur de
  température et une caméra sur le bracelet : non vérifié).

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
  `arreter_alarme` à l'objet `watch`), optionnelle `bracelet_hors_ligne` (courriel).
- Déclencheurs Aliot (≥ 2 exigés) : base de données `/doc/chute` = true → `alerte_chute` ; connexion de l'objet `watch`
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
- Créés dans ALIVEcode (vu sur les captures d'un coéquipier le 11 nov.) : 5 déclencheurs (objet déconnecté, porte == false,
  en_ligne == false, detection_active == false, chute == true -> Enrégistrer chute) et 5 procédures. « Alerte chute » n'est
  appelée par aucun déclencheur (à vérifier).

- Données froides (lu) : « Créer un dataset » (nom + description, nouveau ou existant), « Modifier le dataset » (ajouter ses
  colonnes, puis le dataset se remplit quand on change les champs de la base chaude ; ou import JSON/CSV), « Ajouter un graphe »
  (depuis le dataset). Sur la page Document temps réel, une liste « insérer les données dans le dataset » relie le document
  au dataset.
- Dataset « Fallguard_mesures » : colonnes Date (automatique = axe X), bpm_moyen, bpm_min, bpm_max, accel_max, chutes_total,
  pieces_stats ; se remplit depuis le 11 nov. vers 12 h. On ne choisit pas les axes : chaque colonne ajoutée au graphe = une
  courbe. PROBLÈMES OUVERTS : plusieurs lignes identiques par minute (une ligne par mise à jour du document ?) ; graphes
  « Chutes cumulées » et accel vides alors que les colonnes ont des valeurs (type de colonne ? INCONNU).

- Capteur de pression (REPORTÉ itération 3) : un code du 7 nov. est décrit dans d'anciennes notes (`pressionPin`, champ
  `pression`, `/doc/serrage`) mais il N'EST PAS dans les fichiers de ce dossier (vérifié le 10 nov.).

## Fichiers (racine du dépôt, vérifiés le 11 nov.)
- `config.ini` (venu d'ALIVEcode, le bon, ne pas modifier, ignoré par git) : section `[watch]`, `main = watch.py`.
  Dans ALIVEcode, l'objet s'affiche sous le nom « myWatch-esp32 » (même obj_id).
- `iteration2.py` : programme principal, `AliotObj("watch")`, même code pour ESP32 DevKit et XIAO.
  `watch/watch.py` = COPIE de `iteration2.py` (+ sys.path vers la racine), lancée par `aliot run watch` depuis la racine.
  Modifier `iteration2.py` puis recopier.
- `fallguard_utils.py` : série 115 200 bauds (SIMULATION = True pour tester sans carte, PORT = None = détection auto).
  Bracelet -> PC : `D:bpm:accel:rssi:etat:doigt:type` (1/s ; accel = PIC de la dernière seconde), `E:alerte:chute|sos`,
  `E:annule`, `E:acquitte`, `W:Chambre,-48;Salon,-71` (balises, toutes les 10 s). Lignes de débogage du bracelet
  (`Impact`, `Verification`, ...) affichées dans le terminal avec `[bracelet]` (MOTS_DEBOGAGE = () pour les masquer).
  PC -> bracelet : `a` arrêter, `t` test, `o` SOS, `c` chute simulée, `r` rappel, `e`/`x` détection, `s`+octet seuil
  (dixièmes de g).
- Croquis À JOUR : `fallguard_esp32_serie_1/` et `fallguard_xiao_serie_1/` (identiques sauf `#define CARTE_XIAO_C3` et
  `utiliserGPS`). Wi-Fi dans `secrets.h` de chaque dossier (ignoré par git ; modèle `secrets.h.exemple`).
  `fallguard_esp32_serie/` et `fallguard_xiao_serie.ino` = ANCIENNES versions. Aucun croquis ne commande de LED.
- `fallguard_balise/` : balise de pièce (ESP32 DevKit, réseau `FG_<pièce>`, canal 1, LED intégrée GPIO2). Python : pièce =
  balise la plus forte 2 scans de suite -> `/doc/piece`, `/doc/balises`, `/doc/piece_chute` (et `piece` dans l'historique).
- Champs écrits seulement quand ils CHANGENT (pour les déclencheurs), renvoyés après une reconnexion : `/doc/chute`,
  `/doc/porte` (vrai = doigt sur le MAX30102 ; faux après 30 s sans contact), `/doc/en_ligne` (faux après 5 s sans mesure).
- Feu `/doc/feu` : GREEN repos ; YELLOW préalerte, test, non porté ; RED alerte, hors ligne.
- Stats par minute (données froides) : `/doc/bpm_moyen`, `/doc/bpm_min`, `/doc/bpm_max` (BPM valides 30–220 seulement),
  `/doc/accel_max`, `/doc/piece_stats`. `stats_heure` supprimé le 11 nov. (horodatage = colonne Date du dataset).
- Au démarrage : get_doc de `/doc/seuil_chute` (reprise du seuil) et création des champs absents (`derniere_chute`,
  `type_alerte`, `piece_chute`, `chutes_total`, `historique`).
- Actions de l'objet : `arreter_alarme`, `tester_alarme`, `simuler_chute`, `alterner_detection` (True/False),
  `regler_seuil` (1,2 à 4 g), et pour les procédures `enregistrer_chute` (get_doc puis update_doc de `/doc/chutes_total` +1
  et `/doc/historique`, 20 dernières alertes {date, piece, type} ; un SOS va dans l'historique mais NE compte PAS dans chutes_total, décidé le 11 nov.) et `rappel_bracelet` (non retenu).
- `interface_bracelet.html` : dessin du bracelet en HTML/CSS pour un composant HTML (ALIVEcode n'affiche pas le SVG).
- Ancien design (à ignorer) : `fallguard_pi_pont.py`, `fallguard_camera.py`, `fallguard_esp32_aliot.ino`,
  `fallguard_tableau_de_bord.txt`.

## À FAIRE
- Itération 2 : réparer/vérifier le MPU6050 puis tester une vraie chute ; tester les balises ; vérifier get_doc ;
  graphes accel et chutes ; captures, vidéo, photos.
- Itération 3 : module gestes (caméra du Pi + MediaPipe) branché sur `iteration2.py` (champ `/doc/geste`, appel de
  `arreter_alarme()`, `declencher_sos()`, `tester_alarme()` de `fallguard_utils.py`).

## INCONNU / non vérifié
- Le professeur exige-t-il une température ? Qu'attend-il par « statistiques » ?
- Brochage réel du PCB reçu vs `connexions_v5.md` et `fallguard_xiao_serie.ino` (sérigraphie non lisible sur les photos).
- Où tourne `iteration2.py` : PC ou Pi ? Modèle de la caméra (module du Pi ou webcam USB) et longueur du câble ?
- Le prof accepte-t-il l'ordinateur à la place du Pi ? Un code ESP32 compte-t-il comme « code Arduino » ?
- La librairie de détection de mains créée en classe n'a pas été vue.
- TESTÉ avec la vraie carte (COM4) et le vrai ALIVEcode : connexion, document, composants, actions, procédure
  enregistrer_chute (compteur), dataset. NON vu fonctionner : détection d'une VRAIE chute, balises de pièce, version XIAO,
  graphes accel et chutes. MediaPipe sur Pi 4 : non testé.
- 11 nov. : le MPU6050 de la platine lit ~6,8 g au repos (valeur figée, toutes les mesures « en mouvement ») alors qu'il
  lisait ~1,0 g avant les essais de chute : fil desserré ou module abîmé probable, à vérifier.
- get_doc : syntaxe chaîne `get_doc("/doc/champ")` (signature d'aliot-py 1.0.6) ; fonctionnement réel non prouvé :
  derniere_chute = « Aucune » alors que chute = true. Test : le journal au démarrage doit afficher le seuil du document (2.6).
- Remise de l'itération 2 (10 nov. 0 h 14 selon l'énoncé) : faite ou repoussée ? INCONNU.
- Valeurs attendues par le feu de circulation (GREEN/YELLOW/RED supposé) et format des valeurs du curseur.
- Le code de départ du cours (`serre_utils.py`) n'a pas pu être lu en entier.
- Date de validation du projet par le prof, noms des 4 membres et répartition des tâches.
