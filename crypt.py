"""Versleutelt/ontsleutelt een bestand met een wachtwoord uit een omgevingsvariabele.

Gebruik: python crypt.py enc|dec VARNAAM invoer uitvoer
Formaat (JSON): PBKDF2-SHA256 + AES-GCM, zo gekozen dat de browser (WebCrypto) het ook kan ontsleutelen.
"""

import base64
import json
import os
import sys

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Hoog, omdat een cijfercode weinig mogelijkheden heeft: maakt elke raadpoging duur.
# Wordt in het bestand opgeslagen, dus de browser en oudere bestanden lezen altijd de juiste waarde.
ITER = 1_000_000


def _key(pw: str, salt: bytes, iters: int) -> bytes:
    return PBKDF2HMAC(hashes.SHA256(), 32, salt, iters).derive(pw.encode())


def encrypt(pw: str, data: bytes) -> str:
    salt, iv = os.urandom(16), os.urandom(12)
    ct = AESGCM(_key(pw, salt, ITER)).encrypt(iv, data, None)
    out = {k: base64.b64encode(v).decode() for k, v in {"salt": salt, "iv": iv, "ct": ct}.items()}
    return json.dumps({**out, "iter": ITER})


def decrypt(pw: str, text: str) -> bytes:
    raw = json.loads(text)
    d = {k: base64.b64decode(raw[k]) for k in ("salt", "iv", "ct")}
    return AESGCM(_key(pw, d["salt"], raw.get("iter", 250_000))).decrypt(d["iv"], d["ct"], None)


if __name__ == "__main__":
    mode, var, src, dst = sys.argv[1:5]
    pw = os.environ[var]
    if not pw:
        sys.exit(f"{var} is leeg")
    with open(src, "rb") as f:
        raw = f.read()
    out = encrypt(pw, raw).encode() if mode == "enc" else decrypt(pw, raw.decode())
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(out)
