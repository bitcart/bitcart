import os


def get_image_filename(image, create=True, model=None):
    if create:
        filename = "images/products/temp.png" if image else None
    else:
        filename = f"images/products/{model.id}.png" if image else model.image
    return filename


async def save_image(filename, image):
    with open(filename, "wb") as f:
        f.write(await image.read())


def safe_remove(filename):
    try:
        os.remove(filename)
    except (TypeError, OSError):
        pass
