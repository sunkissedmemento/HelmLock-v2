#include <Arduino.h>

// =========================================================
// CONFIG
// =========================================================
#define BAUD_RATE 115200
#define MAX_LOCKERS 6

// ---- Pins (EDIT THESE BASED ON YOUR WIRING) ----
int LOCK_PINS[MAX_LOCKERS]   = {22, 23, 24, 25, 26, 27};
int REED_PINS[MAX_LOCKERS]   = {30, 31, 32, 33, 34, 35};

// Coin acceptor
#define COIN_PIN 2

// =========================================================
// STATE VARIABLES
// =========================================================
volatile int coinPulseCount = 0;

// =========================================================
// INTERRUPT (COIN ACCEPTOR)
// =========================================================
void coinISR() {
  coinPulseCount++;
}

// =========================================================
// SETUP
// =========================================================
void setup() {
  Serial.begin(BAUD_RATE);

  for (int i = 0; i < MAX_LOCKERS; i++) {
    pinMode(LOCK_PINS[i], OUTPUT);
    pinMode(REED_PINS[i], INPUT_PULLUP);

    digitalWrite(LOCK_PINS[i], HIGH); // LOCKED by default
  }

  pinMode(COIN_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(COIN_PIN), coinISR, FALLING);

  Serial.println("[SYSTEM] READY");
}

// =========================================================
// UTILITIES
// =========================================================
void lockDoor(int n) {
  digitalWrite(LOCK_PINS[n], HIGH);
}

void unlockDoor(int n) {
  digitalWrite(LOCK_PINS[n], LOW);
}

bool isDoorOpen(int n) {
  return digitalRead(REED_PINS[n]) == LOW;
}

// =========================================================
// SERIAL COMMAND HANDLER
// =========================================================
String input = "";

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      handleCommand(input);
      input = "";
    } else {
      input += c;
    }
  }
}

// =========================================================
// COMMAND PARSER
// =========================================================
void handleCommand(String cmd) {
  cmd.trim();

  // ---------------- STORE HELMET ----------------
  if (cmd.startsWith("locker:")) {
    int n = cmd.substring(7).toInt();
    storeHelmet(n);
  }

  // ---------------- CLAIM ----------------
  else if (cmd.startsWith("claim:")) {
    int n = cmd.substring(6).toInt();
    claimHelmet(n);
  }

  // ---------------- SANITISE ----------------
  else if (cmd.startsWith("sanitise:")) {
    int n = cmd.substring(10).toInt();
    sanitise(n);
  }

  // ---------------- DOOR LOCK ----------------
  else if (cmd.startsWith("doorlock:")) {
    int n = cmd.substring(9).toInt();
    lockDoor(n);
    Serial.println("DOORLOCK-" + String(n));
  }

  // ---------------- DOOR UNLOCK ----------------
  else if (cmd.startsWith("doorunlock:")) {
    int n = cmd.substring(11).toInt();
    unlockDoor(n);
    Serial.println("DOORUNLOCK-" + String(n));
  }

  // ---------------- DOOR STATUS ----------------
  else if (cmd.startsWith("doorstatus:")) {
    int n = cmd.substring(11).toInt();
    if (isDoorOpen(n)) {
      Serial.println("DOORSTATUS-" + String(n) + "-OPEN");
    } else {
      Serial.println("DOORSTATUS-" + String(n) + "-CLOSED");
    }
  }

  // ---------------- NFC READ (SIMULATED) ----------------
  else if (cmd == "nfcread") {
    delay(2000); // simulate tap delay
    Serial.println("NFCREAD-123ABC456");
  }

  // ---------------- COIN PAYMENT ----------------
  else if (cmd.startsWith("coinpayment:")) {
    int cost = cmd.substring(12).toInt();
    handleCoinPayment(cost);
  }
}

// =========================================================
// STORE FLOW
// =========================================================
void storeHelmet(int n) {
  unlockDoor(n);

  unsigned long start = millis();

  // Wait for door to open and close
  while (millis() - start < 30000) {
    if (isDoorOpen(n)) {
      // wait until closed again
      while (isDoorOpen(n));
      lockDoor(n);
      sanitise(n);

      Serial.println("STOREHELMET-DONE-" + String(n));
      return;
    }
  }
}

// =========================================================
// CLAIM FLOW
// =========================================================
void claimHelmet(int n) {
  unlockDoor(n);

  unsigned long start = millis();

  while (millis() - start < 20000) {
    if (isDoorOpen(n)) {
      while (isDoorOpen(n));
      lockDoor(n);

      Serial.println("CLAIM-DONE-" + String(n));
      return;
    }
  }
}

// =========================================================
// SANITISE (SIMULATED)
// =========================================================
void sanitise(int n) {
  delay(3000); // simulate UV / spray
  Serial.println("SANITISE-DONE-" + String(n));
}

// =========================================================
// COIN PAYMENT HANDLER
// =========================================================
void handleCoinPayment(int cost) {
  coinPulseCount = 0;
  int total = 0;

  unsigned long start = millis();

  while (millis() - start < 120000) {
    if (coinPulseCount > 0) {
      total += coinPulseCount; // 1 pulse = ₱1 (adjust if needed)
      coinPulseCount = 0;

      Serial.println("TOTAL-" + String(total));
    }

    if (total >= cost) {
      Serial.println("COINPAYMENT-SUCCESS");
      return;
    }
  }
}