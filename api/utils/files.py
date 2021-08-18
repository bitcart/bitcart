import os

from api.settings import DATADIR, IMAGES_DIR, ensure_exists

PRODUCTS_IMAGE_DIR = os.path.join(IMAGES_DIR, "products")
ensure_exists(PRODUCTS_IMAGE_DIR)


def get_product_image_path(model_id):
    return f"images/products/{model_id}.png"


def get_product_image_filename(filename):
    return os.path.join(DATADIR, filename)


async def save_image(filename, image):
    filename = get_product_image_filename(filename)
    with open(filename, "wb") as f:
        f.write(await image.read())


def safe_remove(filename):
    try:
        os.remove(filename)
    except (TypeError, OSError):
        pass
