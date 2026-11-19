# 🛠️ Hardware & Firmware Troubleshooting Guide

This guide documents the real-world hardware fixes discovered and verified during system development.

---

## 1. 16x2 LCD Issues

### Symptom A: The LCD screen is completely blank / no pixels visible
* **Root Cause:** Contrast Pin 3 (V0) voltage is too high.
  * An HD44780 LCD requires $V_0 \le 0.8\text{V}$ (near 0V) for characters to be visible.
  * If Pin 3 is floating or connected to 5V, contrast is 0% (pixels are 100% transparent).
  * Using a plain 10kΩ fixed resistor to GND leaves $V_0$ at ~2.4V (still too high).
* **The Fix:**
  * Use a **10kΩ potentiometer** with outer legs on 5V and GND, and the wiper pin connected to Pin 3 (V0). Rotate the knob until text appears sharp.
  * Or connect **LCD Pin 3 directly to Arduino GND with a jumper wire** for guaranteed 100% contrast.

---

### Symptom B: The LCD shows 1 row of solid black blocks (`████████`)
* **Root Cause:** The LCD has power and contrast, but is **stuck in uninitialized 8-bit default mode**.
* **Checkpoints:**
  1. **Pin 5 (RW) MUST be grounded:** If RW is floating or connected to 5V, the LCD is locked in "Read Mode" and rejects all commands.
  2. **Data Pin Order:** In 4-bit mode, pins are wired in descending order:
     * LCD **Pin 11 (D4)** ➔ Arduino **Pin 5**
     * LCD **Pin 12 (D5)** ➔ Arduino **Pin 4**
     * LCD **Pin 13 (D6)** ➔ Arduino **Pin 3**
     * LCD **Pin 14 (D7)** ➔ Arduino **Pin 2**
     *(If wired in reverse order 2, 3, 4, 5, the 4-bit initialization nibble 0x02 becomes 0x04, failing initialization).*
  3. **Header Pins Soldering:** If the 16-pin male header is pushed into the LCD PCB holes loosely without solder, intermittent data lines prevent commands from passing through.

---

### Symptom C: The LCD displays garbage characters (`?___?`) after a reset
* **Root Cause:** 4-bit bus nibble desynchronization.
  * In 4-bit mode, every byte requires two 4-bit nibbles (High then Low).
  * If the Arduino resets via DTR/USB while the LCD remains powered at 5V, the LCD retains its previous state. The first nibble is interpreted as the second half of an old command, throwing every character 4 bits out of phase.
* **The Fix:**
  * Perform a **cold reboot**: Unplug the Arduino USB cable for 3 seconds to discharge the LCD controller, then plug it back in.

---

## 2. RC522 RFID Card Detection Issues

### Symptom: RFID cards are not detected when swiped
* **Root Cause 1: Weak Antenna Gain on 3.3V Clone Boards (Firmware 0xB2)**
  * Chinese clone RC522 modules default to `RxGain_33dB`. At 3.3V, the induced magnetic field is too weak to energize passive 13.56MHz cards through air.
  * **The Fix:** In code, set maximum receiver gain (48dB):
    ```cpp
    mfrc522.PCD_SetAntennaGain(mfrc522.RxGain_max);
    mfrc522.PCD_AntennaOff();
    delay(10);
    mfrc522.PCD_AntennaOn();
    ```
* **Root Cause 2: Cards in HALT state ignore `RequestA`**
  * When a card is read and halted, ISO 14443-3 specifies that it will only respond to `WakeupA` (`WUPA`), not `RequestA` (`REQA`).
  * **The Fix:** Poll both functions in the scanning loop:
    ```cpp
    bool cardDetected = mfrc522.PICC_IsNewCardPresent();
    if (!cardDetected) {
      byte bufferATQA[2];
      byte bufferSize = sizeof(bufferATQA);
      cardDetected = (mfrc522.PICC_WakeupA(bufferATQA, &bufferSize) == MFRC522::STATUS_OK);
    }
    ```

---

## 3. Breadboard Power Splits
* **Standard 830-point breadboards** have a physical separation break in the middle of the positive (+) and negative (-) rails.
* If the Arduino 5V/GND are plugged into the left side of the breadboard, the right side has **0 volts** unless jumper wires bridge the middle gap.
