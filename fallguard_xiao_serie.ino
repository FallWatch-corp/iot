// FallGuard - Bracelet (ESP32 DevKit ou XIAO ESP32C3), version SERIE pour ALIVEcode (itération 2)
//
// Comme dans le cours Aliot (serre connectee) : la carte est branchee en USB a l'ordinateur et
// parle en serie (115200 bauds). Le programme Python iteration2.py lit les lignes "D:..." et les
// publie dans le document ALIVEcode ; il renvoie des commandes (a, t, e, x, s+octet).
// IMPORTANT : fermer le moniteur serie de l'IDE Arduino avant de lancer le programme Python
// (un seul programme peut utiliser le port a la fois).
// Le Wi-Fi ne sert plus qu'a obtenir l'heure (NTP). Sans Wi-Fi : l'ecran affiche "--:--".
//

//
// Fonctionnement (version 2) :
//   - L'OLED affiche en permanence la date, l'heure et le pouls (BPM).
//   - DETECTION DE CHUTE EN 3 PHASES (MPU6050, accelerometre + gyroscope) :
//       1) impact : |a| depasse le seuil (2,5 g par defaut, reglable depuis le tableau de bord),
//          eventuellement precede d'une chute libre (|a| sous 0,5 g) ;
//       2) attente de 1 s, puis observation pendant 3 s ;
//       3) la chute est retenue si le bracelet reste IMMOBILE ET (chute libre vue OU orientation
//          changee d'au moins 40 degres). Sinon : fausse alerte, on ne fait rien.
//   - PREALERTE de 15 s : buzzer par impulsions, ecran "CHUTE ?". Un appui sur le bouton ANNULE
//     (le Pi est prevenu). Sans appui, l'ALERTE part : buzzer continu, ecran "CHUTE !", et le Pi
//     est prevenu (photo + verification par camera).
//   - SOS : appui long (2 s) sur le bouton = alerte immediate, sans delai d'annulation.
//   - En alerte, un appui sur le bouton arrete le buzzer et previent le Pi.
//   - Toutes les 2 s, le bracelet envoie ses mesures au Raspberry Pi (POST /donnees) et recoit en
//     reponse les commandes du tableau de bord (arreter, tester, seuil, detection, delai).
//   - L'heure vient d'Internet (NTP). SANS Wi-Fi : "--:--". Pas de LED.
//
// TOUS LES SEUILS DE DETECTION SONT DES VALEURS DE DEPART, A AJUSTER PAR ESSAIS
// (chutes simulees sur un matelas, gestes du quotidien). Rien n'a ete teste sur une vraie carte.
//
// Bibliothèques (Gestionnaire de bibliothèques) : Adafruit SSD1306 et Adafruit GFX
// (le JSON est lu a la main : pas besoin d'ArduinoJson).
// Moniteur série : 115200 bauds.
//
// ---- Choix de la carte ----
//   ESP32 DevKit : carte "ESP32 Dev Module", laisser la ligne CARTE_XIAO_C3 en commentaire.
//   XIAO ESP32C3 : carte "XIAO_ESP32C3", option "USB CDC On Boot" = Enabled,
//                  et retirer les // devant #define CARTE_XIAO_C3.
//
// ---- Branchements (alimentation 3,3 V) ----
//                          ESP32 DevKit     XIAO ESP32C3
//   I2C SDA (OLED, MPU, MAX)   D21           D4  (GPIO6)
//   I2C SCL                    D22           D5  (GPIO7)
//   Buzzer                     D25           D1  (GPIO3)
//   Bouton (l'autre patte GND) D27           D10 (GPIO10)
//   GPS : TX du GPS ->         GPIO16        D7  (GPIO20)
//   GPS : RX du GPS ->         GPIO17        D6  (GPIO21)

#include <Wire.h>
#include <WiFi.h>
#include <time.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define CARTE_XIAO_C3   // <-- version XIAO ESP32C3 (carte "XIAO_ESP32C3", USB CDC On Boot = Enabled)

// ---------- Broches ----------
#ifdef CARTE_XIAO_C3
const int sdaPin = 6;
const int sclPin = 7;
const int gpsRxPin = 20;   // reçoit le TX du GPS
const int gpsTxPin = 21;   // envoie vers le RX du GPS
const int buzzer = 3;
const int buttonPin = 10;
const char* nomObjet = "xiao";     // doit correspondre a OBJETS dans fallguard_pi_pont.py
#else
const int sdaPin = 21;
const int sclPin = 22;
const int gpsRxPin = 16;
const int gpsTxPin = 17;
const int buzzer = 25;
const int buttonPin = 27;
const char* nomObjet = "esp32";
#endif

