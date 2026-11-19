"""Approved profile photography, using bundled files only for exact source matches."""

import json
from functools import lru_cache

from django.conf import settings
from django.templatetags.static import static

from .diagrams import SiteDiagram


@lru_cache(maxsize=1)
def photo_manifest():
    return json.loads((settings.BASE_DIR / "data/profile_photos_2026_11_19.json").read_text())


def public_profile_photo(asset):
    photo = asset.site_diagrams.filter(
        publication_approved=True, image_kind=SiteDiagram.ImageKind.PHOTO,
    ).order_by("pk").first()
    if not photo:
        return None
    approved = next((entry for entry in photo_manifest()["photos"] if
                     (entry["state"], entry["asset_name"], entry["image_url"])
                     == (asset.state, asset.name, photo.image_url)), None)
    return {
        "image_url": static(approved["static_path"]) if approved else photo.image_url,
        "width": approved["width"] if approved else None,
        "height": approved["height"] if approved else None,
        "alt_text": photo.alt_text, "caption": photo.caption,
        "credit": photo.credit, "source_url": photo.source_url,
    }
