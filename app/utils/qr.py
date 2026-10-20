"""Local QR image generation."""

from io import BytesIO

import qrcode
from qrcode.constants import ERROR_CORRECT_H


def make_qr_png(value: str) -> BytesIO:
    code = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_H, box_size=12, border=4)
    code.add_data(value)
    code.make(fit=True)
    image = code.make_image(fill_color="#0f172a", back_color="white")
    output = BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return output