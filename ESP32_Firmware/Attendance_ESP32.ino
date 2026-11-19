#include <SPI.h>
#include <MFRC522.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>

// 1. RC522 RFID Pins (VSPI)
#define SS_PIN  5
#define RST_PIN 4
MFRC522 mfrc522(SS_PIN, RST_PIN);

// 2. SH110X OLED Setup (I2C: SDA=21, SCL=22)
#define OLED_ADDR 0x3c
Adafruit_SH1106G oled = Adafruit_SH1106G(128, 64, &Wire, -1);
bool oledAvailable = false;

// 3. Serial to Arduino Uno (Serial2: RX=16, TX=17)
#define RXD2 16
#define TXD2 17

// Student Record Structure
struct Student {
  String uidPattern;
  String roll;
  String name;
  String pin;
};

#define MAX_STUDENTS 2
Student studentDB[MAX_STUDENTS] = {
  {"F30", "101", "John", "1234"},
  {"DF5", "102", "Alice", "1234"}
};

int logCount = 0;
String lastLoggedName = "None";
String lastLoggedRoll = "----";
unsigned long lastHeartbeat = 0;

void updateOled(String statusMsg) {
  if (!oledAvailable) return;
  oled.clearDisplay();
  oled.setCursor(0, 0);
  oled.setTextSize(1);
  oled.println("ATTENDANCE SYSTEM");
  oled.println("---------------------");
  oled.println("Mode: Desktop Python");
  oled.print("Total Logged: ");
  oled.println(logCount);
  oled.println("---------------------");
  oled.print("Last: ");
  oled.println(lastLoggedName);
  oled.println(statusMsg);
  oled.display();
}

void logAttendance(String roll, String name, String method, String uid) {
  logCount++;
  lastLoggedName = name;
  lastLoggedRoll = roll;
  updateOled("Logged: " + name);

  // Send structured JSON packet over USB Serial to Python Desktop App
  Serial.print("[DATA] {\"name\":\"");
  Serial.print(name);
  Serial.print("\",\"roll\":\"");
  Serial.print(roll);
  Serial.print("\",\"method\":\"");
  Serial.print(method);
  Serial.print("\",\"uid\":\"");
  Serial.print(uid);
  Serial.print("\",\"count\":");
  Serial.print(logCount);
  Serial.println("}");

  // Notify Arduino Uno over Serial2 to trigger buzzer & 16x2 LCD
  Serial2.println("OK:" + name + ":" + roll);
}

void setup() {
  Serial.begin(115200);
  Serial2.begin(9600, SERIAL_8N1, RXD2, TXD2);

  // 1. SPI & RFID Init
  SPI.begin();
  mfrc522.PCD_Init();
  delay(50);
  mfrc522.PCD_SetAntennaGain(mfrc522.RxGain_max); // Max 48dB RF gain
  mfrc522.PCD_AntennaOff();
  delay(10);
  mfrc522.PCD_AntennaOn();

  Serial.println("\n==================================");
  Serial.println("  ESP32 ATTENDANCE HUB (PYTHON)   ");
  Serial.println("==================================");
  mfrc522.PCD_DumpVersionToSerial();

  // 2. OLED Init (Optional check)
  Wire.begin(21, 22);
  Wire.beginTransmission(OLED_ADDR);
  if (Wire.endTransmission() == 0) {
    if (oled.begin(OLED_ADDR, true)) {
      oledAvailable = true;
      oled.setTextColor(SH110X_WHITE);
      oled.clearDisplay();
      oled.setCursor(0, 10);
      oled.println("ATTENDANCE ONLINE");
      oled.println("Connected to PC");
      oled.display();
      Serial.println("[OLED] Connected at 0x3C");
    }
  } else {
    Serial.println("[OLED] Not detected on I2C (skipping OLED render)");
  }

  updateOled("Ready for Cards");
  Serial.println("[SYSTEM] ESP32 Ready for Python App connection");
}

void loop() {
  // 1. Scan for RFID Cards (checks both NewCard and Wakeup for halted clone cards)
  bool cardDetected = mfrc522.PICC_IsNewCardPresent();
  if (!cardDetected) {
    byte bufferATQA[2];
    byte bufferSize = sizeof(bufferATQA);
    cardDetected = (mfrc522.PICC_WakeupA(bufferATQA, &bufferSize) == MFRC522::STATUS_OK);
  }

  if (cardDetected && mfrc522.PICC_ReadCardSerial()) {
    String cardUid = "";
    for (byte i = 0; i < mfrc522.uid.size; i++) {
      if (mfrc522.uid.uidByte[i] < 0x10) cardUid += "0";
      cardUid += String(mfrc522.uid.uidByte[i], HEX);
    }
    cardUid.toUpperCase();
    Serial.println("\n>>> RFID CARD SCANNED: " + cardUid);

    // Identify Student
    String matchedName = "";
    String matchedRoll = "";

    if (cardUid.indexOf("F30") >= 0 || cardUid.indexOf("F3") >= 0) {
      matchedName = "John";
      matchedRoll = "101";
    } else if (cardUid.indexOf("DF5") >= 0 || cardUid.indexOf("DF") >= 0) {
      matchedName = "Alice";
      matchedRoll = "102";
    } else {
      matchedName = "Card " + cardUid.substring(0, 4);
      matchedRoll = cardUid.substring(0, 4);
    }

    // Instantly log attendance!
    logAttendance(matchedRoll, matchedName, "RFID Direct", cardUid);

    mfrc522.PICC_HaltA();
    mfrc522.PCD_StopCrypto1();
    delay(800); // Debounce
  }

  // 2. Listen for Manual Roll Verification from Uno Keypad
  if (Serial2.available()) {
    String request = Serial2.readStringUntil('\n');
    request.trim();

    if (request.startsWith("VERIFY_ROLL:")) {
      int colon1 = request.indexOf(':', 12);
      String roll = request.substring(12, colon1);
      String pin = request.substring(colon1 + 1);

      bool found = false;
      for (int i = 0; i < MAX_STUDENTS; i++) {
        if (studentDB[i].roll == roll && studentDB[i].pin == pin) {
          logAttendance(studentDB[i].roll, studentDB[i].name, "Manual Keypad", "KEYPAD");
          found = true;
          break;
        }
      }
      if (!found) {
        Serial2.println("FAIL:Invalid PIN/Roll");
        updateOled("Manual Entry Failed");
        Serial.println("[ERROR] Manual Entry Failed: " + roll);
      }
    }
  }

  // 3. Listen for Commands from Python Desktop App via USB Serial
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.startsWith("CMD:TRIGGER:")) {
      int c1 = cmd.indexOf(':', 12);
      String name = cmd.substring(12, c1);
      String roll = cmd.substring(c1 + 1);
      logAttendance(roll, name, "Desktop Trigger", "PC_TRIGGER");
    } else if (cmd == "CMD:CLEAR") {
      logCount = 0;
      lastLoggedName = "None";
      lastLoggedRoll = "----";
      updateOled("Logs Cleared");
      Serial.println("[STATUS] Logs cleared");
    } else if (cmd == "CMD:PING") {
      Serial.println("[PONG] ESP32 Ready");
    }
  }

  // 4. Heartbeat every 5 seconds
  if (millis() - lastHeartbeat > 5000) {
    lastHeartbeat = millis();
    Serial.println("[Heartbeat] Total Logs: " + String(logCount));
  }
}