// ---------- Wi-Fi, heure et Raspberry Pi (À MODIFIER) ----------
const char* wifiSsid = "VOTRE_SSID";
const char* wifiMotDePasse = "VOTRE_MOT_DE_PASSE";
const char* fuseau = "EST5EDT,M3.2.0,M11.1.0";   // Montréal : heure d'été et d'hiver automatiques

const char* jours[] = {"dim", "lun", "mar", "mer", "jeu", "ven", "sam"};
const char* moisNoms[] = {"janv", "fevr", "mars", "avr", "mai", "juin",
                          "juil", "aout", "sept", "oct", "nov", "dec"};

// ---------- Adresses I2C ----------
const uint8_t adresseMPU = 0x68;
const uint8_t adresseOLED = 0x3C;
const uint8_t adresseMAX = 0x57;

// ---------- Seuils de détection (valeurs de départ, à ajuster) ----------
float seuilChute = 2.5;                       // g : impact (modifiable depuis le tableau de bord)
bool detectionActive = true;                  // false = chutes ignorees (tableau de bord)
const float seuilChuteLibre = 0.5;            // g : sous cette valeur = chute libre
const unsigned long fenetreChuteLibre = 1000; // ms : chute libre valable jusqu'a l'impact
const unsigned long attenteApresImpact = 1000;// ms : laisser le bracelet se stabiliser
const unsigned long dureeVerification = 3000; // ms : observation de l'immobilite
const float seuilGyroMouvement = 60.0;        // deg/s : au-dessus = mouvement
const float ecartAccelMouvement = 0.35;       // g : ecart a 1 g au-dessus duquel = mouvement
const float partMouvementMax = 0.25;          // max. 25 % d'echantillons "en mouvement"
const float angleChangementMin = 40.0;        // deg : changement d'orientation exige
const unsigned long delaiSOS = 2000;          // ms : appui long = SOS
unsigned long delaiAnnulation = 15000;        // ms : modifiable par le Pi (reponse "delai")
const long seuilDoigt = 50000;                // valeur infrarouge quand la peau est posee

Adafruit_SSD1306 display(128, 64, &Wire, -1);
HardwareSerial gpsSerial(1);

// ---------- États du bracelet ----------
enum Etat { REPOS, VERIF, PREALERTE, ALERTE, TEST };
Etat etat = REPOS;
String typeAlerte = "";                       // "chute" ou "sos"

// ---------- Variables ----------
bool mpuOK = false;
bool maxOK = false;
bool oledOK = false;

float ax, ay, az, magnitude;       // accélération en g
float gx, gy, gz, gyroTotal;       // rotation en deg/s
long valeurIR = 0;                 // dernière valeur infrarouge du MAX30102

const bool utiliserGPS = false;    // false = ne pas lire le GPS (débranché)
const bool afficherNMEA = false;   // true = afficher les phrases GGA et RMC dans le moniteur série
String ligneGPS = "";
unsigned long octetsGPS = 0;
unsigned long phrasesGPS = 0;
bool gpsFix = false;
String gpsSatellites = "0";

unsigned long dernierTestChute = 0;
unsigned long dernierAffichage = 0;
unsigned long dernierSerie = 0;
unsigned long derniereLectureMAX = 0;
unsigned long dernierEnvoiDonnees = 0;

// ---------- Détection de chute ----------
float refX = 0, refY = 0, refZ = 1;           // direction de la gravité au repos (moyenne lente)
int echantillonsChuteLibre = 0;
bool chuteLibreVue = false;
unsigned long tChuteLibre = 0;
bool chuteLibreAuImpact = false;
unsigned long debutImpact = 0;
float impactG = 0;
int nbEch = 0, nbMouv = 0;
float sommeX = 0, sommeY = 0, sommeZ = 0;
unsigned long finInhibition = 0;              // pas de nouvelle detection avant cet instant
unsigned long debutPrealerte = 0;
unsigned long debutTest = 0;
bool buzzerSon = false;

