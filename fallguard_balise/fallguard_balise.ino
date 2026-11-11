// FallGuard - BALISE DE PIECE (un ESP32 DevKit par piece)
//
// La balise cree un petit reseau Wi-Fi nomme "FG_<piece>" (ex. "FG_Chambre"). Le bracelet scanne
// les reseaux, garde ceux qui commencent par "FG_" et envoie leur force (RSSI) au programme
// Python : la balise captee le plus fort = la piece ou se trouve le resident.
// Personne ne se connecte a ce reseau : il sert seulement de repere.
//
// Pour chaque balise : changer NOM_PIECE, televerser, puis brancher la balise dans sa piece
// (chargeur USB de telephone). Toutes les balises a la MEME hauteur (environ 1 m), loin les
// unes des autres, pas derriere un meuble en metal.
//
// Carte : "ESP32 Dev Module". Aucune bibliotheque a installer.

#include <WiFi.h>

// ---------- À MODIFIER pour chaque balise ----------
const char* NOM_PIECE = "Chambre";        // Chambre, Salon, Salle de bain, Cuisine...
// ----------------------------------------------------

const char* MOT_DE_PASSE = "fallguard2026"; // empeche d'autres appareils de s'y connecter (8 car. min.)
const int CANAL = 1;                        // meme canal pour toutes les balises
const int LED_CARTE = 2;                    // LED bleue de l'ESP32 DevKit : clignote = balise active

void setup() {
  Serial.begin(115200);
  pinMode(LED_CARTE, OUTPUT);

  String ssid = String("FG_") + NOM_PIECE;
  WiFi.mode(WIFI_AP);
  WiFi.setTxPower(WIFI_POWER_8_5dBm);       // puissance moderee et identique pour toutes les balises
  bool ok = WiFi.softAP(ssid.c_str(), MOT_DE_PASSE, CANAL);

  Serial.print("Balise FallGuard : ");
  Serial.print(ssid);
  Serial.println(ok ? " -> active" : " -> ERREUR");
}

void loop() {
  // Clignotement lent : la balise fonctionne
  digitalWrite(LED_CARTE, HIGH);
  delay(100);
  digitalWrite(LED_CARTE, LOW);
  delay(1900);
}
