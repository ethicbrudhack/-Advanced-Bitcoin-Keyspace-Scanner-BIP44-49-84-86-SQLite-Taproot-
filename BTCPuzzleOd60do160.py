import os
import sys
import hashlib
import base58
import random
import sqlite3
import multiprocessing
import threading
import time
import ecdsa
import psutil
import traceback
from bech32 import convertbits

# -----------------------------------------------------------
#                 USTAWIENIA GLOBALNE
# -----------------------------------------------------------

OUTPUT_FILE = "JESTEMBOGATY123.txt"
ADDRESS_DB = "addresses111.db"
PROCESSES = 5
DB_RETRIES = 5            # liczba ponowień przy blokadzie
DB_BACKOFF_BASE = 0.2     # sekundy (exponential backoff)

# -----------------------------------------------------------
#            BECH32 / BECH32M IMPLEMENTACJA (BIP350)
# -----------------------------------------------------------

CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"

def bech32_polymod(values):
    GENERATORS = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3]
    chk = 1
    for v in values:
        top = chk >> 25
        chk = ((chk & 0x1ffffff) << 5) ^ v
        for i in range(5):
            if (top >> i) & 1:
                chk ^= GENERATORS[i]
    return chk

def bech32_hrp_expand(hrp):
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]

def bech32_create_checksum(hrp, data, spec='bech32'):
    values = bech32_hrp_expand(hrp) + data
    const = 1 if spec == 'bech32' else 0x2bc830a3
    polymod = bech32_polymod(values + [0, 0, 0, 0, 0, 0]) ^ const
    return [(polymod >> (5 * (5 - i))) & 31 for i in range(6)]

def bech32_encode(hrp, data, spec='bech32'):
    combined = data + bech32_create_checksum(hrp, data, spec)
    return hrp + '1' + ''.join([CHARSET[d] for d in combined])

# -----------------------------------------------------------
#           GENERATOR KLUCZY I KONWERSJE ADRESÓW
# -----------------------------------------------------------

def jump_generator(start, stop):
    """Bez końca losuje prywatne klucze z przedziału [start, stop)."""
    while True:
        yield random.randrange(start, stop)

def private_key_to_wif(priv_key, compressed=True):
    pk_bytes = priv_key.to_bytes(32, 'big')
    if compressed:
        extended = b'\x80' + pk_bytes + b'\x01'
    else:
        extended = b'\x80' + pk_bytes
    checksum = hashlib.sha256(hashlib.sha256(extended).digest()).digest()[:4]
    return base58.b58encode(extended + checksum).decode()

def private_key_to_addresses(priv_key):
    sk = ecdsa.SigningKey.from_secret_exponent(priv_key, curve=ecdsa.SECP256k1)
    vk = sk.verifying_key
    vk_bytes = vk.to_string()  # 64 bajty: X||Y

    # PUBKEY KOMPRESOWANY / NIEKOMPRESOWANY
    pub_comp = b'\x02' + vk_bytes[:32] if vk_bytes[63] % 2 == 0 else b'\x03' + vk_bytes[:32]
    pub_uncomp = b'\x04' + vk_bytes

    # HASH160
    h160_comp = hashlib.new('ripemd160', hashlib.sha256(pub_comp).digest()).digest()
    h160_uncomp = hashlib.new('ripemd160', hashlib.sha256(pub_uncomp).digest()).digest()

    # BIP44 (P2PKH)
    addr44_comp = base58.b58encode_check(b'\x00' + h160_comp).decode()
    addr44_uncomp = base58.b58encode_check(b'\x00' + h160_uncomp).decode()

    # BIP49 (P2SH-P2WPKH)
    redeem_comp = b'\x00\x14' + h160_comp
    rs_hash_comp = hashlib.new('ripemd160', hashlib.sha256(redeem_comp).digest()).digest()
    addr49_comp = base58.b58encode_check(b'\x05' + rs_hash_comp).decode()

    redeem_uncomp = b'\x00\x14' + h160_uncomp
    rs_hash_uncomp = hashlib.new('ripemd160', hashlib.sha256(redeem_uncomp).digest()).digest()
    addr49_uncomp = base58.b58encode_check(b'\x05' + rs_hash_uncomp).decode()

    # BIP84 (bech32)
    segwit_data_comp = [0] + convertbits(h160_comp, 8, 5, True)
    addr84_comp = bech32_encode("bc", segwit_data_comp, spec='bech32')
    segwit_data_uncomp = [0] + convertbits(h160_uncomp, 8, 5, True)
    addr84_uncomp = bech32_encode("bc", segwit_data_uncomp, spec='bech32')

    # BIP86 (Taproot, bech32m)
    xonly = vk_bytes[:32]
    segwit_data_86 = [1] + convertbits(xonly, 8, 5, True)
    addr86 = bech32_encode("bc", segwit_data_86, spec='bech32m')

    return {
        "compressed":   (addr44_comp, addr49_comp, addr84_comp, addr86),
        "uncompressed": (addr44_uncomp, addr49_uncomp, addr84_uncomp, addr86),
        "wif": {
            "compressed":   private_key_to_wif(priv_key, True),
            "uncompressed": private_key_to_wif(priv_key, False)
        }
    }

