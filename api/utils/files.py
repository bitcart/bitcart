import os


def get_image_filename(model_id):
    return f"images/products/{model_id}.png"


async def save_image(filename, image):
    with open(filename, "wb") as f:
        f.write(await image.read())


def safe_remove(filename):
    try:
        os.remove(filename)
    except (TypeError, OSError):
        pass
