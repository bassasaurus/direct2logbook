"""Render stored normalized handwriting only when a consumer needs an image."""
import base64
from io import BytesIO
from PIL import Image, ImageDraw


def render_signature(strokes, aspect_ratio=3):
    # Supersampling smooths handwriting; retain a fixed 3:1 aspect ratio on all devices.
    image = Image.new('RGBA', (1800, round(1800 / aspect_ratio)), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    for stroke in strokes:
        points = [(round(x * 1799), round(y * (image.height - 1))) for x, y in stroke]
        if len(points) > 1:
            draw.line(points, fill='black', width=7, joint='curve')
        for x, y in (points[0], points[-1]):
            draw.ellipse((x-3, y-3, x+3, y+3), fill='black')
    image = image.resize((900, round(900 / aspect_ratio)), Image.Resampling.LANCZOS)
    output = BytesIO()
    image.save(output, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii')
