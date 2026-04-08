class RelayController:
    def __init__(self, port='/dev/ttyUSB0'):
        import serial, time
        self.ser = serial.Serial(port, 9600, timeout=1)
        time.sleep(2)

    def send(self, cmd):
        self.ser.write((cmd + "\n").encode())