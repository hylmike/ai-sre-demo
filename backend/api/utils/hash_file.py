import hashlib


def get_file_hash(file_url: str) -> str:
    with open(file_url, "rb") as file:
        file_hash = hashlib.md5()
        # consider file can be huge, so break into 8192 bytes chunks
        while chunk := file.read(8192):
            file_hash.update(chunk)

    return file_hash.hexdigest()
