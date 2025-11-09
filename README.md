# ⚡ Advanced Bitcoin Keyspace Scanner (BIP44/49/84/86 + SQLite + Taproot)

This Python program is a **multi-process, fault-tolerant Bitcoin address scanner** that:
- Randomly generates private keys across a defined bit range  
- Derives all major Bitcoin address types (BIP44, BIP49, BIP84, BIP86)  
- Checks each generated address against a **local SQLite database** (`addresses111.db`)  
- Handles SQLite locks with automatic retries and exponential backoff  
- Logs any matching private keys to `JESTEMBOGATY123.txt`  

> ⚠️ **For research and educational purposes only.**  
> This tool demonstrates Bitcoin key/address generation, derivation paths, and database querying — **not brute-force feasibility**.

---

## 🚀 Key Features

✅ **Multiprocessing scanner** — runs multiple address search processes in parallel  
✅ **Bech32/Bech32m support** — implements both SegWit (BIP173) and Taproot (BIP350)  
✅ **Database lock recovery** — automatic retry with exponential backoff  
✅ **Real-time progress tracking** via a background thread  
✅ **BIP-compliant address generation**:
- **BIP44:** Legacy (`1...`)
- **BIP49:** P2SH-SegWit (`3...`)
- **BIP84:** Native SegWit (`bc1q...`)
- **BIP86:** Taproot (`bc1p...`)
✅ **Readable, color-coded terminal output**  
✅ **Memory usage tracking (via `psutil`)**

---

## 📂 File Overview

| File | Description |
|------|--------------|
| `main.py` | Main scanning script |
| `addresses111.db` | SQLite database containing known Bitcoin addresses |
| `JESTEMBOGATY123.txt` | Output log file with found private keys |
| `bech32` module | Used for encoding SegWit & Taproot addresses |

---

## ⚙️ Database Setup

The scanner connects to `addresses111.db` (read-only mode).  
It must contain a single table with a list of Bitcoin addresses:

```sql
CREATE TABLE addresses (
    address TEXT PRIMARY KEY
);
Insert target addresses:

INSERT INTO addresses (address) VALUES ('1BoatSLRHtKNngkdXEeobR76b53LETtpyT');
INSERT INTO addresses (address) VALUES ('bc1q4nyq7kr4nwq6zw35pg0zl0k9jmdmtmadlfvqhr');

🧩 How It Works

Random key generation

Each process continuously generates random 256-bit private keys in the selected range.

Address derivation

The script converts every private key into public keys and all major Bitcoin address formats:

BIP44 → Legacy

BIP49 → P2SH-P2WPKH

BIP84 → Native SegWit (bech32)

BIP86 → Taproot (bech32m)

SQLite database lookup

Each generated address is checked against a local database.

If a match is found, the corresponding private key and all derived addresses are written to the output file.

Error handling

SQLite lock errors are automatically retried with exponential backoff.

Any database or runtime exceptions are logged without stopping other processes.

Progress display

A separate thread prints the total number of keys checked in real time.

📜 Example Output
Podaj zakres do BTC Puzzle (np. 67–70):
Od bitu: 67
Do bitu: 70
🔎 Szukam adresów w zakresie 147573952589676412928–1180591620717411303424…
[Proces 0] Zakres: 147573952589676412928 → 294147905179352825856
[Proces 1] Zakres: 294147905179352825856 → 441721857769029238784
...

[Proces 2] 🔍 Sample BIP44: 1FZbgi29cpjq2GjdwV8eyHuJJnkLtktZc5
[Proces 3] 🔄 500,000 keys checked... RAM: 96 MB

💰 ZNALEZIONO ADRES!
PrivKey (hex): 0x21a9b77ccf49ee9b1...
WIF compressed:   KxzY5jL8Z8Z3xN6...
WIF uncompressed: 5Jab9RqF5W...
------------------------------------------------------------

🧠 Technical Details
Component	Description
jump_generator()	Generates random integers in the given bit range
private_key_to_wif()	Converts private key to Wallet Import Format
private_key_to_addresses()	Derives all BIP44/49/84/86 addresses from a private key
address_exists_in_db()	Safe SQLite lookup with retries and backoff
search_process()	Main worker function (runs in separate processes)
print_counter()	Threaded real-time progress display
bech32_encode()	Custom implementation supporting bech32 and bech32m
⚙️ Configuration
Parameter	Default	Description
OUTPUT_FILE	JESTEMBOGATY123.txt	Output file for found keys
ADDRESS_DB	addresses111.db	SQLite database file
PROCESSES	5	Number of concurrent search processes
DB_RETRIES	5	Number of retries on SQLite lock
DB_BACKOFF_BASE	0.2s	Base time for exponential backoff
🧮 Multiprocessing Architecture
[Main Thread]
   ├── Counter thread ─► prints total keys checked
   └── Spawned Processes (5 total)
        ├── Process 0 → range A₀–B₀
        ├── Process 1 → range A₁–B₁
        ├── Process 2 → range A₂–B₂
        ├── Process 3 → range A₃–B₃
        └── Process 4 → range A₄–B₄


Each process:

Generates random keys in its own numeric range

Derives multiple address types

Checks SQLite for matches

Writes successful hits to the output log

🧰 Installation
1️⃣ Install dependencies
pip install ecdsa bech32 psutil base58

2️⃣ Create the database
sqlite3 addresses111.db "CREATE TABLE addresses(address TEXT PRIMARY KEY);"

3️⃣ Add Bitcoin addresses
sqlite3 addresses111.db "INSERT INTO addresses VALUES('1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa');"

4️⃣ Run the scanner
python3 main.py

⚠️ Ethical Use & Disclaimer

This tool is for cryptographic education and blockchain research only.
It is not designed or suitable for recovering private keys of third-party wallets.
The Bitcoin keyspace (2²⁵⁶) is astronomically large — brute-force attacks are computationally impossible.

Use responsibly, for:

Academic demonstrations

Testing local database lookups

Understanding Bitcoin address derivations

BTC donation address: bc1q4nyq7kr4nwq6zw35pg0zl0k9jmdmtmadlfvqhr
