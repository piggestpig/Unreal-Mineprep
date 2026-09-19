"""Small PNG alpha reader for thin-face validation; no Pillow dependency.

Only non-interlaced 8-bit PNG pixels are decoded here. UE handles actual texture
import, including images outside this reader's subset.
"""
import math
import struct
import zlib


def alpha_reader(raw):
    if not raw or not raw.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Invalid PNG skin')

    offset, data, transparency = 8, bytearray(), b''
    width = height = channels = color = 0
    ended = False
    while offset + 12 <= len(raw):
        size = int.from_bytes(raw[offset:offset+4], 'big')
        kind = raw[offset+4:offset+8]
        chunk = raw[offset+8:offset+8+size]
        if len(chunk) != size or offset+12+size > len(raw):
            raise ValueError('Truncated PNG')
        crc = int.from_bytes(raw[offset+8+size:offset+12+size], 'big')
        if zlib.crc32(kind+chunk) != crc:
            raise ValueError('Invalid PNG checksum')
        offset += size+12

        if kind == b'IHDR':
            if size != 13:
                raise ValueError('Invalid PNG header')
            width, height, depth, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', chunk)
            if depth != 8 or interlace or color not in (0, 2, 3, 4, 6):
                return None
            if not 0 < width*height <= 16777216:
                raise ValueError('Skin dimensions exceed limit')
            channels = {0:1, 2:3, 3:1, 4:2, 6:4}[color]
        elif kind == b'tRNS':
            transparency = chunk
        elif kind == b'IDAT':
            data.extend(chunk)
        elif kind == b'IEND':
            ended = True
            break

    if not ended:
        raise ValueError('Missing PNG end marker')

    stride = width*channels
    limit = (stride+1)*height
    decoder = zlib.decompressobj()
    pixels = decoder.decompress(data, limit+1)
    if not channels or len(pixels) != limit or not decoder.eof:
        raise ValueError('Invalid PNG pixel data')

    previous = bytearray(stride)
    alpha = bytearray(width*height)
    for y in range(height):
        row_offset = y*(stride+1)
        mode = pixels[row_offset]
        row = bytearray(pixels[row_offset+1:row_offset+1+stride])
        if mode > 4:
            raise ValueError('Invalid PNG filter')

        for i in range(stride):
            a = row[i-channels] if i >= channels else 0
            b = previous[i]
            c = previous[i-channels] if i >= channels else 0
            predictor = a+b-c
            pa, pb, pc = abs(predictor-a), abs(predictor-b), abs(predictor-c)
            paeth = a if pa <= pb and pa <= pc else b if pb <= pc else c
            row[i] = (row[i] + (0, a, b, (a+b)//2, paeth)[mode]) & 255

        for x in range(width):
            p = row[x*channels:(x+1)*channels]
            if color in (4, 6):
                value = p[-1]
            elif color == 3:
                value = transparency[p[0]] if p[0] < len(transparency) else 255
            else:
                transparent = tuple(int.from_bytes(transparency[i:i+2], 'big') for i in range(0,len(transparency),2))
                value = 0 if transparent and tuple(p) == transparent else 255
            alpha[y*width+x] = value
        previous = row

    def painted(rect, texture_size):
        u1,v1,u2,v2 = rect
        tw,th = texture_size
        x0,x1 = math.floor(min(u1,u2)*width/tw), math.ceil(max(u1,u2)*width/tw)
        y0,y1 = math.floor(min(v1,v2)*height/th), math.ceil(max(v1,v2)*height/th)
        return any(alpha[y*width+x] for y in range(max(0,y0),min(height,y1))
                   for x in range(max(0,x0),min(width,x1)))
    return painted
