"""Simple Cipher.

Notes:
    This cipher is vulnerable.
    Hard to edit with hex editors, but easy to decode for programers.
"""

KEY = list('F-JaNcRfUjXn2r5u8x/A?D(G+KbPeSgV'.encode())


def encrypt(string):
    """Encrypt a string."""
    if len(string) == 0:
        return b''
    str_int = list(string.encode())
    encrypted = []
    key = (KEY * (len(str_int) // len(KEY) + 1))[:len(str_int)]
    i_2 = 0
    for i, k in zip(str_int, key):
        j = i ^ i_2 ^ k
        encrypted.append(j.to_bytes(1, 'big'))
        i_2 = j

    encrypted = b''.join(encrypted)
    return encrypted


def decrypt(binary):
    """Decrypt binary data."""
    if len(binary) == 0:
        return ''
    decrypted = []
    bin_int = list(binary)

    bin_int.reverse()
    key = (KEY * (len(bin_int) // len(KEY) + 1))[:len(bin_int)]
    key.reverse()
    i_2 = bin_int[0]
    for i, k in zip(bin_int[1:], key):
        j = i ^ i_2 ^ k
        decrypted.append(j.to_bytes(1, 'big'))
        i_2 = i
    decrypted.append((i_2 ^ key[-1]).to_bytes(1, 'big'))
    decrypted.reverse()
    decrypted = b''.join(decrypted)
    return decrypted.decode()
