from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("assets", "0026_submission_state")]

    operations = [
        migrations.AddField(
            model_name="sitediagram",
            name="image_kind",
            field=models.CharField(
                choices=[("diagram", "Diagram"), ("photo", "Profile photograph")],
                default="diagram", max_length=12,
                help_text="The first approved photograph appears beside the asset overview. "
                          "Diagrams stay in Supporting details.",
            ),
        ),
    ]
