# FallGuard : bracelet de détection de chute

Projet du cours **420-5D7 Internet des objets**.

**Équipe :** Oladé Junior, Delavie, Glodie, Alexander.

FallGuard est un bracelet pour résidences de personnes âgées. Il **détecte les chutes** et mesure le **pouls**. Il indique aussi **dans quelle pièce** se trouve le résident. Les alertes et les mesures s'affichent sur un tableau de bord **ALIVEcode**, où le personnel peut aussi agir sur le bracelet.

---

## 1. Vue d'ensemble

```
  Balises de pièce (ESP32)          Bracelet (ESP32 DevKit)                 Ordinateur                    ALIVEcode
  ┌──────────────────┐   Wi-Fi    ┌─────────────────────────┐  USB série   ┌──────────────────┐  Internet  ┌──────────────────┐
  │ FG_Chambre       │ ─ RSSI ──► │ MPU6050  (mouvement)    │ ───────────► │ iteration2.py    │ ─────────► │ Document (JSON)  │
  │ FG_Salon   ...   │            │ MAX30102 (pouls)        │ ◄─────────── │ fallguard_utils  │ ◄───────── │ Interface        │
  └──────────────────┘            │ OLED, buzzer, bouton    │  commandes   │ (aliot-py)       │  actions   │ Procédure,       │
                                  └─────────────────────────┘              └──────────────────┘            │ déclencheurs,    │
                                                                                                           │ dataset, graphes │
                                                                                                           └──────────────────┘
```

Le travail est réparti ainsi :
1. Le **bracelet** fait les mesures et décide s'il y a une chute. Il envoie une ligne de mesures par seconde sur le port série.
2. **`iteration2.py`** lit ces lignes, trouve la pièce, calcule les statistiques et écrit dans le document ALIVEcode (`update_doc`).
3. **ALIVEcode** affiche l'interface. Les boutons de l'interface renvoient des actions au programme (`on_action_recv`), qui les transmet au bracelet.

---

## 2. Matériel (prototype sur platine)

| Élément | Rôle | Branchement (ESP32 DevKit) |
|---|---|---|
| ESP32 DevKit | Carte du bracelet | — |
| MPU6050 (I2C 0x68) | Accéléromètre et gyroscope : détection de chute | SDA 21, SCL 22 |
| MAX30102 (I2C 0x57) | Pouls (BPM) et contact avec la peau | SDA 21, SCL 22 |
| OLED SSD1306 (I2C 0x3C) | Date, heure et BPM ; message en cas de chute | SDA 21, SCL 22 |
| Buzzer | Alarme | GPIO 25 |
| Bouton latéral | Annuler une préalerte, arrêter l'alarme, SOS | GPIO 27 (`INPUT_PULLUP`, vers GND) |
| ESP32 DevKit (×1 par pièce) | Balise de pièce | Alimentée par un chargeur USB |

Le bracelet n'a ni LED ni caméra. Une version sur PCB (XIAO ESP32C3) est en cours d'assemblage. Elle utilise le même code et les mêmes commandes, dans le dossier `fallguard_xiao_serie_1/`.

---

## 3. Fonctionnalités

### 3.1 Détection de chute (sur le bracelet)
Le MPU6050 est lu **100 fois par seconde**. Une chute est reconnue en **3 phases** :

1. **Impact** : l'accélération dépasse le seuil, **2,5 g** par défaut. Le seuil se règle de 1,2 à 4 g avec le curseur de l'interface.
2. **Attente de 1 s**, le temps que le bracelet se stabilise.
3. **Vérification de 3 s** : le résident doit être **presque immobile**, avec au plus 25 % des mesures « en mouvement ». Il faut aussi **au moins une** de ces deux conditions :
   - une **chute libre** juste avant l'impact (moins de 0,5 g) ;
   - un **changement d'orientation** d'au moins 40° par rapport à la position de départ.

Cette méthode évite qu'un simple geste brusque ou un bracelet cogné sur une table ne déclenche une alarme.

**Préalerte de 15 s.** Avant de donner l'alerte, le bracelet sonne et affiche un message. Le résident peut **annuler avec le bouton** s'il va bien. Sans annulation, l'**alerte** part vers ALIVEcode.

**SOS.** Un **appui long de 2 s** sur le bouton déclenche une alerte de type `sos`, même sans chute.

### 3.2 Pouls et « bracelet porté »
- Le MAX30102 mesure le **BPM**. Il détecte aussi le **contact avec la peau** : l'infrarouge dépasse 50 000 quand la peau est posée sur le capteur.
- `/doc/porte` passe à **faux** seulement après **30 s sans contact**. Le capteur perd souvent le contact quelques secondes quand le poignet bouge.
- Un bracelet non porté ne peut pas détecter de chute. Le statut l'indique, et le feu passe au jaune.

