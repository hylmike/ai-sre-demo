"""Using nanoid to generate id, to be used as document id in vectorDB"""

from nanoid import generate


def gen_document_id() -> str:
    chars = "1234567890abcdefghijklmnopqrstuvwxyz"
    return generate(chars, size=10)