// ---------- Calcul du pouls (BPM) ----------
int bpm = 0;                       // pouls calculé (0 = pas de mesure)
float lisse = 0;                   // signal IR adouci
float base = 0;                    // niveau moyen lent du signal
float amplitude = 0;               // taille des variations récentes
bool armeBattement = false;        // true quand on a vu un creux du signal
bool doigtPresent = false;
unsigned long numEchantillon = 0;  // compteur d'échantillons (1 échantillon = 10 ms)
unsigned long dernierBattement = 0;
unsigned long intervalles[4];      // 4 derniers intervalles entre battements, en ms
int nbIntervalles = 0;
int indexIntervalle = 0;

// ---------- Bouton ----------
int buttonState;                   // état précédent du bouton
int currentButtonState;            // état actuel du bouton
unsigned long debutAppui = 0;
bool appuiTraite = true;

// =====================================================
// I2C : fonctions de base
// =====================================================
bool presenceI2C(uint8_t adresse) {
  Wire.beginTransmission(adresse);
  return Wire.endTransmission() == 0;
}

void ecrireRegistre(uint8_t adresse, uint8_t registre, uint8_t valeur) {
  Wire.beginTransmission(adresse);
  Wire.write(registre);
  Wire.write(valeur);
  Wire.endTransmission();
}

uint8_t lireRegistre(uint8_t adresse, uint8_t registre) {
  Wire.beginTransmission(adresse);
  Wire.write(registre);
  Wire.endTransmission(false);
  Wire.requestFrom(adresse, (uint8_t)1);
  if (Wire.available()) return Wire.read();
  return 0xFF;
}

void scannerI2C() {
  Serial.println("--- Scan I2C ---");
  int trouves = 0;
  for (uint8_t adresse = 1; adresse < 127; adresse++) {
    if (presenceI2C(adresse)) {
      Serial.print("Appareil a l'adresse 0x");
      if (adresse < 16) Serial.print("0");
      Serial.println(adresse, HEX);
      trouves++;
    }
  }
  if (trouves == 0) Serial.println("Aucun appareil I2C. Verifier SDA, SCL, 3V3 et GND.");
}

// =====================================================
// MPU6050 : accéléromètre + gyroscope
// =====================================================
void initMPU() {
  mpuOK = presenceI2C(adresseMPU);
  if (!mpuOK) {
    Serial.println("MPU6050 : absent (0x68)");
    return;
  }
  ecrireRegistre(adresseMPU, 0x6B, 0x00);   // sortir du mode veille
  ecrireRegistre(adresseMPU, 0x1C, 0x10);   // accéléromètre +-8 g (4096 par g) : l'impact ne sature plus
  ecrireRegistre(adresseMPU, 0x1B, 0x08);   // gyroscope +-500 deg/s (65,5 par deg/s)
  ecrireRegistre(adresseMPU, 0x1A, 0x02);   // filtre passe-bas ~94 Hz
  Serial.println("MPU6050 : OK (+-8 g, +-500 deg/s)");
}

int16_t lire16() {
  int16_t v = Wire.read() << 8;             // octet de poids fort
  v = v | Wire.read();                      // octet de poids faible
  return v;
}

bool lireMPU() {
  Wire.beginTransmission(adresseMPU);
  Wire.write(0x3B);                         // premier registre de l'accélération
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(adresseMPU, (uint8_t)14) != 14) return false;
  int16_t brutX = lire16();
  int16_t brutY = lire16();
  int16_t brutZ = lire16();
  lire16();                                 // température (ignorée)
  int16_t gyroX = lire16();
  int16_t gyroY = lire16();
  int16_t gyroZ = lire16();
  ax = brutX / 4096.0;
  ay = brutY / 4096.0;
  az = brutZ / 4096.0;
  magnitude = sqrt(ax * ax + ay * ay + az * az);
  gx = gyroX / 65.5;
  gy = gyroY / 65.5;
  gz = gyroZ / 65.5;
  gyroTotal = sqrt(gx * gx + gy * gy + gz * gz);
  return true;
}

