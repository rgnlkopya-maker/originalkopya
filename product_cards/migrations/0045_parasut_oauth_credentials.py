from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("product_cards", "0044_parasut_mappings")]
    operations = [
        migrations.CreateModel(name="ParasutOAuthCredential", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("company_id", models.CharField(max_length=30, unique=True)),
            ("access_token_encrypted", models.TextField()),
            ("refresh_token_encrypted", models.TextField()),
            ("expires_at", models.DateTimeField()),
            ("updated_at", models.DateTimeField(auto_now=True)),
        ]),
    ]
