class Cipher:
    #Block chained XOR cipher
    KEY=list('F-JaNcRfUjXn2r5u8x/A?D(G+KbPeSgV'.encode())
    
    def encrypt(str):
        if len(str)==0:
            return b''
        str_int=list(str.encode())
        encrypted=[]
        key=(Cipher.KEY*(len(str_int)//len(Cipher.KEY)+1))[:len(str_int)]
        i2=0
        for i,k in zip(str_int, key):
            j=i^i2^k
            encrypted.append(j.to_bytes(1, 'big'))
            i2=j

        encrypted=b''.join(encrypted)
        return encrypted

    def decrypt(bin):
        if len(bin)==0:
            return ''
        decrypted=[]
        bin_int=list(bin)

        bin_int.reverse()
        key=(Cipher.KEY*(len(bin_int)//len(Cipher.KEY)+1))[:len(bin_int)]
        key.reverse()
        i2=bin_int[0]
        for i,k in zip(bin_int[1:], key):
            j=i^i2^k
            decrypted.append(j.to_bytes(1, 'big'))
            i2=i
        decrypted.append((i^key[-1]).to_bytes(1, 'big'))
        decrypted.reverse()
        decrypted=b''.join(decrypted)
        return decrypted.decode()