### 3.3 Localisation par pièce (Wi-Fi, force du signal)
Un GPS ne fonctionne pas à l'intérieur et ne dit pas dans quelle pièce on est. Nous utilisons donc la **force du signal Wi-Fi** (RSSI) de petites balises.

**Principe :**
1. Chaque pièce reçoit une **balise** : un ESP32 DevKit avec [fallguard_balise.ino](fallguard_balise/fallguard_balise.ino). Elle crée un petit réseau Wi-Fi nommé **`FG_<pièce>`**, par exemple `FG_Chambre` ou `FG_Salon`.
   - Personne ne s'y connecte : il sert seulement de repère.
   - Toutes les balises émettent avec la **même puissance** (8,5 dBm) sur le **même canal** (1). Leurs signaux sont donc comparables.
2. Toutes les **10 s**, le bracelet fait un **scan Wi-Fi** sans bloquer la détection de chute. Il garde seulement les réseaux qui commencent par `FG_` et envoie leur force au programme : `W:Chambre,-48;Salon,-71`.
3. Le programme Python choisit la **balise la plus forte**, c'est-à-dire le RSSI le plus proche de 0. **-48 dBm est plus fort que -71 dBm.**
4. **Anti-sauts :** la pièce change seulement si la même balise est la plus forte **2 scans de suite**, soit environ 20 s. Un scan sans aucune balise est ignoré, sauf s'il y en a **3 de suite** : la pièce devient alors « Inconnue ». Ces règles évitent que la pièce saute d'une valeur à l'autre près d'une porte.
5. Résultats dans le document :
   - `/doc/piece` : la pièce actuelle ;
   - `/doc/balises` : tous les signaux captés ;
   - `/doc/piece_chute` : la pièce au moment de l'alerte, également notée dans l'historique.

**Installation des balises :**
- dans `fallguard_balise.ino`, changer `NOM_PIECE`, puis téléverser ;
- une balise par pièce, toutes à environ **1 m** de hauteur ;
- loin les unes des autres, pas derrière un meuble en métal.

La LED bleue de la carte clignote quand la balise est active.

**Limites :** les murs, le corps du résident et les meubles changent le signal. On obtient **la pièce**, pas une position précise. Deux pièces très ouvertes l'une sur l'autre peuvent être confondues.

### 3.4 Statistiques (données froides)
Chaque **minute**, le programme écrit :
- `/doc/bpm_moyen`, `/doc/bpm_min` et `/doc/bpm_max`, calculés seulement avec les BPM valides (bracelet porté, de 30 à 220) ;
- `/doc/accel_max` ;
- `/doc/piece_stats`.

Ces champs remplissent le dataset **Fallguard_mesures**, une ligne par mise à jour, avec la date ajoutée automatiquement. Les graphes du tableau de bord sont tirés de ce dataset.

Le compteur `/doc/chutes_total` et l'historique `/doc/historique` gardent les 20 dernières alertes, avec la date, la pièce et le type. Un **SOS** va dans l'historique mais **ne compte pas** comme une chute.

---

## 4. ALIVEcode

### Document (champs principaux)

| Champ | Contenu |
|---|---|
| `/doc/bpm`, `/doc/accel`, `/doc/rssi` | Mesures de chaque seconde (accel = pic de la dernière seconde, en g) |
| `/doc/niveau`, `/doc/statut`, `/doc/feu` | État (`repos`, `prealerte`, `alerte`, `test`) ; texte du statut ; feu `GREEN`, `YELLOW` ou `RED` |
| `/doc/chute`, `/doc/porte`, `/doc/en_ligne` | Booléens surveillés par les déclencheurs (écrits seulement quand ils changent) |
| `/doc/derniere_chute`, `/doc/type_alerte`, `/doc/piece_chute` | Dernière alerte (date, `chute` ou `sos`, pièce) |
| `/doc/piece`, `/doc/balises` | Localisation |
| `/doc/chutes_total`, `/doc/historique` | Compteur et historique des alertes |
| `/doc/seuil_chute`, `/doc/detection_active` | Réglages (repris au démarrage avec `get_doc`) |
| `/doc/bpm_moyen`, `/doc/bpm_min`, `/doc/bpm_max`, `/doc/accel_max`, `/doc/piece_stats` | Statistiques par minute |

Le **feu** est vert au repos. Il est jaune en préalerte, en test ou quand le bracelet n'est pas porté. Il est rouge en alerte ou quand le bracelet est hors ligne.

### Actions de l'interface (`on_action_recv`)

| Action | Effet |
|---|---|
| `arreter_alarme` | Arrête l'alarme du bracelet |
| `tester_alarme` | Fait sonner le bracelet (test) |
| `simuler_chute` | Lance une préalerte de chute (démonstration sans tomber) |
| `alterner_detection` | Interrupteur : active ou coupe la détection |
| `regler_seuil` | Curseur : seuil d'impact, de 1,2 à 4 g |
| `enregistrer_chute` | Appelée par une procédure : compteur et historique (`get_doc`, puis `update_doc`) |

