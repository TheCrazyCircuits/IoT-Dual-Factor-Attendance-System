#include <LiquidCrystal.h>
#include <Keypad.h>
#include <SoftwareSerial.h>

// 1. Confirmed Working LCD Pins: RS=12, E=11, D4=5, D5=4, D6=3, D7=2
LiquidCrystal lcd(12, 11, 5, 4, 3, 2);

// 2. 4x4 Keypad Setup
const byte ROWS = 4;
const byte COLS = 4;
char keys[ROWS][COLS] = {
  {'1','2','3','A'},
  {'4','5','6','B'},
  {'7','8','9','C'},
  {'*','0','#','D'}
};
byte rowPins[ROWS] = {A0, A1, A2, A3}; // Rows 1 to 4
byte colPins[COLS] = {6, 7, 8, 10};    // Columns 1 to 4
Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);

// 3. Buzzer Pin
const int BUZZER_PIN = 9;

// 4. SoftwareSerial to ESP32: RX = A4, TX = A5
SoftwareSerial espSerial(A4, A5);

// State Management
enum SystemState {
  IDLE_WAIT,
  WAIT_PIN_FOR_CARD,
  WAIT_ROLL_NO,
  WAIT_PIN_FOR_MANUAL
};
SystemState currentState = IDLE_WAIT;

String currentCardUID = "";
String currentRoll = "";
String enteredPin = "";
unsigned long stateTimeout = 0;
unsigned long lastHeartbeat = 0;

void beepSuccess() {
  tone(BUZZER_PIN, 2000, 100);
  delay(120);
  tone(BUZZER_PIN, 2500, 150);
}

void beepKey() {
  tone(BUZZER_PIN, 1800, 30);
}

void beepError() {
  tone(BUZZER_PIN, 400, 400);
}

void showIdleScreen() {
  currentState = IDLE_WAIT;
  currentCardUID = "";
  currentRoll = "";
  enteredPin = "";
  lcd.clear();
  delay(10);
  lcd.setCursor(0, 0);
  lcd.print("ATTENDANCE SYS");
  lcd.setCursor(0, 1);
  lcd.print("Tap Card or *");
}

void handleEspMessage(String msg) {
  Serial.println("[FROM ESP32] " + msg);

  if (msg.startsWith("CARD:")) {
    currentCardUID = msg.substring(5);
    currentState = WAIT_PIN_FOR_CARD;
    enteredPin = "";
    stateTimeout = millis() + 15000;

    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Card Detected!");
    lcd.setCursor(0, 1);
    lcd.print("Enter PIN: ");
  } else if (msg.startsWith("OK:")) {
    int firstColon = msg.indexOf(':', 3);
    String name = msg.substring(3, firstColon);
    String roll = msg.substring(firstColon + 1);

    beepSuccess();
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Welcome!");
    lcd.setCursor(0, 1);
    lcd.print(name.substring(0, 16));
    delay(2500);
    showIdleScreen();
  } else if (msg.startsWith("FAIL:")) {
    String reason = msg.substring(5);
    beepError();
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Access Denied");
    lcd.setCursor(0, 1);
    lcd.print(reason.substring(0, 16));
    delay(2000);
    showIdleScreen();
  }
}

void handleKeyPress(char key) {
  stateTimeout = millis() + 15000;
  Serial.print("[KEY PRESSED] '");
  Serial.print(key);
  Serial.println("'");

  if (currentState == IDLE_WAIT) {
    if (key == '*') {
      currentState = WAIT_ROLL_NO;
      currentRoll = "";
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("Manual Roll No:");
      lcd.setCursor(0, 1);
      lcd.print(">");
    }
  } else if (currentState == WAIT_ROLL_NO) {
    if (key == '#') {
      if (currentRoll.length() > 0) {
        currentState = WAIT_PIN_FOR_MANUAL;
        enteredPin = "";
        lcd.clear();
        lcd.setCursor(0, 0);
        lcd.print("Roll: " + currentRoll);
        lcd.setCursor(0, 1);
        lcd.print("Enter PIN: ");
      }
    } else if (key == 'D') {
      showIdleScreen();
    } else if (key >= '0' && key <= '9') {
      if (currentRoll.length() < 8) {
        currentRoll += key;
        lcd.setCursor(1, 1);
        lcd.print(currentRoll);
      }
    }
  } else if (currentState == WAIT_PIN_FOR_CARD || currentState == WAIT_PIN_FOR_MANUAL) {
    if (key == '#') {
      if (enteredPin.length() >= 4) {
        lcd.clear();
        lcd.setCursor(0, 0);
        lcd.print("Verifying...");
        
        if (currentState == WAIT_PIN_FOR_CARD) {
          espSerial.println("VERIFY_CARD:" + currentCardUID + ":" + enteredPin);
        } else {
          espSerial.println("VERIFY_ROLL:" + currentRoll + ":" + enteredPin);
        }
      }
    } else if (key == 'D') {
      showIdleScreen();
    } else if (key >= '0' && key <= '9') {
      if (enteredPin.length() < 4) {
        enteredPin += key;
        lcd.setCursor(11 + enteredPin.length() - 1, 1);
        lcd.print("*");
      }
    }
  }
}

void setup() {
  pinMode(BUZZER_PIN, OUTPUT);
  Serial.begin(9600);
  espSerial.begin(9600);

  Serial.println("\n==================================");
  Serial.println("  ATTENDANCE SYSTEM: READY       ");
  Serial.println("==================================");
  
  delay(150);
  lcd.begin(16, 2);
  delay(50);
  lcd.clear();
  delay(20);

  showIdleScreen();
  beepSuccess();
  Serial.println("System fully online.");
}

void loop() {
  // Check for commands from ESP32
  if (espSerial.available()) {
    String msg = espSerial.readStringUntil('\n');
    msg.trim();
    if (msg.length() > 0) {
      handleEspMessage(msg);
    }
  }

  // Keypad handling
  char key = keypad.getKey();
  if (key) {
    beepKey();
    handleKeyPress(key);
  }

  // Timeout reset to idle after 15 seconds of inactivity
  if (currentState != IDLE_WAIT && millis() > stateTimeout) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Time Expired");
    beepError();
    delay(1500);
    showIdleScreen();
  }

  // Heartbeat every 4 seconds
  if (millis() - lastHeartbeat > 4000) {
    lastHeartbeat = millis();
    Serial.println("[Uno Heartbeat] Ready");
  }
}
