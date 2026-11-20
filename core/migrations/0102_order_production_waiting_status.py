from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0101_gallery_production_note"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="kesim_durum",
            field=models.CharField(
                max_length=20,
                default="bekliyor",
                choices=[
                    ("bekliyor", "Bekliyor"), ("basladi", "Başladı"),
                    ("bitti", "Bitti"), ("beklemede", "Beklemede"),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="order",
            name="dikim_durum",
            field=models.CharField(
                max_length=20,
                default="bekliyor",
                choices=[
                    ("bekliyor", "Bekliyor"), ("basladi", "Başladı"),
                    ("bitti", "Bitti"), ("beklemede", "Beklemede"),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="order",
            name="susleme_durum",
            field=models.CharField(
                max_length=20,
                default="bekliyor",
                choices=[
                    ("bekliyor", "Bekliyor"), ("basladi", "Başladı"),
                    ("bitti", "Bitti"), ("beklemede", "Beklemede"),
                ],
            ),
        ),
    ]