Le journal (`Mylog`) et l'avertisseur sonore (`Mybuzzer`) sont alimentés avec `update_component`.

### Procédure et déclencheurs
- Le déclencheur **`/doc/chute` == true** lance la procédure « Enregistrer chute ». Celle-ci envoie l'action `enregistrer_chute` à l'objet `watch`.
- D'autres déclencheurs sont prévus dans le projet ALIVEcode :
  - objet déconnecté ;
  - `/doc/porte` == false ;
  - `/doc/en_ligne` == false ;
  - `/doc/detection_active` == false.

---

## 5. Protocole série (bracelet ↔ ordinateur, 115 200 bauds)

**Du bracelet vers l'ordinateur**

| Ligne | Signification |
|---|---|
| `D:bpm:accel:rssi:etat:doigt:type` | Mesures, une fois par seconde |
| `E:alerte:chute` ou `E:alerte:sos` | Début d'une alerte |
| `E:annule` | Préalerte annulée par le résident |
| `E:acquitte` | Alerte arrêtée avec le bouton |
| `W:Chambre,-48;Salon,-71` | Scan des balises, toutes les 10 s |

**De l'ordinateur vers le bracelet**

| Commande | Effet |
|---|---|
| `a` | Arrêter l'alarme |
| `t` | Tester l'alarme |
| `o` | Déclencher un SOS |
| `c` | Simuler une chute |
| `e` / `x` | Activer / couper la détection |
| `s` + 1 octet | Régler le seuil, en dixièmes de g |

---

## 6. Fichiers

| Fichier | Rôle |
|---|---|
| [iteration2.py](iteration2.py) | Programme principal : lit le bracelet et l'envoie à ALIVEcode (objet `watch`) |
| [fallguard_utils.py](fallguard_utils.py) | Port série : lecture des lignes, envoi des commandes, mode simulation sans carte |
| [watch/watch.py](watch/watch.py) | Copie de `iteration2.py`, lancée par `aliot run watch` |
| [fallguard_esp32_serie_1/](fallguard_esp32_serie_1/) | Croquis du bracelet (ESP32 DevKit) |
| [fallguard_balise/](fallguard_balise/) | Croquis d'une balise de pièce |
| [secrets.h.exemple](secrets.h.exemple) | Modèle du fichier Wi-Fi du bracelet |
| [interface_bracelet.html](interface_bracelet.html) | Dessin du bracelet pour un composant HTML de l'interface |

**Ne jamais publier :** `config.ini`, qui contient le jeton de l'objet ALIVEcode, et `secrets.h`, qui contient le mot de passe Wi-Fi. Les deux sont exclus par `.gitignore`.

---

## 7. Installation et lancement

1. **Bracelet**
   1. Copier `secrets.h.exemple` dans `fallguard_esp32_serie_1/` sous le nom `secrets.h`, puis y écrire le réseau Wi-Fi (2,4 GHz). Le Wi-Fi sert à l'heure de l'écran.
   2. Ouvrir `fallguard_esp32_serie_1.ino` dans l'IDE Arduino.
   3. Choisir la carte **ESP32 Dev Module** et téléverser.
2. **Balises** : changer `NOM_PIECE` dans `fallguard_balise.ino`, puis téléverser sur chaque ESP32 de pièce.
3. **Python**
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install aliot-py pyserial
   ```
   Mettre le `config.ini` de l'objet ALIVEcode (section `[watch]`) à la racine du projet.
4. **Lancer** depuis la racine du projet, après avoir **fermé le moniteur série** de l'IDE Arduino :
   ```
   aliot run watch
   ```
   Ou bien `python iteration2.py`. Le port série est détecté automatiquement.

   Pour tester sans carte, mettre `SIMULATION = True` dans `fallguard_utils.py`.

---

## 8. État des tests et limites

**Testé avec la vraie carte et ALIVEcode :**
- la connexion, le document, les composants et les actions ;
- la procédure `enregistrer_chute` et son compteur ;
- le dataset ;
- la chute simulée, avec la dernière alerte (date, type, pièce) ;
- la localisation par pièce avec plusieurs balises ;
- la détection d'une **vraie** chute par le MPU6050 (essai physique).

**Pas encore vérifié :**
- les graphes d'accélération et de chutes ;
- la version PCB (XIAO).

**Limites connues :**
- Les seuils de chute sont des valeurs de départ, à ajuster par essais.
- Le MAX30102 a besoin d'un bon contact avec la peau.
- La localisation dépend des murs et des meubles (voir 3.3).
- Le bracelet doit rester branché à l'ordinateur par USB : il n'a pas encore de batterie.
