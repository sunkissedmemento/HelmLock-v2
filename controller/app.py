import serial
import time
import threading

SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE = 115200
TIMEOUT = 10

ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
time.sleep(2)

buffer = []
lock = threading.Lock()

# ================= READER =================
def reader():
    while True:
        try:
            line = ser.readline().decode().strip()
            if line:
                print("[MEGA]", line)
                with lock:
                    buffer.append(line)
        except:
            pass

threading.Thread(target=reader, daemon=True).start()

# ================= SEND =================
def send(cmd):
    print("[RPI → MEGA]", cmd)
    ser.write((cmd + "\n").encode())

# ================= WAIT =================
def wait(key, timeout=TIMEOUT):
    start = time.time()
    while time.time() - start < timeout:
        with lock:
            for b in buffer:
                if key in b:
                    buffer.clear()
                    return True
        time.sleep(0.1)
    return False

def clear():
    with lock:
        buffer.clear()

# ================= NFC =================
def nfc_read():
    clear()
    send("nfcread")

    start = time.time()
    while time.time() - start < TIMEOUT:
        with lock:
            for b in buffer:
                if b.startswith("NFCREAD-"):
                    buffer.clear()
                    return b.split("-",1)[1]
        time.sleep(0.1)
    return ""

# ================= STORE =================
def store(locker):
    clear()
    send(f"store:{locker}")
    return wait(f"STORE-DONE-{locker}")

# ================= CLAIM =================
def claim(locker):
    clear()
    send(f"claim:{locker}")
    return wait(f"CLAIM-DONE-{locker}")

# ================= SANITISE =================
def sanitise(locker):
    clear()
    send(f"sanitise:{locker}")
    return wait(f"SANITISE-DONE-{locker}")

# ================= PAYMENT =================
def payment(cost):
    clear()
    send(f"coinpayment:{cost}")
    return wait("COINPAYMENT-SUCCESS", timeout=120)

# ================= FLOW =================
def full_flow(locker, cost):
    print("\n--- SESSION START ---")

    uid = nfc_read()
    if not uid:
        print("No NFC")
        return

    print("UID:", uid)

    if not payment(cost):
        print("Payment failed")
        return

    print("Paid")

    if not store(locker):
        print("Store failed")
        return

    print("Stored + Sanitised")

    input("Press ENTER to claim...")

    if not claim(locker):
        print("Claim failed")
        return

    print("Done")

# ================= CLI =================
while True:
    cmd = input(">> ")

    if cmd == "exit":
        break

    elif cmd.startswith("flow"):
        _, locker, cost = cmd.split()
        full_flow(int(locker), int(cost))

    elif cmd == "nfc":
        print(nfc_read())