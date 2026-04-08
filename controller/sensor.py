import time

class Sensor:
    def __init__(self, relay, locker_id):
        self.relay = relay
        self.id = locker_id

    def read(self):
        """
        Requests DHT22 data from Arduino
        Returns: (temperature, humidity) or None
        """
        cmd = f"L{self.id}_READ_DHT"
        self.relay.send(cmd)

        # wait for Arduino response
        timeout = time.time() + 2  # 2 sec timeout

        while time.time() < timeout:
            if self.relay.ser.in_waiting:
                line = self.relay.ser.readline().decode().strip()

                if line.startswith(f"L{self.id}_TEMP"):
                    return self._parse(line)

        return None

    def _parse(self, line):
        """
        Example:
        L1_TEMP:28.5_HUM:65.2
        """
        try:
            parts = line.split("_")
            temp = float(parts[1].split(":")[1])
            hum = float(parts[2].split(":")[1])
            return temp, hum
        except:
            return None