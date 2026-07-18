from django.db import migrations


def reset_catalog_verification(apps, schema_editor):
    Asset = apps.get_model("assets", "Asset")
    Source = apps.get_model("sources", "Source")
    Asset.objects.filter(internal_notes__startswith="Catalog provenance:").update(
        last_verified_at=None,
        reviewed_at=None,
        reviewed_by=None,
        review_notes="",
    )
    Source.objects.filter(notes__startswith="Catalog provenance:").update(
        verification_status="unreviewed",
        last_verified_at=None,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0003_asset_review_notes_asset_reviewed_at_and_more"),
        ("sources", "0002_source_check_error_source_http_status_and_more"),
    ]

    operations = [migrations.RunPython(reset_catalog_verification, migrations.RunPython.noop)]
