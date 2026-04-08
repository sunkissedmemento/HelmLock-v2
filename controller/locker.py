class Locker:
    def __init__(self, relay, locker_id):
        self.relay = relay
        self.id = locker_id

    def open(self):
        self.relay.send(f"L{self.id}_LOCK_ON")

    def close(self):
        self.relay.send(f"L{self.id}_LOCK_OFF")