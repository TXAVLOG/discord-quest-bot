import os
import zipfile
import hashlib
import struct
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization

KEY_FILE = os.path.join(os.path.dirname(__file__), "extension_key.pem")
ZIP_FILE = os.path.join(os.path.dirname(__file__), "extension.zip")
CRX_FILE = os.path.join(os.path.dirname(__file__), "extension.crx")
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "discord-token-extension"))

def pack_source_to_zip():
    """Tự động nén thư mục nguồn discord-token-extension thành extension.zip nếu thư mục nguồn tồn tại."""
    if os.path.exists(SRC_DIR) and os.path.isdir(SRC_DIR):
        try:
            with zipfile.ZipFile(ZIP_FILE, "w", zipfile.ZIP_DEFLATED) as z:
                for root, dirs, files in os.walk(SRC_DIR):
                    for file in files:
                        if file.endswith(".pem") or "_metadata" in root:
                            continue
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, SRC_DIR)
                        z.write(full_path, rel_path)
            print(f"Đã tự động nén source từ '{SRC_DIR}' vào '{ZIP_FILE}'")
        except Exception as e:
            print(f"Lỗi khi nén nguồn tiện ích: {e}")

def get_or_create_key():
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)
    else:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        with open(KEY_FILE, "wb") as f:
            f.write(pem)
        return key

def encode_varint(n):
    out = bytearray()
    while n >= 0x80:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n & 0x7F)
    return bytes(out)

def build_crx():
    # 1. Tự động nén mã nguồn extension mới nhất (nếu có)
    pack_source_to_zip()

    if not os.path.exists(ZIP_FILE):
        print(f"Error: {ZIP_FILE} not found.")
        return

    with open(ZIP_FILE, "rb") as f:
        zip_bytes = f.read()

    key = get_or_create_key()
    pub_key_der = key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    crx_id = hashlib.sha256(pub_key_der).digest()[:16]
    signed_header_data = b"\x0a\x10" + crx_id

    signed_payload = (
        b"CRX3 SignedData\x00"
        + struct.pack("<I", len(signed_header_data))
        + signed_header_data
        + zip_bytes
    )

    signature = key.sign(
        signed_payload,
        padding.PKCS1v15(),
        hashes.SHA256()
    )

    proof_bytes = (
        b"\x0a" + encode_varint(len(pub_key_der)) + pub_key_der +
        b"\x12" + encode_varint(len(signature)) + signature
    )

    header_bytes = (
        b"\x12" + encode_varint(len(proof_bytes)) + proof_bytes +
        encode_varint((10000 << 3) | 2) + encode_varint(len(signed_header_data)) + signed_header_data
    )

    crx3_data = (
        b"Cr24"
        + b"\x03\x00\x00\x00"
        + struct.pack("<I", len(header_bytes))
        + header_bytes
        + zip_bytes
    )

    with open(CRX_FILE, "wb") as f:
        f.write(crx3_data)

    print(f"Successfully generated valid CRX3 package: {CRX_FILE} ({len(crx3_data)} bytes)")

if __name__ == "__main__":
    build_crx()