// =====================================================
// MAX30102 : lumière infrarouge et pouls
// =====================================================
void initMAX() {
  maxOK = presenceI2C(adresseMAX);
  if (!maxOK) {
    Serial.println("MAX30102 : absent (0x57)");
    return;
  }
  Serial.print("MAX30102 : detecte, Part ID = 0x");
  Serial.println(lireRegistre(adresseMAX, 0xFF), HEX);   // doit valoir 0x15

  ecrireRegistre(adresseMAX, 0x09, 0x40);   // remise à zéro
  delay(100);
  ecrireRegistre(adresseMAX, 0x04, 0x00);   // vider la mémoire FIFO
  ecrireRegistre(adresseMAX, 0x05, 0x00);
  ecrireRegistre(adresseMAX, 0x06, 0x00);
  ecrireRegistre(adresseMAX, 0x08, 0x1F);   // pas de moyenne, la mémoire se réécrit en continu
  ecrireRegistre(adresseMAX, 0x09, 0x03);   // mode SpO2 : LED rouge + infrarouge
  ecrireRegistre(adresseMAX, 0x0A, 0x27);   // 100 mesures par seconde
  ecrireRegistre(adresseMAX, 0x0C, 0x3F);   // intensité de la LED rouge
  ecrireRegistre(adresseMAX, 0x0D, 0x3F);   // intensité de la LED infrarouge
}

// Analyse un échantillon IR (100 par seconde) pour détecter les battements du coeur.
// Principe : le signal monte et descend à chaque battement. On repère un creux,
// puis la remontée qui suit = 1 battement. Le temps entre 2 battements donne le BPM.
void traiterEchantillon(long s) {
  numEchantillon++;

  if (s < seuilDoigt) {                    // pas de contact : on remet tout à zéro
    doigtPresent = false;
    bpm = 0;
    nbIntervalles = 0;
    indexIntervalle = 0;
    dernierBattement = 0;
    armeBattement = false;
    amplitude = 0;
    return;
  }
  if (!doigtPresent) {                     // le contact vient de commencer
    doigtPresent = true;
    lisse = s;
    base = s;
  }

  lisse = lisse * 0.7 + s * 0.3;           // adoucir le bruit
  base = base * 0.98 + lisse * 0.02;       // niveau moyen lent
  float ac = lisse - base;                 // variation due au battement

  amplitude = amplitude * 0.995;           // l'amplitude s'adapte lentement
  if (fabs(ac) > amplitude) amplitude = fabs(ac);
  float seuil = amplitude * 0.4;

  if (amplitude > 20 && ac < -seuil) armeBattement = true;   // creux détecté

  if (armeBattement && ac > 0) {           // remontée après le creux = battement
    armeBattement = false;
    if (dernierBattement != 0) {
      unsigned long duree = (numEchantillon - dernierBattement) * 10;   // en ms
      if (duree < 300) return;             // trop rapide (> 200 BPM) : du bruit
      if (duree <= 2000) {                 // entre 30 et 200 BPM
        intervalles[indexIntervalle] = duree;
        indexIntervalle = (indexIntervalle + 1) % 4;
        if (nbIntervalles < 4) nbIntervalles++;
        unsigned long somme = 0;
        for (int i = 0; i < nbIntervalles; i++) somme += intervalles[i];
        bpm = 60000 / (somme / nbIntervalles);
      }
    }
    dernierBattement = numEchantillon;
  }
}

// Lit tous les échantillons en attente du MAX30102.
void lireMAX() {
  uint8_t ecriture = lireRegistre(adresseMAX, 0x04);
  uint8_t lecture = lireRegistre(adresseMAX, 0x06);
  int nombre = (ecriture - lecture) & 0x1F;
  if (nombre == 0 && lireRegistre(adresseMAX, 0x05) != 0) nombre = 32;   // mémoire pleine
  for (int i = 0; i < nombre; i++) {
    Wire.beginTransmission(adresseMAX);
    Wire.write(0x07);                       // registre de données
    Wire.endTransmission(false);
    if (Wire.requestFrom(adresseMAX, (uint8_t)6) != 6) return;
    for (int k = 0; k < 3; k++) Wire.read();   // on ignore les 3 octets de la LED rouge
    long infrarouge = 0;
    for (int k = 0; k < 3; k++) {
      infrarouge = (infrarouge << 8) | Wire.read();
    }
    valeurIR = infrarouge & 0x3FFFF;
    traiterEchantillon(valeurIR);
  }
  ecrireRegistre(adresseMAX, 0x05, 0x00);   // remettre à zéro le compteur de débordement
}

