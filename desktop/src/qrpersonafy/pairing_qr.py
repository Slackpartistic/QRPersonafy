"""QR code images for the pairing URI."""

import qrcode
import qrcode.image.svg


def qr_svg(uri: str) -> str:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=2, box_size=10)
    qr.add_data(uri)
    return qr.make_image(image_factory=qrcode.image.svg.SvgPathImage).to_string(encoding="unicode")
