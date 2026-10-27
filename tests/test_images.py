import struct

from tistory_mcp.images import image_dimensions


def test_png_gif_jpeg_webp():
    png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 300, 366)
    assert image_dimensions(png) == (300, 366)
    gif = b"GIF89a" + struct.pack("<HH", 12, 34)
    assert image_dimensions(gif) == (12, 34)
    # JPEG: SOI, APP0(len 16), SOF0(len 17: precision, height, width)
    jpeg = b"\xff\xd8" + b"\xff\xe0" + struct.pack(">H", 16) + b"\x00" * 14
    jpeg += (
        b"\xff\xc0" + struct.pack(">H", 17) + b"\x08" + struct.pack(">HH", 480, 640) + b"\x00" * 10
    )
    assert image_dimensions(jpeg) == (640, 480)
    vp8x = (
        b"RIFF"
        + b"\x00" * 4
        + b"WEBP"
        + b"VP8X"
        + b"\x00" * 8
        + (99).to_bytes(3, "little")
        + (49).to_bytes(3, "little")
    )
    assert image_dimensions(vp8x) == (100, 50)
    assert image_dimensions(b"notanimage") is None