// =====================================================
// OLED : écran normal (date, heure, BPM) et écran de chute
// =====================================================
void initOLED() {
  oledOK = presenceI2C(adresseOLED) && display.begin(SSD1306_SWITCHCAPVCC, adresseOLED);
  if (!oledOK) {
    Serial.println("OLED : absent (0x3C)");
    return;
  }
  Serial.println("OLED : OK");
  display.clearDisplay();
  display.setTextSize(2);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("FallGuard");
  display.display();
}

// Lit l'heure locale. Retourne false tant que l'heure n'a pas été reçue d'Internet.
bool lireHeure(struct tm* t) {
  return getLocalTime(t, 0);
}

void afficherEcranNormal() {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);

  struct tm t;
  bool heureOK = lireHeure(&t);

  // Date (en haut)
  display.setTextSize(1);
  display.setCursor(0, 0);
  if (heureOK) {
    display.print(jours[t.tm_wday]);
    display.print(" ");
    display.print(t.tm_mday);
    display.print(" ");
    display.print(moisNoms[t.tm_mon]);
    display.print(" ");
    display.print(t.tm_year + 1900);
  } else {
    display.print("Heure : attente Wi-Fi");
  }

  // Heure (grande) et secondes (petites)
  char buf[8];
  display.setTextSize(3);
  display.setCursor(0, 14);
  if (heureOK) {
    snprintf(buf, sizeof(buf), "%02d:%02d", t.tm_hour, t.tm_min);
  } else {
    snprintf(buf, sizeof(buf), "--:--");
  }
  display.print(buf);
  if (heureOK) {
    display.setTextSize(2);
    display.setCursor(104, 21);
    snprintf(buf, sizeof(buf), "%02d", t.tm_sec);
    display.print(buf);
  }

  // BPM (en bas)
  display.setTextSize(2);
  display.setCursor(0, 46);
  display.print("BPM ");
  if (valeurIR < seuilDoigt) {
    display.print("--");
  } else if (bpm > 0) {
    display.print(bpm);
  } else {
    display.print("...");
  }
  display.display();
}

void afficherEcranAlerte() {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(2);
  display.setCursor(0, 4);
  if (etat == PREALERTE) {
    display.println("CHUTE ?");
    unsigned long ecoule = millis() - debutPrealerte;
    unsigned long reste = (ecoule >= delaiAnnulation) ? 0 : (delaiAnnulation - ecoule) / 1000 + 1;
    display.setTextSize(1);
    display.setCursor(0, 28);
    display.print("Alerte dans ");
    display.print(reste);
    display.println(" s");
    display.setCursor(0, 48);
    display.println("Bouton = annuler");
  } else if (etat == ALERTE) {
    display.println(typeAlerte == "sos" ? "SOS !" : "CHUTE !");
    display.setTextSize(1);
    display.setCursor(0, 30);
    display.println("Aide prevenue");
    display.setCursor(0, 48);
    display.println("Bouton = arreter");
  } else {
    display.println("TEST");
    display.setTextSize(1);
    display.setCursor(0, 30);
    display.println("Test de l'alarme");
    display.setCursor(0, 48);
    display.println("Bouton = arreter");
  }
  display.display();
}

void afficherEcran() {
  if (!oledOK) return;
  if (etat == REPOS || etat == VERIF) {
    afficherEcranNormal();    // l'écran ne change qu'en préalerte, alerte ou test
  } else {
    afficherEcranAlerte();
  }
}

// =====================================================
// GPS : lecture des phrases NMEA (optionnel, résultats dans le moniteur série)
// =====================================================
String champ(String ligne, int numero) {
  int debut = 0;
  for (int i = 0; i < numero; i++) {
    debut = ligne.indexOf(',', debut);
    if (debut < 0) return "";
    debut++;
  }
  int fin = ligne.indexOf(',', debut);
  if (fin < 0) fin = ligne.length();
  return ligne.substring(debut, fin);
}

void traiterLigneGPS(String ligne) {
  phrasesGPS++;
  if (afficherNMEA && (ligne.indexOf("GGA") == 3 || ligne.indexOf("RMC") == 3)) {
    Serial.print("NMEA : ");
    Serial.println(ligne);
  }
  if (ligne.indexOf("RMC") == 3) {
    gpsFix = (champ(ligne, 2) == "A");      // A = position valide
  } else if (ligne.indexOf("GGA") == 3) {
    gpsSatellites = champ(ligne, 7);
  }
}

