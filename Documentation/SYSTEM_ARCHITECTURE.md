# 🏛️ System Architecture & Protocol Specification

## 1. System Block Diagram

```mermaid
flowchart TD
    subgraph UserInterface["User Physical Interface"]
        Card["RFID Card / Keyfob\n(13.56 MHz Mifare)"]
        KP["4x4 Matrix Keypad\n(Roll & PIN Entry)"]
        LCD["16x2 Parallel LCD\n(User Prompts & Greetings)"]
        BUZZ["Active Buzzer\n(Audio Confirmation)"]
    end

    subgraph Processing["Distributed Embedded Core"]
        ESP32["ESP32 DevKit Core\n(RFID Reader + Database Matching)"]
        UNO["Arduino Uno R3\n(I/O Controller + Keypad Scanner)"]
    end

    subgraph Host["Host PC Layer"]
        App["Python Desktop GUI\n(CustomTkinter Dashboard)"]
        CSV["attendance_report.csv\n(Exported Records)"]
    end

    Card -->|RFID RF Field| ESP32
    KP -->|Row/Col Scanning| UNO
    UNO -->|4-Bit Nibbles| LCD
    UNO -->|PWM Frequencies| BUZZ

    UNO <-->|Serial2 Bridge\n(9600 Baud + 1kΩ Resistor)| ESP32
    ESP32 <-->|USB Serial\n(115200 Baud JSON Packets)| App
    App -->|Export| CSV
```

---

## 2. Distributed Responsibilities

| Subsystem | Responsibilities |
|---|---|
| **ESP32** | 1. Drives RC522 SPI bus with boosted 48dB antenna gain.<br>2. Verifies student profiles against in-memory database.<br>3. Streams live JSON event packets to the Python Desktop App.<br>4. Emits serial `OK:<Name>:<Roll>` commands to Arduino Uno. |
| **Arduino Uno** | 1. Scans 4x4 keypad matrix for user keypresses and debounce.<br>2. Drives 16x2 character LCD via 4-bit parallel bus.<br>3. Generates audio confirmation chirps (`tone()`) on the buzzer.<br>4. Maintains interactive state machine (Idle, PIN Entry, Manual Roll). |
| **Python GUI App** | 1. Maintains asynchronous serial connection with ESP32.<br>2. Dynamically populates live attendance table on host PC.<br>3. Computes attendee statistics.<br>4. Provides one-click CSV report export. |

---

## 3. Inter-Board Serial Protocol (Uno ⇄ ESP32)

* **Baud Rate:** `9600`
* **Format:** ASCII strings terminated by newline `\n`

| Command | Sender | Receiver | Description |
|---|:---:|:---:|---|
| `OK:<Name>:<Roll>` | ESP32 | Uno | Informs Uno of successful attendance. Uno beeps buzzer and displays "Welcome! <Name>". |
| `FAIL:<Reason>` | ESP32 | Uno | Informs Uno of rejected access. Uno sounds error buzzer. |
| `CARD:<UID>` | ESP32 | Uno | Prompts Uno to switch to PIN verification for the scanned card. |
| `VERIFY_ROLL:<Roll>:<PIN>`| Uno | ESP32 | Uno forwards user-entered Roll No & PIN to ESP32 for validation. |

---

## 4. Host PC Serial Protocol (ESP32 ⇄ Python App)

* **Baud Rate:** `115200`
* **Format:** JSON strings prefixed by `[DATA]`

```json
[DATA] {
  "name": "John",
  "roll": "101",
  "method": "RFID Direct",
  "uid": "F30AB12C",
  "count": 1
}
```

### Supported PC Commands to Hardware:
* `CMD:TRIGGER:<Name>:<Roll>` ➔ Forces an attendance log on ESP32 and updates Uno LCD/Buzzer.
* `CMD:CLEAR` ➔ Resets internal log counters and status variables.
* `CMD:PING` ➔ ESP32 replies `[PONG] ESP32 Ready`.
