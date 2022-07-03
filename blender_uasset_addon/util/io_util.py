"""Utils for I/O."""

import os
import struct
import tempfile


def make_temp_file(suffix=None):
    """Make a temp file and return its path.

    Notes:
        You need to delete the file by your self.
    """
    temp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    temp_path = temp.name
    temp.close()
    return temp_path


def mkdir(directory):
    """Make dirctory."""
    os.makedirs(directory, exist_ok=True)


def get_ext(file):
    """Get file extension."""
    return file.split('.')[-1]


def get_size(f):
    """Get file size."""
    pos = f.tell()
    f.seek(0, 2)
    size = f.tell()
    f.seek(pos)
    return size


def check(actual, expected, f=None, msg='Parse failed. This is unexpected error.'):
    """Check if actual and expected is the same."""
    if actual != expected:
        if f is not None:
            print(f'offset: {f.tell()}')
        print(f'actual: {actual}')
        print(f'expected: {expected}')
        raise RuntimeError(msg)


def read_uint32(file):
    """Read 4-byte as uint."""
    binary = file.read(4)
    return int.from_bytes(binary, "little")


def read_uint16(file):
    """Read 2-byte as uint."""
    binary = file.read(2)
    return int.from_bytes(binary, "little")


def read_uint8(file):
    """Read 1-byte as uint."""
    binary = file.read(1)
    return int(binary[0])


def read_int32(file):
    """Read 4-byte as int."""
    binary = file.read(4)
    return int.from_bytes(binary, "little", signed=True)


def read_uint64(file):
    """Read 8-byte as uint."""
    binary = file.read(8)
    return int.from_bytes(binary, "little")


def read_float32(file):
    """Read 4-byte as float."""
    binary = file.read(4)
    return struct.unpack('<f', binary)[0]


def read_float16(file):
    """Read 2-byte as float."""
    binary = file.read(2)
    return struct.unpack('<e', binary)[0]


def read_array(file, read_func, len=None):
    """Read an array."""
    if len is None:
        len = read_uint32(file)
    ary = [read_func(file) for i in range(len)]
    return ary


st_list = ['b', 'B', 'h', 'H', 'i', 'I', 'l', 'L', 'e', 'f', 'd']
st_size = [1, 1, 2, 2, 4, 4, 8, 8, 2, 4, 8]


def read_num_array(file, st, len=None):
    """Read an array of numbers."""
    if st not in st_list:
        raise RuntimeError('Structure not found. {}'.format(st))
    if len is None:
        len = read_uint32(file)
    binary = file.read(st_size[st_list.index(st)] * len)
    return list(struct.unpack(st * len, binary))


def read_uint32_array(file, len=None):
    """Read an array of uint32."""
    return read_num_array(file, 'I', len=len)


def read_uint16_array(file, len=None):
    """Read an array of uint16."""
    return read_num_array(file, 'H', len=len)


def read_uint8_array(file, len=None):
    """Read an array of uint8."""
    return read_num_array(file, 'B', len=len)


def read_int32_array(file, len=None):
    """Read an array of int32."""
    return read_num_array(file, 'i', len=len)


def read_float64_array(file, len=None):
    """Read an array of float64."""
    return read_num_array(file, 'd', len=len)


def read_float32_array(file, len=None):
    """Read an array of float32."""
    return read_num_array(file, 'f', len=len)


def read_float16_array(file, len=None):
    """Read an array of float16."""
    return read_num_array(file, 'e', len=len)


def read_vec3_f32(file):
    """Read 3 float numbers."""
    return read_float32_array(file, len=3)


def read_vec3_f32_array(file):
    """Read an array of vec3."""
    return read_array(file, read_vec3_f32)


def read_16byte(file):
    """Read 16 bytes."""
    return file.read(16)


def read_str(file):
    """Read string."""
    num = read_int32(file)
    if num == 0:
        return None

    utf16 = num < 0
    if num < 0:
        num = -num
    encode = 'utf-16-le' if utf16 else 'ascii'
    # encode = "utf-16-le" * utf16 + "ascii" * (not utf16)
    string = file.read((num - 1) * (1 + utf16)).decode(encode)
    file.seek(1 + utf16, 1)
    return string


def read_const_uint32(f, n, msg='Unexpected Value!'):
    """Read uint32 and check if it's the same as specified value."""
    const = read_uint32(f)
    check(const, n, f, msg)