void lireGPS() {
  while (gpsSerial.available()) {
    char c = gpsSerial.read();
    octetsGPS++;
    if (c == '\n') {
      if (ligneGPS.length() > 6 && ligneGPS[0] == '$') traiterLigneGPS(ligneGPS);
      ligneGPS = "";
    } else if (c != '\r') {
      if (ligneGPS.length() < 120) ligneGPS += c;
    }
  }
}

// =====================================================
// Wi-Fi : connexion, heure (NTP) et signaux envoyés au Raspberry Pi
// =====================================================
void connecterWiFi() {
  Serial.print("WiFi : connexion a ");
  Serial.println(wifiSsid);
  WiFi.mode(WIFI_STA);
  WiFi.begin(wifiSsid, wifiMotDePasse);
  unsigned long debut = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - debut < 10000) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("WiFi : OK, IP = ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("WiFi : ECHEC (SSID, mot de passe, reseau 2,4 GHz ?)");
  }
}

// Demande l'heure à Internet. Appelée même sans Wi-Fi : l'heure arrivera
// dès que la connexion sera là.
void initHeure() {
  configTzTime(fuseau, "pool.ntp.org", "time.nist.gov");
}

// ---- Communication série avec l'ordinateur (comme dans le cours Aliot) ----
// Chaque ligne commençant par "D:" = mesures ; "E:" = événement. Les autres lignes sont du
// texte de débogage que le programme Python ignore.
void envoyerChutePi(const String& type) {
  Serial.println("E:alerte:" + type);
}

void acquitterPi() {
  Serial.println("E:acquitte");
}

void annulerPi() {
  Serial.println("E:annule");
}

// =====================================================
// Buzzer, alerte et états
// =====================================================
// À appeler souvent : préalerte = impulsions, alerte et test = son continu
void mettreAJourBuzzer() {
  bool son = false;
  if (etat == ALERTE || etat == TEST) {
    son = true;
  } else if (etat == PREALERTE) {
    son = ((millis() / 300) % 2 == 0);
  }
  if (son != buzzerSon) {
    buzzerSon = son;
    if (son) tone(buzzer, 1500); else noTone(buzzer);
  }
}

void bip(int frequence, int duree) {
  tone(buzzer, frequence);
  delay(duree);
  noTone(buzzer);
}

String nomEtat() {
  if (etat == PREALERTE) return "prealerte";
  if (etat == ALERTE) return "alerte";
  if (etat == TEST) return "test";
  return "repos";
}

void retourAuRepos() {
  etat = REPOS;
  finInhibition = millis() + 5000;     // évite de re-détecter le geste du bouton
  chuteLibreVue = false;
  mettreAJourBuzzer();
  afficherEcran();
}

void demarrerPrealerte() {
  etat = PREALERTE;
  debutPrealerte = millis();
  Serial.println("PREALERTE : chute probable, annulation possible avec le bouton");
  mettreAJourBuzzer();
  afficherEcran();
}

void passerEnAlerte(const String& type) {
  typeAlerte = type;
  etat = ALERTE;
  Serial.print("ALERTE (");
  Serial.print(type);
  Serial.println(")");
  mettreAJourBuzzer();
  afficherEcran();
  envoyerChutePi(type);                // le Pi prend une photo et vérifie avec la caméra
}

void demarrerTest() {
  if (etat != REPOS) return;
  etat = TEST;
  debutTest = millis();
  mettreAJourBuzzer();
  afficherEcran();
  Serial.println("TEST d'alarme (tableau de bord)");
}

// Envoie une ligne de mesures à l'ordinateur : D:bpm:accel:rssi:etat:doigt:type
void envoyerDonnees() {
  int rssi = (WiFi.status() == WL_CONNECTED) ? WiFi.RSSI() : 0;
  Serial.print("D:");
  Serial.print(bpm);
  Serial.print(":");
  Serial.print(magnitude, 2);
  Serial.print(":");
  Serial.print(rssi);
  Serial.print(":");
  Serial.print(nomEtat());
  Serial.print(":");
  Serial.print(doigtPresent ? 1 : 0);
  Serial.print(":");
  Serial.println(typeAlerte.length() > 0 ? typeAlerte : String("-"));
}

