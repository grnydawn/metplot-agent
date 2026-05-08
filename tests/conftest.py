# tests/conftest.py — add image-diff CLI option
def pytest_addoption(parser):
    parser.addoption("--image-diff", action="store_true", default=False,
                     help="Run image-diff suite against tests/golden/")
    parser.addoption("--regenerate-golden", action="store_true", default=False,
                     help="Regenerate golden PNGs (requires --image-diff)")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--image-diff"):
        return
    skip_image = __import__("pytest").mark.skip(reason="--image-diff not given")
    for item in items:
        if "image_diff" in item.keywords:
            item.add_marker(skip_image)
