# Révision : examen pratique IoT (vendredi 27 novembre 2026)

## L'examen
- **Matière** : Arduino ; Python dans VS Code avec pyserial ; aliot-py pour faire le tableau de bord (comme à l'itération 2).
- **Format** : sur machine.
- **Permis** : tout le site alivecode.ca (la doc aliot ET les pages du cours).
- **Matériel** : Arduino + n'importe lequel des capteurs vus en cours (un ou plusieurs).

Comme le site est permis, il ne faut pas tout apprendre par cœur. Il faut surtout **retrouver vite** les exemples du cours, **les adapter** et **déboguer**.

> Ce document vient des pages du cours que j'ai pu lire (Arduino, pyserial / serre, Aliot-3, 4 et 5) et de notre itération 2.
> Je n'ai pas lu `serre_utils.py` en entier ni le détail des clics dans l'interface ALIVEcode : vérifiez ces parties sur le site.

---

## Plan de révision

| Jour | Quoi faire |
|---|---|
| **Lun 23** | Parcourir les pages du cours. Pour chaque capteur, noter **où** est l'exemple (nom de la page et de la section) dans l'index en bas de ce fichier. But : tout retrouver en moins de 30 s. Refaire chaque capteur seul : le lire, l'envoyer en série, réagir avec la LED ou le buzzer. |
| **Mar 24** | Partir du code de la serre et le modifier pour un autre capteur ou une autre commande. Faire 2 ou 3 variantes chronométrées, avec 2 ou 3 capteurs dans la même ligne série. |
| **Mer 25** | aliot et interface : refaire le tableau de bord de l'itération 2 **avec la doc ouverte**. Exercices de débogage : trouver les erreurs (port, vitesse, `/doc/`, `b''`, id d'action…). |
| **Jeu 26** | Examen blanc de 2 h, sur machine, avec le site ouvert. |
| **Ven 27 matin** | Relire la section « Pièges ». Vérifier que tout est installé : venv, pyserial, aliot-py, IDE Arduino, pilote USB de la carte. |

---

## Le chemin des données (à savoir expliquer)

**Données (capteur vers tableau de bord)**
```
capteur → Arduino : Serial.print("a:b:c") → câble USB → Python : readline() + split(':')
        → update_doc({"/doc/x": ...}) → composant CONTRÔLÉ de l'interface (lié à /doc/x)
```

**Commandes (tableau de bord vers actionneur)**
```
bouton / interrupteur / curseur de l'interface (id d'action) → on_action_recv(action_id=...)
        → ser.write(b'1') → Arduino : Serial.read() → LED / buzzer
```

