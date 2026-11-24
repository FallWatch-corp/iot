// FallGuard - TEST sans multimetre : e la XIAO alimente-t-elle le PCB ?
//
// Principe : les modules I2C (OLED, MPU6050, MAX30102) ont des resistances qui tirent
// SDA et SCL vers LEUR alimentation. On met une petite resistance interne vers GND
// sur SDA et SCL, puis on lit les broches :
//   - HIGH (1) : un module alimente tire la ligne vers 3V3 -> 3V3, GND et la soudure sont OK
//   - LOW  (0) : aucun module alimente sur cette ligne -> verifier pastilles 12 (3V3), 13 (GND),
//                5 (SDA) ou 6 (SCL), et les soudures/fils de J4
//
// Brancher l'OLED sur J4 avant de lancer le test.
// Carte : "XIAO_ESP32C3", USB CDC On Boot = Enabled. Moniteur serie : 115200 bauds.

const int sdaPin = 6;   // D4 = pastille 5 de la XIAO
const int sclPin = 7;   // D5 = pastille 6 de la XIAO

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 5000) delay(10);
  pinMode(sdaPin, INPUT_PULLDOWN);
  pinMode(sclPin, INPUT_PULLDOWN);
}

void loop() {
  int sda = digitalRead(sdaPin);
  int scl = digitalRead(sclPin);

  Serial.print("SDA (pastille 5) = ");
  Serial.print(sda);
  Serial.print("   SCL (pastille 6) = ");
  Serial.print(scl);

  if (sda == HIGH && scl == HIGH) {
    Serial.println("   -> PCB alimente, SDA et SCL relies : OK");
  } else if (sda == LOW && scl == LOW) {
    Serial.println("   -> rien : verifier pastilles 12 (3V3) et 13 (GND), soudures et fils de J4");
  } else if (sda == LOW) {
    Serial.println("   -> SDA coupe : verifier pastille 5 et le fil SDA");
  } else {
    Serial.println("   -> SCL coupe : verifier pastille 6 et le fil SCL");
  }
  delay(1000);
}