// Commandes reçues de l'ordinateur (1 caractère chacune) :
//   a = arrêter l'alarme   t = tester l'alarme   e = détection activée   x = détection coupée
//   s + 1 octet = seuil de chute en dixièmes de g (ex. 25 = 2,5 g)
void lireCommandes() {
  static bool attendSeuil = false;
  while (Serial.available()) {
    int c = Serial.read();
    if (attendSeuil) {
      seuilChute = constrain(c / 10.0, 1.2, 4.0);
      attendSeuil = false;
      Serial.print("Seuil de chute = ");
      Serial.println(seuilChute, 1);
    } else if (c == 'a') {
      if (etat != REPOS && etat != VERIF) {
        retourAuRepos();
        Serial.println("Alarme arretee depuis l'ordinateur");
      }
    } else if (c == 't') {
      demarrerTest();
    } else if (c == 'e') {
      detectionActive = true;
    } else if (c == 'x') {
      detectionActive = false;
    } else if (c == 's') {
      attendSeuil = true;
    }
  }
}

// =====================================================
// Détection de chute en 3 phases (appelée toutes les 10 ms)
// =====================================================
void testerChute() {
  unsigned long t = millis();

  if (etat == REPOS) {
    // La direction de la gravité au repos sert de référence pour mesurer le changement d'orientation
    if (magnitude > 0.8 && magnitude < 1.2) {
      refX = refX * 0.95 + ax * 0.05;
      refY = refY * 0.95 + ay * 0.05;
      refZ = refZ * 0.95 + az * 0.05;
    }
    // Chute libre : |a| très faible pendant au moins 3 échantillons (30 ms)
    if (magnitude < seuilChuteLibre) {
      echantillonsChuteLibre++;
      if (echantillonsChuteLibre >= 3) {
        chuteLibreVue = true;
        tChuteLibre = t;
      }
    } else {
      echantillonsChuteLibre = 0;
    }
    if (chuteLibreVue && t - tChuteLibre > fenetreChuteLibre) chuteLibreVue = false;

    // Phase 1 : impact
    if (detectionActive && t >= finInhibition && magnitude > seuilChute) {
      etat = VERIF;
      debutImpact = t;
      impactG = magnitude;
      chuteLibreAuImpact = chuteLibreVue;
      nbEch = 0;
      nbMouv = 0;
      sommeX = sommeY = sommeZ = 0;
      Serial.print("Impact : ");
      Serial.print(impactG, 2);
      Serial.print(" g, chute libre avant = ");
      Serial.println(chuteLibreAuImpact ? "oui" : "non");
    }
    return;
  }

  if (etat != VERIF) return;

  // Phase 2 : attendre que le bracelet se stabilise, puis observer
  unsigned long ecoule = t - debutImpact;
  if (ecoule < attenteApresImpact) return;

  nbEch++;
  bool mouvement = (gyroTotal > seuilGyroMouvement) || (fabs(magnitude - 1.0) > ecartAccelMouvement);
  if (mouvement) nbMouv++;
  sommeX += ax;
  sommeY += ay;
  sommeZ += az;

  if (ecoule < attenteApresImpact + dureeVerification) return;

  // Phase 3 : décision
  bool immobile = (nbEch > 0) && (nbMouv <= partMouvementMax * nbEch);
  float angle = 0;
  float mx = sommeX / nbEch, my = sommeY / nbEch, mz = sommeZ / nbEch;
  float na = sqrt(mx * mx + my * my + mz * mz);
  float nr = sqrt(refX * refX + refY * refY + refZ * refZ);
  if (na > 0.1 && nr > 0.1) {
    float c = (mx * refX + my * refY + mz * refZ) / (na * nr);
    angle = acos(constrain(c, -1.0, 1.0)) * 180.0 / PI;
  }
  bool confirmee = immobile && (chuteLibreAuImpact || angle >= angleChangementMin);

  Serial.print("Verification : mouvement ");
  Serial.print(nbMouv);
  Serial.print("/");
  Serial.print(nbEch);
  Serial.print(", orientation changee de ");
  Serial.print(angle, 0);
  Serial.print(" deg -> ");
  Serial.println(confirmee ? "CHUTE" : "fausse alerte");

  if (confirmee) {
    demarrerPrealerte();
  } else {
    etat = REPOS;
    chuteLibreVue = false;
    finInhibition = millis() + 2000;
  }
}