**Composant NON contrôlé** (Logs, buzzer de l'interface) : seulement avec `update_component("id", valeur)`.

---

## 1. Arduino

### Squelette complet
```cpp
#include <DHT.h>                 // seulement si DHT11
#define DHTPIN 7
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);

const int ledPin = 3;
const int buzzer = 2;
const int buttonPin = 12;
const int photoresistorPin = A0;

int buttonState = HIGH;          // état précédent
int currentButtonState;          // état actuel

void setup() {
  Serial.begin(9600);
  pinMode(ledPin, OUTPUT);
  pinMode(buzzer, OUTPUT);
  pinMode(buttonPin, INPUT);     // + résistance externe 10 kΩ (ou INPUT_PULLUP sans résistance)
  dht.begin();
}

void loop() {
  // Read sensors
  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();
  int luminosity = analogRead(photoresistorPin);   // 0 à 1023 sur Uno

  // Send to Python: values separated by ':'
  Serial.print(temperature); Serial.print(":");
  Serial.print(humidity);    Serial.print(":");
  Serial.println(luminosity);                      // println = fin de ligne (OBLIGATOIRE)

  // Button: detect the press (edge)
  currentButtonState = digitalRead(buttonPin);
  if (currentButtonState == LOW && buttonState == HIGH) {
    Serial.println("button pressed");
  }
  buttonState = currentButtonState;

  // Commands from Python (1 character)
  if (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '1') digitalWrite(ledPin, HIGH);
    else if (c == '0') digitalWrite(ledPin, LOW);
    else if (c == 'b') { tone(buzzer, 1500); delay(300); noTone(buzzer); }
  }
  delay(1000);
}
```

### Aide-mémoire par capteur
Seulement les capteurs vus dans les pages lues. **À compléter** avec les autres capteurs du cours.

| Capteur | Lecture / commande | Piège |
|---|---|---|
| DHT11 | `#include <DHT.h>`, `DHT dht(DHTPIN, DHTTYPE);`, `dht.begin();`, `dht.readTemperature()`, `dht.readHumidity()` | `isnan()` si la lecture échoue. Une lecture au plus toutes les 1 à 2 s. |
| Photorésistance | `analogRead(A0)`, de 0 à 1023 (0 à 4095 sur ESP32) | Le sens (plus de lumière = plus grand ou plus petit) dépend du montage : vérifier en vrai. |
| Bouton | `digitalRead(buttonPin)` + détection du front (`buttonState` / `currentButtonState`) | Sans front, le code réagit à chaque tour de `loop()`. Rebonds : ajouter `delay(30)`. |
| LED | `pinMode(ledPin, OUTPUT)`, `digitalWrite(ledPin, HIGH/LOW)` | Résistance d'environ 220 Ω. |
| Buzzer | `tone(buzzer, 1500)` / `noTone(buzzer)` | Un buzzer actif n'a besoin que de `digitalWrite`. |
| … | | |

### À savoir expliquer
- `digitalRead` / `digitalWrite` : HIGH ou LOW. `analogRead` : un nombre.
- **Front d'un bouton** : on compare l'ancien état et l'état actuel.
- **`delay()` bloque** tout le programme. Pour attendre sans bloquer, on utilise `millis()` :
  ```cpp
  unsigned long dernier = 0;
  if (millis() - dernier >= 1000) { dernier = millis(); /* ... */ }
  ```
- `INPUT_PULLUP` : pas de résistance externe, appuyé = LOW.

### Exercice
Un potentiomètre règle la fréquence du buzzer, et la valeur est envoyée en série.

---

## 2. pyserial (Python ↔ Arduino)

### Module utils (comme `serre_utils.py`)
```python
import serial
import threading
import time
import math

ser = serial.Serial('COM24', 9600)   # même vitesse que Serial.begin
time.sleep(2)                        # la carte redémarre à l'ouverture du port

temperature = None
humidity = None
luminosity = None
_led_state = False

def _lire_serie():
    global temperature, humidity, luminosity
    while True:
        ligne = ser.readline().decode('utf-8', errors='ignore').strip()
        parties = ligne.split(':')
        if len(parties) != 3:
            continue                 # ligne de débogage ou incomplète
        try:
            temperature = float(parties[0])
            humidity = float(parties[1])
            luminosity = int(parties[2])
        except ValueError:
            pass

threading.Thread(target=_lire_serie, daemon=True).start()

def get_temperature_and_humidity():
    if temperature is None or humidity is None or math.isnan(temperature):
        return None, None
    return temperature, humidity

def get_luminosity():
    return luminosity

def get_led_state():
    return _led_state

def set_led(value):
    global _led_state
    ser.write(b'1' if value else b'0')   # write prend des OCTETS (b'...')
    _led_state = value
```

### À savoir expliquer
- `decode()` et `strip()` : `readline()` renvoie des **octets** avec `\r\n` à la fin.
- Le **thread** : `readline()` attend une ligne et bloquerait le reste du programme.
- `ser.write("1".encode())` revient au même que `b'1'`.
- Le port : `COMx` sous Windows (Gestionnaire de périphériques), `/dev/ttyUSB0` ou `/dev/ttyACM0` sous Linux.
- Installation : `python -m venv venv_projet`, activer le venv, puis `pip install pyserial aliot-py`.

### Exercice
Afficher `print(f"Temp: {temp} | Humidity: {hum}")` chaque seconde, et allumer la LED quand la luminosité passe sous 300.

---

## 3. aliot-py

### Préparer le projet
1. Sur ALIVEcode : créer l'**objet IoT** pour obtenir son `obj_id` et son `auth_token`, puis l'ajouter au projet.
2. Dans le dossier : `aliot init`, puis `aliot new rasp-serre`.
3. `config.ini` contient une section `[rasp-serre]` avec `obj_id`, `auth_token` et `main = ...`. **Jamais sur GitHub.**
4. Lancer : `aliot run rasp-serre`.

### Programme principal
```python
# Documentation: https://alivecode.ca/docs/aliot
import time
import serre_utils
from aliot.aliot_obj import AliotObj

# Attente pour bien établir la communication avec le capteur
time.sleep(5)

# Création de l'objet à partir du fichier de configuration
rasp_serre = AliotObj("rasp-serre")          # = nom de la section dans config.ini

# Action de l'interface (bouton / interrupteur / curseur)
def set_led_cb(value):                        # interrupteur : True / False
    serre_utils.set_led(value)
    rasp_serre.update_doc({"/doc/light": value})

def buzz(data):
    rasp_serre.update_component("Mybuzzer", 450)     # composant NON contrôlé

# Écouteur : appelé quand un champ du document change
def humidite_change(fields):
    print("Nouvelle humidité :", fields['/doc/humidity'])

rasp_serre.on_action_recv(action_id="set_led", callback=set_led_cb)
rasp_serre.on_action_recv(action_id="buzz", callback=buzz)
rasp_serre.listen_doc(["/doc/humidity"], callback=humidite_change)

def start():
    # Lecture dans la base au démarrage
    seuil = rasp_serre.get_doc("/doc/seuil")
    while True:
        try:
            # Obtenir les données du capteur
            temp, hum = serre_utils.get_temperature_and_humidity()
            lum = serre_utils.get_luminosity()
            # Envoi des données au serveur ALIVEcode
            if temp is not None:
                rasp_serre.update_doc({"/doc/temperature": temp,
                                       "/doc/humidity": hum,
                                       "/doc/luminosity": lum})
            time.sleep(1)
        except KeyboardInterrupt:
            break

rasp_serre.on_start(callback=start)
rasp_serre.run()          # connects your object to the server (toujours la DERNIÈRE ligne)
```

### Les méthodes
| Méthode | Rôle |
|---|---|
| `AliotObj("nom")` | crée l'objet à partir de `config.ini` |
| `update_doc({"/doc/x": v})` | écrit un ou plusieurs champs du document (base « chaude ») |
| `get_doc("/doc/x")` | lit un champ |
| `listen_doc(["/doc/x"], callback=f)` | `f(fields)` est appelée quand le champ change ; lire `fields['/doc/x']` |
| `update_component("id", v)` | envoie une valeur à un composant **non contrôlé** (Logs, buzzer) |
| `on_action_recv(action_id="id", callback=f)` | `f(data)` est appelée quand un bouton, un interrupteur ou un curseur envoie cette action |
| `on_start(callback=start)` | `start()` démarre à la connexion |
| `run()` | se connecte à ALIVEcode (bloquant, en dernier) |
| `stop()` | se déconnecte |

### Exercice
Un curseur règle le seuil (`/doc/seuil`). Quand la luminosité passe sous le seuil : la LED s'allume et une ligne s'écrit dans le journal.

---

## 4. Interface ALIVEcode
- **Composant contrôlé** : lié à un champ du document (jauge ou affichage sur `/doc/temperature`). Il se met à jour seul quand `update_doc` écrit ce champ.
- **Composant non contrôlé** : Logs ou buzzer, avec un id personnalisé (`Mylog`, `Mybuzzer`), alimenté par `update_component`.
- **Bouton, interrupteur, curseur** : on leur donne un **id d'action**, exactement le même que dans `on_action_recv`. L'interrupteur envoie True/False, le curseur un nombre.
- **Procédure** (onglet Procédures) :
  - « Envoi d'actions » : id d'action, avec un JSON en option ;
  - « Envoi de courriels » : objet + corps, envoyé au créateur du projet.
- **Déclencheur** (onglet Déclencheurs) :
  - « Changement dans la base de données » : `champ comparateur valeur` → procédure ;
  - « Changement d'état de connexion » : Connecté/Déconnecté → procédure.
- **Données froides** : créer un dataset, ajouter ses colonnes (il se remplit quand les champs changent), puis ajouter un graphe.
- Pour réviser : rouvrir le projet « FallWatch » de l'itération 2 et refaire un composant de chaque type.

---

## 5. Pièges (à relire le matin de l'examen)
1. **Port occupé** : fermer le moniteur série de l'IDE Arduino avant de lancer Python.
2. **Même vitesse** des deux côtés (9600).
3. `time.sleep(2)` après l'ouverture du port, sinon les premières lignes se perdent.
4. `ser.write` prend des **octets** : `b'1'`, pas `'1'`.
5. Le préfixe **`/doc/`** est obligatoire dans `update_doc` et `get_doc`.
6. Envoyer les **vrais types** : un nombre reste un nombre, `True`/`False` restent des booléens, pas `"25"`.
7. Le nom dans `AliotObj("...")` est le même que la section de `config.ini`.
8. L'id d'action est le même dans l'interface et dans `on_action_recv` (majuscules comprises).
9. `run()` va en dernier : le code placé après ne s'exécute jamais.
10. Il faut `println` à la fin de la ligne côté Arduino, sinon `readline()` attend sans fin.
11. Vu dans FallGuard (pas écrit dans le cours) : deux `update_doc` dans la même seconde, et le 2e peut se perdre. Il vaut mieux regrouper les champs dans un seul appel.

### Messages d'erreur fréquents
| Symptôme | Cause probable |
|---|---|
| « port occupé » / `PermissionError` | le moniteur série (ou un autre programme) a le port |
| `could not open port` | mauvais COM, ou carte débranchée |
| caractères bizarres dans `readline()` | vitesse différente entre `Serial.begin` et `serial.Serial` |
| `ValueError` dans `float(...)` | ligne incomplète ou ligne de débogage : vérifier `len(parties)` |
| le composant ne bouge pas | champ mal écrit, `/doc/` oublié, ou composant pas lié au bon champ |
| le bouton de l'interface ne fait rien | id d'action différent entre l'interface et `on_action_recv` |
| l'objet ne se connecte pas | `obj_id` / `auth_token` faux, ou section de `config.ini` différente du nom dans `AliotObj` |

---

## Index du cours (à remplir lundi)
| Je cherche… | Page du cours / section sur alivecode.ca |
|---|---|
| DHT11 | |
| Photorésistance | |
| Bouton | |
| LED / buzzer | |
| Autres capteurs : … | |
| pyserial : ouvrir le port, lire, écrire | |
| `serre_utils.py` complet | |
| `update_doc` / `update_component` | |
| `on_action_recv` / `listen_doc` / `get_doc` | |
| Créer l'objet, `config.ini`, `aliot init/new/run` | |
| Interface : composants contrôlés | |
| Procédures / déclencheurs / données froides | |
