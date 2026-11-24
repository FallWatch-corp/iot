// FallGuard - TEST I2C du PCB : quels modules repondent, et sur quel connecteur ?
//
// Scanne le bus I2C toutes les 2 s et affiche les modules trouves :
//   0x68 = MPU6050   0x57 = MAX30102   0x3C (ou 0x3D) = OLED SSD1306
// Utilisation :
//   Essaie aussi SDA/SCL croises (erreur de cablage du PCB).
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

// Scanne le bus avec SDA/SCL donnes, retourne le nombre de modules trouves
int scanner(int sda, int scl) {
  Wire.end();
  pinMode(sda, INPUT);
  pinMode(scl, INPUT);
  Serial.print("  SDA=GPIO");
  Serial.print(sda);
  Serial.print("(");
  Serial.print(digitalRead(sda));
  Serial.print(") SCL=GPIO");
  Serial.print(scl);
  Serial.print("(");
  Serial.print(digitalRead(scl));
  Serial.print(") | ");
  Wire.begin(sda, scl);
  Wire.setClock(100000);   // vitesse lente : plus tolerante aux mauvais contacts
  int trouves = 0;
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
  return trouves;
}

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 5000) delay(10);
  Serial.println("Test I2C : scan toutes les 2 s, dans le sens normal PUIS avec SDA/SCL croises");
}

void loop() {
  Serial.println("Sens normal (celui du programme) :");
  int normal = scanner(sdaPin, sclPin);
  Serial.println("SDA et SCL croises :");
  int croise = scanner(sclPin, sdaPin);
  if (normal == 0 && croise > 0) Serial.println("=> SDA et SCL sont CROISES sur le PCB");
  if (normal == 0 && croise == 0) Serial.println("=> rien dans les deux sens : soudure, cablage ou module");
  Serial.println();
  delay(2000);
}
