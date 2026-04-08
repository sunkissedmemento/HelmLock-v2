#include <DHT.h>

// ================= RELAY CONFIG =================
#define RELAY_ON LOW
#define RELAY_OFF HIGH

// {LOCK, UV, MIST, OZONE, FAN}
int lockerRelays[3][5] = {
  {2, 3, 4, 5, 6},       // Locker 1
  {7, 8, 9, 10, 11},     // Locker 2
  {12, 13, 22, 23, 24}   // Locker 3
};

#define LOCK 0
#define UV 1
#define MIST 2
#define OZONE 3
#define FAN 4

// ================= DHT22 =================
#define DHTTYPE DHT22

DHT dht[3] = {
  DHT(30, DHTTYPE),
  DHT(31, DHTTYPE),
  DHT(32, DHTTYPE)
};

// ================= SERIAL =================
String input = "";

// ================= SETUP =================
void setup() {
  Serial.begin(9600);

  // Init relays
  for (int i = 0; i < 3; i++) {
    for (int j = 0; j < 5; j++) {
      pinMode(lockerRelays[i][j], OUTPUT);
      digitalWrite(lockerRelays[i][j], RELAY_OFF);
    }
  }

  // Init sensors
  for (int i = 0; i < 3; i++) {
    dht[i].begin();
  }
}

// ================= LOOP =================
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

// ================= COMMAND HANDLER =================
void handleCommand(String cmd) {
  cmd.trim();

  // Expected: L1_UV_ON
  if (cmd.length() < 3) return;

  int locker = cmd.charAt(1) - '1';
  if (locker < 0 || locker > 2) return;

  // ===== SENSOR REQUEST =====
  if (cmd.endsWith("READ_DHT")) {
    sendDHT(locker);
    return;
  }

  // ===== ALL OFF =====
  if (cmd.endsWith("ALL_OFF")) {
    for (int i = 0; i < 5; i++) {
      digitalWrite(lockerRelays[locker][i], RELAY_OFF);
    }
    return;
  }

  // ===== RELAY CONTROL =====
  bool state = cmd.endsWith("_ON");

  if (cmd.indexOf("LOCK") > 0) {
    digitalWrite(lockerRelays[locker][LOCK], state ? RELAY_ON : RELAY_OFF);
  }
  else if (cmd.indexOf("UV") > 0) {
    digitalWrite(lockerRelays[locker][UV], state ? RELAY_ON : RELAY_OFF);
  }
  else if (cmd.indexOf("MIST") > 0) {
    digitalWrite(lockerRelays[locker][MIST], state ? RELAY_ON : RELAY_OFF);
  }
  else if (cmd.indexOf("OZONE") > 0) {
    digitalWrite(lockerRelays[locker][OZONE], state ? RELAY_ON : RELAY_OFF);
  }
  else if (cmd.indexOf("FAN") > 0) {
    digitalWrite(lockerRelays[locker][FAN], state ? RELAY_ON : RELAY_OFF);
  }
}

// ================= DHT SEND =================
void sendDHT(int locker) {
  float temp = dht[locker].readTemperature();
  float hum  = dht[locker].readHumidity();

  if (isnan(temp) || isnan(hum)) {
    Serial.println("ERR_DHT");
    return;
  }

  Serial.print("L");
  Serial.print(locker + 1);
  Serial.print("_TEMP:");
  Serial.print(temp);
  Serial.print("_HUM:");
  Serial.println(hum);
}