// =====================================================
// Bouton : annuler (préalerte), arrêter (alerte/test), SOS (appui long)
// =====================================================
void gererBouton() {
  buttonState = currentButtonState;
  currentButtonState = digitalRead(buttonPin);
  unsigned long t = millis();

  if (currentButtonState == LOW && buttonState == HIGH) {      // début d'appui
    Serial.println("button pressed");
    debutAppui = t;
    appuiTraite = false;
    if (etat == PREALERTE) {
      appuiTraite = true;
      retourAuRepos();
      Serial.println("Prealerte annulee");
      annulerPi();
    } else if (etat == ALERTE || etat == TEST) {
      bool etaitTest = (etat == TEST);
      appuiTraite = true;
      retourAuRepos();
      Serial.println("Alarme arretee");
      if (!etaitTest) acquitterPi();
    }
    delay(30);                                                 // évite les rebonds
  }

  // Appui long en repos = SOS
  if (currentButtonState == LOW && !appuiTraite && (etat == REPOS || etat == VERIF)
      && t - debutAppui >= delaiSOS) {
    appuiTraite = true;
    passerEnAlerte("sos");
  }
}

// =====================================================
// Programme principal
// =====================================================
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("FallGuard (bracelet, version 2)");

  pinMode(buzzer, OUTPUT);
  pinMode(buttonPin, INPUT_PULLUP);   // bouton relâché = HIGH, appuyé = LOW
  digitalWrite(buzzer, LOW);
  currentButtonState = digitalRead(buttonPin);

  Wire.begin(sdaPin, sclPin);
  Wire.setClock(400000);              // I2C rapide : l'écran bloque moins la lecture du MPU6050
  scannerI2C();
  initMPU();
  initMAX();
  initOLED();

  if (utiliserGPS) {
    gpsSerial.begin(9600, SERIAL_8N1, gpsRxPin, gpsTxPin);
    Serial.println("GPS : ecoute a 9600 bauds");
  }
  connecterWiFi();
  initHeure();

  bip(1000, 200);
  delay(150);
  bip(2000, 200);
}

void loop() {
  if (utiliserGPS) lireGPS();
  gererBouton();

  // MAX30102 : lecture toutes les 100 ms (sinon la mémoire du capteur déborde)
  if (maxOK && millis() - derniereLectureMAX >= 100) {
    derniereLectureMAX = millis();
    lireMAX();
  }

  // MPU6050 : 100 mesures par seconde pour ne pas rater l'impact
  if (mpuOK && millis() - dernierTestChute >= 10) {
    dernierTestChute = millis();
    if (lireMPU()) testerChute();
  }

  // Fin de la préalerte (pas d'annulation) -> alerte
  if (etat == PREALERTE && millis() - debutPrealerte >= delaiAnnulation) passerEnAlerte("chute");
  // Le test d'alarme s'arrête tout seul après 5 s
  if (etat == TEST && millis() - debutTest > 5000) retourAuRepos();
  mettreAJourBuzzer();

  lireCommandes();

  // Mesures vers l'ordinateur toutes les secondes
  if (millis() - dernierEnvoiDonnees >= 1000) {
    dernierEnvoiDonnees = millis();
    envoyerDonnees();
  }

  // Écran : 4 fois par seconde en préalerte (compte à rebours), sinon 1 fois par seconde
  unsigned long periodeEcran = (etat == PREALERTE) ? 250 : 1000;
  if (millis() - dernierAffichage >= periodeEcran) {
    dernierAffichage = millis();
    afficherEcran();
  }

  // Moniteur série toutes les secondes
  if (millis() - dernierSerie >= 1000) {
    dernierSerie = millis();
    Serial.print("etat=");
    Serial.print(nomEtat());
    Serial.print(" |a|=");
    Serial.print(magnitude, 2);
    Serial.print(" g, rot=");
    Serial.print(gyroTotal, 0);
    Serial.print(" deg/s, IR=");
    Serial.print(valeurIR);
    Serial.print(" BPM=");
    Serial.println(bpm);
    if (utiliserGPS) {
      Serial.print("GPS : octets=");
      Serial.print(octetsGPS);
      Serial.print(" phrases=");
      Serial.print(phrasesGPS);
      Serial.print(" fix=");
      Serial.print(gpsFix ? "OUI" : "non");
      Serial.print(" satellites=");
      Serial.println(gpsSatellites);
    }
  }
}
