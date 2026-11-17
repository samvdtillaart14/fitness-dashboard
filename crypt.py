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

ITER = 250_000  # moet gelijk zijn aan ITER in site/index.html


def _key(pw: str, salt: bytes) -> bytes:
    return PBKDF2HMAC(hashes.SHA256(), 32, salt, ITER).derive(pw.encode())


def encrypt(pw: str, data: bytes) -> str:
    salt, iv = os.urandom(16), os.urandom(12)
    ct = AESGCM(_key(pw, salt)).encrypt(iv, data, None)
    return json.dumps({k: base64.b64encode(v).decode() for k, v in {"salt": salt, "iv": iv, "ct": ct}.items()})


def decrypt(pw: str, text: str) -> bytes:
    d = {k: base64.b64decode(v) for k, v in json.loads(text).items()}
    return AESGCM(_key(pw, d["salt"])).decrypt(d["iv"], d["ct"], None)


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
