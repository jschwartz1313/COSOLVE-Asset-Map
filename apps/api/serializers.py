from apps.assets.scoping import asset_is_in_public_scope


def names(items):
    return [{"name": item.name, "slug": item.slug} for item in items.all()]


def public_relationships(asset):
    related = [
        {
            "name": relationship.to_asset.name,
            "relationship": relationship.get_relationship_type_display(),
            "direction": "outgoing",
            "url": relationship.to_asset.get_absolute_url(),
        }
        for relationship in asset.outgoing_relationships.select_related("to_asset")
        if relationship.is_public
        and relationship.to_asset.status in asset.public_status_values()
        and relationship.to_asset.visibility == asset.Visibility.PUBLIC
        and asset_is_in_public_scope(relationship.to_asset)
    ]
    related.extend(
        {
            "name": relationship.from_asset.name,
            "relationship": relationship.get_relationship_type_display(),
            "direction": "incoming",
            "url": relationship.from_asset.get_absolute_url(),
        }
        for relationship in asset.incoming_relationships.select_related("from_asset")
        if relationship.is_public
        and relationship.from_asset.status in asset.public_status_values()
        and relationship.from_asset.visibility == asset.Visibility.PUBLIC
        and asset_is_in_public_scope(relationship.from_asset)
    )
    return related


def public_asset_dict(asset, include_detail=True):
    data = {
        "id": str(asset.pk),
        "name": asset.name,
        "slug": asset.slug,
        "record_type": asset.record_type,
        "record_type_label": asset.get_record_type_display(),
        "short_description": asset.short_description,
        "overview": asset.overview,
        "unmanned_systems_relevance": asset.unmanned_systems_relevance,
        "location": {
            "address_line": asset.address_line,
            "city": asset.city,
            "state": asset.state,
            "postal_code": asset.postal_code,
            "precision": asset.location_precision,
            "precision_label": asset.get_location_precision_display(),
            "region": asset.region.name if asset.region else None,
        },
        "strategic_categories": names(asset.strategic_categories),
        "platform_domains": names(asset.platform_domains),
        "capabilities": names(asset.capabilities),
        "missions": names(asset.missions),
        "last_verified_at": asset.last_verified_at.isoformat() if asset.last_verified_at else None,
        "review_status": "editorially-reviewed"
        if asset.is_editorially_reviewed
        else "source-backed",
        "review_status_label": asset.verification_label,
        "detail_url": asset.get_absolute_url(),
    }
    if include_detail:
        data.update(
            {
                "website_url": asset.website_url,
                "contact_text": asset.contact_text,
                "contact_phone": asset.contact_phone,
                "contact_email": asset.contact_email,
                "contact_url": asset.contact_url,
                "sources": [
                    {
                        "title": source.title,
                        "url": source.url,
                        "source_date": source.source_date.isoformat()
                        if source.source_date
                        else None,
                        "last_verified_at": (
                            source.last_verified_at.isoformat() if source.last_verified_at else None
                        ),
                        "verification_status": source.verification_status,
                    }
                    for source in asset.sources.all()
                    if source.is_public
                ],
                "related_entities": public_relationships(asset),
            }
        )
    return data


def asset_feature(asset):
    if not asset.has_public_coordinates:
        geometry = None
    else:
        geometry = {
            "type": "Point",
            "coordinates": [float(asset.longitude), float(asset.latitude)],
        }
    properties = {
        "name": asset.name,
        "slug": asset.slug,
        "record_type": asset.record_type,
        "record_type_label": asset.get_record_type_display(),
        "short_description": asset.short_description,
        "verification_state": asset.verification_state,
        "verification_state_label": asset.verification_state_label,
        "last_verified_at": asset.last_verified_at.isoformat()
        if asset.last_verified_at
        else None,
        "location": {
            "address_line": asset.address_line,
            "city": asset.city,
            "state": asset.state,
            "postal_code": asset.postal_code,
            "precision": asset.location_precision,
            "precision_label": asset.get_location_precision_display(),
            "region": asset.region.name if asset.region else None,
            "region_slug": asset.region.slug if asset.region else None,
        },
        "strategic_categories": names(asset.strategic_categories),
        "platform_domains": names(asset.platform_domains),
        "capabilities": names(asset.capabilities),
        "missions": names(asset.missions),
        "detail_url": asset.get_absolute_url(),
    }
    return {"type": "Feature", "id": str(asset.pk), "geometry": geometry, "properties": properties}
