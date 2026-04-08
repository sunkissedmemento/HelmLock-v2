from controller.relay import RelayController
from controller.locker import Locker
from controller.sanitation import Sanitation
from controller.sensor import Sensor

relay = RelayController()

# Create objects per locker
lockers = {
    1: {
        "locker": Locker(relay, 1),
        "san": Sanitation(relay, 1),
        "sensor": Sensor(relay, 1)
    },
    2: {
        "locker": Locker(relay, 2),
        "san": Sanitation(relay, 2),
        "sensor": Sensor(relay, 2)
    },
    3: {
        "locker": Locker(relay, 3),
        "san": Sanitation(relay, 3),
        "sensor": Sensor(relay, 3)
    }
}

print("=== Locker Control Terminal ===")
print("Commands:")
print("locker <n> open")
print("locker <n> close")
print("locker <n> sanitize")
print("locker <n> temp")

while True:
    cmd = input(">> ").lower().strip()
    parts = cmd.split()

    if len(parts) < 3:
        print("Invalid command")
        continue

    if parts[0] != "locker":
        print("Use: locker <1-3> <action>")
        continue

    try:
        locker_id = int(parts[1])
        system = lockers[locker_id]
    except:
        print("Invalid locker number")
        continue

    action = parts[2]

    # 🔓 LOCK CONTROL
    if action == "open":
        system["locker"].open()

    elif action == "close":
        system["locker"].close()

    # 🧼 SANITATION
    elif action == "sanitize":
        system["san"].run_cycle()

    # 🌡 SENSOR
    elif action == "temp":
        data = system["sensor"].read()
        if data:
            temp, hum = data
            print(f"Locker {locker_id} → Temp: {temp}°C | Humidity: {hum}%")
        else:
            print("Sensor read failed")

    else:
        print("Unknown action")