"""Maps: the map library (Leaflet) served from the site itself, and early connections to the tile hosts.

site/vendor/leaflet-1.9.4/ holds release files of Leaflet 1.9.4 as published (npm leaflet@1.9.4, dist/), with their
licence. The page loads them from LEAFLET in site/features/50-maps.js; the service worker saves them with the shell.
"""

import hashlib
import shutil

from build_web import SITE, BookError, Site

LEAFLET = "vendor/leaflet-1.9.4"
# SHA-256 of each published file (the npm tarball matched its registry integrity), so a changed file fails the build.
LEAFLET_FILES = {
    "leaflet.js": "db49d009c841f5ca34a888c96511ae936fd9f5533e90d8b2c4d57596f4e5641a",
    "leaflet.css": "a7837102824184820dfa198d1ebcd109ff6d0ff9a2672a074b9a1b4d147d04c6",
    "images/layers.png": "1dbbe9d028e292f36fcba8f8b3a28d5e8932754fc2215b9ac69e4cdecf5107c6",
    "images/layers-2x.png": "066daca850d8ffbef007af00b06eac0015728dee279c51f3cb6c716df7c42edf",
    "images/marker-icon.png": "574c3a5cca85f4114085b6841596d62f00d7c892c7b03f28cbfa301deb1dc437",
    "images/marker-icon-2x.png": "00179c4c1ee830d3a108412ae0d294f55776cfeb085c60129a39aa6fc4ae2528",
    "images/marker-shadow.png": "264f5c640339f042dd729062cfc04c17f8ea0f29882b538e3848ed8f10edb4da",
}
# The tile hosts of makeMap in 50-maps.js. Tiles load with CORS, so the early connection needs crossorigin too.
# Known limit: every page opens these connections, also a book with no map. Revisit when a book without maps ships.
TILE_HOSTS = ("https://a.tile.opentopomap.org", "https://b.tile.opentopomap.org", "https://c.tile.opentopomap.org")


def values(site: Site) -> dict[str, str]:
    return {"head": "".join(f'<link rel="preconnect" href="{host}" crossorigin>\n' for host in TILE_HOSTS)}


def write(site: Site) -> None:
    for name, sha256 in LEAFLET_FILES.items():
        source = SITE / LEAFLET / name
        if hashlib.sha256(source.read_bytes()).hexdigest() != sha256:
            raise BookError(f"{source}: not the published Leaflet 1.9.4 file")
        dest = site.out / LEAFLET / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
