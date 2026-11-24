// FallGuard - TEST sans multimetre : SDA et SCL sont-ils relies entre eux (court-circuit) ?
//
// Principe : on met une ligne a 0 (sortie LOW) et on lit l'autre, tiree vers 3V3.
//   - l'autre ligne reste a 1 : pas de court-circuit entre SDA et SCL (normal)
//   - l'autre ligne passe a 0 : SDA et SCL sont RELIES (goutte de soudure entre les
//     pastilles 5 et 6 de la XIAO, ou entre les broches 3 et 4 de J3/J4/J5)
// On lit aussi chaque ligne avec une resistance vers GND (pulldown) :
//   - SANS module branche, on doit lire 0. Si on lit 1 : la ligne touche le 3V3.
//
// Carte : "XIAO_ESP32C3", USB CDC On Boot = Enabled. Moniteur serie : 115200 bauds.

const int sdaPin = 6;   // XIAO D4 = pastille 5
const int sclPin = 7;   // XIAO D5 = pastille 6

// Met "basse" a 0 pendant 2 ms et lit "lue" (tiree vers 3V3 par la resistance interne)
int lireAvecAutreA0(int basse, int lue) {
  pinMode(lue, INPUT_PULLUP);
  pinMode(basse, OUTPUT);
  digitalWrite(basse, LOW);
  delay(2);
  int valeur = digitalRead(lue);
  pinMode(basse, INPUT);           // on relache tout de suite
  return valeur;
}

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 5000) delay(10);
  Serial.println("Test court-circuit SDA/SCL");
}

void loop() {
  pinMode(sdaPin, INPUT_PULLDOWN);
  pinMode(sclPin, INPUT_PULLDOWN);
  delay(2);
  int sdaRepos = digitalRead(sdaPin);
  int sclRepos = digitalRead(sclPin);

  // Controle : chaque ligne seule, tiree vers 3V3, l'autre relachee -> doit lire 1
  pinMode(sclPin, INPUT);
  pinMode(sdaPin, INPUT_PULLUP);
  delay(2);
  int sdaControle = digitalRead(sdaPin);
  pinMode(sdaPin, INPUT);
  pinMode(sclPin, INPUT_PULLUP);
  delay(2);
  int sclControle = digitalRead(sclPin);
  pinMode(sclPin, INPUT);

  int sdaQuandScl0 = lireAvecAutreA0(sclPin, sdaPin);
  int sclQuandSda0 = lireAvecAutreA0(sdaPin, sclPin);

  Serial.print("Repos (pulldown) : SDA=");
  Serial.print(sdaRepos);
  Serial.print(" SCL=");
  Serial.print(sclRepos);
  Serial.print("  |  controle SDA=");
  Serial.print(sdaControle);
  Serial.print(" SCL=");
  Serial.print(sclControle);
  Serial.print("  |  SCL a 0 -> SDA=");
  Serial.print(sdaQuandScl0);
  Serial.print("  SDA a 0 -> SCL=");
  Serial.print(sclQuandSda0);

  if (sdaControle == 0 || sclControle == 0) {
    Serial.println("   => controle a 0 : une ligne est tiree vers GND (test non concluant)");
  } else if (sdaQuandScl0 == 0 || sclQuandSda0 == 0) {
    Serial.println("   => SDA et SCL RELIES : court-circuit (soudure) !");
  } else {
    Serial.println("   => pas de court-circuit entre SDA et SCL");
  }
  delay(2000);
}
