from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0008_separate_source_backed_listings"),
    ]

    operations = [
        migrations.AlterField(
            model_name="asset",
            name="location_precision",
            field=models.CharField(
                choices=[
                    ("exact", "Exact"),
                    ("site", "Site or campus"),
                    ("approximate", "Approximate"),
                    ("locality", "Locality only"),
                    ("regional", "Regional; no single site"),
                    ("hidden", "Hidden"),
                ],
                default="approximate",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="historicalasset",
            name="location_precision",
            field=models.CharField(
                choices=[
                    ("exact", "Exact"),
                    ("site", "Site or campus"),
                    ("approximate", "Approximate"),
                    ("locality", "Locality only"),
                    ("regional", "Regional; no single site"),
                    ("hidden", "Hidden"),
                ],
                default="approximate",
                max_length=20,
            ),
        ),
    ]