def read_null(f, msg='Not NULL!'):
    """Read uint32 and check if it's 0."""
    read_const_uint32(f, 0, msg)


def read_null_array(f, len, msg='Not NULL!'):
    """Read an array of 0s."""
    null = read_uint32_array(f, len=len)
    check(null, [0] * len, f, msg)


def read_struct_array(f, obj, len=None):
    """Read an array of ctypes objects."""
    if len is None:
        len = read_uint32(f)
    objects = [obj() for i in range(len)]
    list(map(f.readinto, objects))
    return objects


def write_uint64(file, n):
    """Write int as uint64."""
    binary = n.to_bytes(8, byteorder="little")
    file.write(binary)


def write_uint32(file, n):
    """Write int as uint32."""
    binary = n.to_bytes(4, byteorder="little")
    file.write(binary)


def write_uint16(file, n):
    """Write int as uint16."""
    binary = n.to_bytes(2, byteorder="little")
    file.write(binary)


def write_uint8(file, n):
    """Write int as uint8."""
    binary = n.to_bytes(1, byteorder="little")
    file.write(binary)


def write_int32(file, n):
    """Write int as int32."""
    binary = n.to_bytes(4, byteorder="little", signed=True)
    file.write(binary)


def write_float64(file, x):
    """Write float as float64."""
    binary = struct.pack('<d', x)
    file.write(binary)


def write_float32(file, x):
    """Write float as float32."""
    binary = struct.pack('<f', x)
    file.write(binary)


def write_float16(file, x):
    """Write float as float16."""
    binary = struct.pack('<e', x)
    file.write(binary)


def write_array(file, ary, write_func, with_length=False):
    """Write an array."""
    if with_length:
        write_uint32(file, len(ary))
    for a in ary:
        write_func(file, a)


def write_uint32_array(file, ary, with_length=False):
    """Write an array of uint32."""
    write_array(file, ary, write_uint32, with_length=with_length)


def write_uint16_array(file, ary, with_length=False):
    """Write an array of uint16."""
    write_array(file, ary, write_uint16, with_length=with_length)


def write_uint8_array(file, ary, with_length=False):
    """Write an array of uint8."""
    write_array(file, ary, write_uint8, with_length=with_length)


def write_int32_array(file, ary, with_length=False):
    """Write an array of int32."""
    write_array(file, ary, write_int32, with_length=with_length)


def write_float64_array(file, ary, with_length=False):
    """Write an array of float64."""
    write_array(file, ary, write_float64, with_length=with_length)


def write_float32_array(file, ary, with_length=False):
    """Write an array of float32."""
    write_array(file, ary, write_float32, with_length=with_length)


def write_float16_array(file, ary, with_length=False):
    """Write an array of float32."""
    write_array(file, ary, write_float16, with_length=with_length)


def write_vec3_f32(file, vec3):
    """Write 3 float numbers."""
    write_float32_array(file, vec3)


def write_vec3_f32_array(file, vec_ary, with_length=False):
    """Write an array of vec3."""
    return write_array(file, vec_ary, write_vec3_f32, with_length=with_length)


def write_16byte(file, binary):
    """Write binary."""
    return file.write(binary)


def write_str(file, string):
    """Write a string."""
    num = len(string) + 1
    utf16 = not string.isascii()
    write_int32(file, num * (1 - 2 * utf16))
    encode = 'utf-16-le' if utf16 else 'ascii'
    str_byte = string.encode(encode)
    file.write(str_byte + b'\x00' * (1 + utf16))


def write_null(f):
    """Write 0 as uint32."""
    write_uint32(f, 0)


def write_null_array(f, len):
    """Write an array of 0s."""
    write_uint32_array(f, [0] * len)


def compare(file1, file2):
    """Check if 2 files have the same binary data."""
    f_1 = open(file1, 'rb')
    f_2 = open(file2, 'rb')
    print(f'Comparing {file1} and {file2}...')

    f1_size = get_size(f_1)
    f2_size = get_size(f_2)

    i = 0
    f1_bin = f_1.read()
    f2_bin = f_2.read()
    f_1.close()
    f_2.close()

    if f1_size == f2_size and f1_bin == f2_bin:
        print('Same data!')
        return

    i = -1
    for b_1, b_2 in zip(f1_bin, f2_bin):
        i += 1
        if b_1 != b_2:
            break

    raise RuntimeError('Not same :{}'.format(i))
