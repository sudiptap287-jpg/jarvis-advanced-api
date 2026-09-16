import hashlib
import zlib
import pickle

# This is the "Engine" you will add to your project
class PremiumEngine:
    def __init__(self, master_key="YZSJVVnwfceBusUO06XGHCrZMg2uMHoy19a7MDC4z9A="):
        self.key = hashlib.sha256(master_key.encode()).digest()

    def _xor_cipher(self, data: bytes) -> bytes:
        key_len = len(self.key)
        return bytes([b ^ self.key[i % key_len] for i, b in enumerate(data)])

    def pack_data(self, data_obj):
        """Premium: Pickle -> Compress -> Encrypt"""
        raw = pickle.dumps(data_obj)
        compressed = zlib.compress(raw, level=9)
        return self._xor_cipher(compressed)

    def unpack_data(self, encrypted_blob):
        """Premium: Decrypt -> Decompress -> Unpickle"""
        try:
            decrypted = self._xor_cipher(encrypted_blob)
            decompressed = zlib.decompress(decrypted)
            return pickle.loads(decompressed)
        except:
            return None # Wrong key or corrupted data