# -----------------------------------------------------------
#           FUNKCJE DO BAZY DANYCH (READ-ONLY + RETRY)
# -----------------------------------------------------------

def address_exists_in_db(conn, address, pid=None):
    """Sprawdza, czy adres istnieje w bazie (retry + komunikaty)."""
    attempt = 0
    while True:
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM addresses WHERE address = ?", (address,))
            return cur.fetchone() is not None

        except sqlite3.OperationalError as exc:
            msg = str(exc).lower()
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            who = f"Proces {pid} - " if pid is not None else ""

            if "locked" in msg:
                if attempt < DB_RETRIES:
                    wait = DB_BACKOFF_BASE * (2 ** attempt)
                    print(f"⚠️] {stamp} {who}Baza zablokowana (próba {attempt+1}/{DB_RETRIES+1}) – czekam {wait:.2f}s", flush=True)
                    time.sleep(wait)
                    attempt += 1
                    continue
                else:
                    print(f"[❌] {stamp} {who}Baza nadal zablokowana po {DB_RETRIES+1} próbach – pomijam.", flush=True)
                    return False
            else:
                print(f"[❌] {stamp} {who}Błąd SQLite: {exc}", flush=True)
                traceback.print_exc()
                return False

        except Exception as exc:
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            who = f"Proces {pid} - " if pid is not None else ""
            print(f"[❌] {stamp} {who}Inny błąd bazy: {exc}", flush=True)
            traceback.print_exc()
            return False

# -----------------------------------------------------------
#               WORKER (PROCES POSZUKIWACZ)
# -----------------------------------------------------------

def search_process(a, b, counter, process_id, lock):
    print(f"[Proces {process_id}] 🔥 Startuję! PID={os.getpid()}")
    try:
        db_uri = f"file:{ADDRESS_DB}?mode=ro"
        conn = sqlite3.connect(db_uri, uri=True, timeout=5, check_same_thread=False)
    except Exception as exc:
        print(f"[❌] Proces {process_id} - nie mogę otworzyć DB: {exc}", flush=True)
        return

    proc = psutil.Process(os.getpid())
    key_gen = jump_generator(a, b)
    local_counter = 0

    while True:
        priv_key = next(key_gen)
        addresses = private_key_to_addresses(priv_key)
        found = False

        # sprawdź każdy adres
        for addr_type in addresses.values():
            if isinstance(addr_type, tuple):
                for addr in addr_type:
                    if address_exists_in_db(conn, addr, pid=process_id):
                        found = True
                        break
            if found:
                break

        if found:
            print(f"\033[92m\n💰 ZNALEZIONO ADRES!\033[0m")
            print(f"\033[92mPrivKey (hex): {hex(priv_key)}\033[0m")
            with lock:
                with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                    f.write("✅ HIT!\n")
                    f.write(f"PrivKey (hex): {hex(priv_key)}\n")
                    f.write(f"WIF compressed:   {addresses['wif']['compressed']}\n")
                    f.write(f"WIF uncompressed: {addresses['wif']['uncompressed']}\n")
                    f.write("------------------------------------------------------------\n\n")

        if local_counter % 10_000 == 0:
            print(f"[{process_id}] 🔍 Sample BIP44: {addresses['compressed'][0]}")

        with lock:
            counter.value += 1
        local_counter += 1

        if local_counter % 100_000 == 0:
            mem_mb = proc.memory_info().rss // (1024 ** 2)
            print(f"[{process_id}] 🔄 {counter.value:,} kluczy sprawdzonych... RAM: {mem_mb} MB")

    conn.close()

# -----------------------------------------------------------
#             WĄTEK WYŚWIETLAJĄCY POSTĘP
# -----------------------------------------------------------

def print_counter(counter, lock):
    while True:
        with lock:
            print(f"⏱️ Total Checked: {counter.value:,}", end='\r')
        time.sleep(1)

# -----------------------------------------------------------
#                     GŁÓWNY PROGRAM
# -----------------------------------------------------------

if __name__ == "__main__":
    print("Podaj zakres do BTC Puzzle (np. 67–70):")
    start_bit = int(input("Od bitu: "))
    end_bit = int(input("Do bitu: "))
    a = 2 ** start_bit
    b = 2 ** end_bit
    print(f"🔎 Szukam adresów w zakresie {a}–{b}…")

    manager = multiprocessing.Manager()
    counter = multiprocessing.Value('i', 0)
    lock = multiprocessing.Lock()
    processes = []

    thread = threading.Thread(target=print_counter, args=(counter, lock))
    thread.daemon = True
    thread.start()

    step = (b - a) // PROCESSES

    for i in range(PROCESSES):
        a_i = a + i * step
        b_i = a + (i + 1) * step if i < PROCESSES - 1 else b
        print(f"[Proces {i}] Zakres: {a_i} → {b_i}")
        p = multiprocessing.Process(target=search_process, args=(a_i, b_i, counter, i, lock))
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

    print(f"\n✅ Gotowe. Sprawdzono: {counter.value:,} kluczy.")
