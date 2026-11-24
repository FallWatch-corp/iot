// FallGuard - TEST I2C du PCB : quels modules repondent, et sur quel connecteur ?
//
// Scanne le bus I2C toutes les 2 s et affiche les modules trouves :
//   0x68 = MPU6050   0x57 = MAX30102   0x3C (ou 0x3D) = OLED SSD1306
// Utilisation :
//   1) Brancher UN SEUL module, televerser, ouvrir le moniteur serie (115200 bauds).
//   2) Noter s'il est trouve. DEBRANCHER L'USB avant de changer de module ou de connecteur.
//   3) Essai utile : mettre le MPU6050 sur le connecteur de l'OLED, puis sur celui du MAX30102.
//      S'il est trouve (0x68) : 3V3, GND, SDA et SCL arrivent sur ce connecteur DANS L'ORDRE DU MPU.
//      Comparer alors l'ordre des broches ecrit sur l'OLED / le MAX30102 avec celui du MPU.
//
// Carte : "XIAO_ESP32C3", USB CDC On Boot = Enabled.
// Pour l'ESP32 DevKit (essai des modules sur breadboard) : mettre sdaPin = 21 et sclPin = 22.

#include <Wire.h>

const int sdaPin = 6;   // XIAO D4
const int sclPin = 7;   // XIAO D5

const char* nomModule(uint8_t adresse) {
  if (adresse == 0x68 || adresse == 0x69) return "MPU6050";
  if (adresse == 0x57) return "MAX30102";
  if (adresse == 0x3C || adresse == 0x3D) return "OLED SSD1306";
  return "inconnu";
}

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 5000) delay(10);
  Wire.begin(sdaPin, sclPin);
  Wire.setClock(100000);   // vitesse lente : plus tolerante aux mauvais contacts
  Serial.println("Test I2C : scan toutes les 2 s");
}

void loop() {
  // Etat des lignes au repos : 1 = tirees vers 3V3 par un module alimente
  Wire.end();              // libere les broches pour les lire, puis on relance l'I2C
  pinMode(sdaPin, INPUT);
  pinMode(sclPin, INPUT);
  int sda = digitalRead(sdaPin);
  int scl = digitalRead(sclPin);
  Wire.begin(sdaPin, sclPin);

  int trouves = 0;
  Serial.print("SDA=");
  Serial.print(sda);
  Serial.print(" SCL=");
  Serial.print(scl);
  Serial.print(" | ");
  for (uint8_t adresse = 1; adresse < 127; adresse++) {
    Wire.beginTransmission(adresse);
    if (Wire.endTransmission() == 0) {
      Serial.print("0x");
      Serial.print(adresse, HEX);
      Serial.print(" (");
      Serial.print(nomModule(adresse));
      Serial.print(")  ");
      trouves++;
    }
  }
  if (trouves == 0) Serial.print("aucun module");
  Serial.println();
  delay(2000);
}
