// FallGuard - BALISE DE PIECE (un ESP32 DevKit ou une XIAO ESP32C3 par piece)
//
// La balise cree un petit reseau Wi-Fi nomme "FG_<piece>" (ex. "FG_Chambre"). Le bracelet scanne
// le canal 1, garde les reseaux qui commencent par "FG_" et envoie leur force (RSSI) au programme
// Python : la balise captee le plus fort = la piece ou se trouve le resident.
// Personne ne se connecte a ce reseau : il sert seulement de repere.
//
// Pour chaque balise : changer NOM_PIECE, televerser, puis brancher la balise dans sa piece
// (chargeur USB de telephone). Toutes les balises a la MEME hauteur (environ 1 m), loin les
// unes des autres, pas derriere un meuble en metal.
// NOM_PIECE : pas de virgule ni de point-virgule (separateurs de la ligne "W:"), pas d'accent
// conseille, 29 caracteres max. (SSID = 32 caracteres avec "FG_"). Un nom different par balise.
//
// Carte : "ESP32 Dev Module" ou "XIAO_ESP32C3". Aucune bibliotheque a installer.
// Moniteur serie : 115200 bauds (etat de la balise toutes les 10 s).

#include <WiFi.h>

// ---------- À MODIFIER pour chaque balise ----------
const char* NOM_PIECE = "Salle de bain";        // Chambre, Salon, Salle de bain, Cuisine...
// ----------------------------------------------------

const char* MOT_DE_PASSE = "fallguard2026"; // empeche d'autres appareils de s'y connecter (8 car. min.)
const int CANAL = 1;                        // meme canal pour toutes les balises (le bracelet scanne ce canal)
const wifi_power_t PUISSANCE = WIFI_POWER_8_5dBm;  // identique pour toutes les balises

// LED de la carte : clignote = balise active. L'ESP32 DevKit a une LED bleue sur GPIO2 ;
// la XIAO ESP32C3 n'a pas de LED programmable (on se fie alors au moniteur serie).
#if defined(CONFIG_IDF_TARGET_ESP32)
const int LED_CARTE = 2;
#else
const int LED_CARTE = -1;                   // -1 = pas de LED
#endif

String ssid;
bool balisePrete = false;
unsigned long dernierEtat = 0;

// Demarre le point d'acces. Retourne false en cas d'echec.
bool demarrerBalise() {
  WiFi.mode(WIFI_AP);
  // Canal fixe, reseau visible (un reseau cache n'a pas de nom dans le scan), 1 connexion max.
  if (!WiFi.softAP(ssid.c_str(), MOT_DE_PASSE, CANAL, 0, 1)) return false;
  // La puissance se regle APRES le demarrage du point d'acces, sinon elle peut etre ignoree
  // (et les balises n'emettraient plus a la meme force : comparaison des RSSI faussee).
  WiFi.setTxPower(PUISSANCE);
  WiFi.setSleep(false);                     // balise sur secteur : pas d'economie d'energie
  return true;
}

void setup() {
  Serial.begin(115200);
  delay(500);
  if (LED_CARTE >= 0) pinMode(LED_CARTE, OUTPUT);

  ssid = String("FG_") + NOM_PIECE;
  if (ssid.length() > 32) {
    Serial.println("ERREUR : NOM_PIECE trop long (29 caracteres max.)");
  }
  if (ssid.indexOf(',') >= 0 || ssid.indexOf(';') >= 0) {
    Serial.println("ERREUR : NOM_PIECE ne doit contenir ni ',' ni ';'");
  }

  balisePrete = demarrerBalise();
  Serial.print("Balise FallGuard : ");
  Serial.print(ssid);
  Serial.print(" (canal ");
  Serial.print(CANAL);
  Serial.println(balisePrete ? ") -> active" : ") -> ERREUR");
}

void loop() {
  // Echec au demarrage : on reessaie toutes les 5 s (LED qui clignote vite)
  if (!balisePrete) {
    for (int i = 0; i < 10 && LED_CARTE >= 0; i++) {
      digitalWrite(LED_CARTE, i % 2 == 0 ? HIGH : LOW);
      delay(250);
    }
    if (LED_CARTE < 0) delay(5000);
    WiFi.mode(WIFI_OFF);
    delay(100);
    balisePrete = demarrerBalise();
    Serial.println(balisePrete ? "Balise : redemarree -> active" : "Balise : ERREUR, nouvel essai dans 5 s");
    return;
  }

  // Etat dans le moniteur serie toutes les 10 s
  if (millis() - dernierEtat >= 10000) {
    dernierEtat = millis();
    Serial.print("Balise ");
    Serial.print(ssid);
    Serial.print(" active, canal ");
    Serial.print(WiFi.channel());
    Serial.print(", appareils connectes : ");
    Serial.println(WiFi.softAPgetStationNum());
  }

  // Clignotement lent : la balise fonctionne
  if (LED_CARTE >= 0) {
    digitalWrite(LED_CARTE, HIGH);
    delay(100);
    digitalWrite(LED_CARTE, LOW);
  }
  delay(1900);
}
