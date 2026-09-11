from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies=[("core","0056_auditlog"),("product_cards","0017_productcard_price_list_active"),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(name="ShowroomDraft",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("status",models.CharField(choices=[("DRAFT","Taslak"),("PENDING","Onay Bekliyor"),("APPROVED","Onaylandı"),("TRANSFERRED","Siparişe Aktarıldı")],default="DRAFT",max_length=12)),
            ("currency",models.CharField(choices=[("TRY","TL"),("USD","USD"),("EUR","EUR")],default="TRY",max_length=3)),
            ("profit_rate",models.DecimalField(decimal_places=2,default=0,max_digits=7)),
            ("discount_rate",models.DecimalField(decimal_places=2,default=0,max_digits=7)),
            ("monthly_term_rate",models.DecimalField(decimal_places=2,default=0,max_digits=7)),
            ("usd_try",models.DecimalField(decimal_places=6,default=1,max_digits=12)),
            ("eur_try",models.DecimalField(decimal_places=6,default=1,max_digits=12)),
            ("overall_discount_amount",models.DecimalField(decimal_places=2,default=0,max_digits=16)),
            ("discount_scope",models.CharField(choices=[("ALL","Tüm ürünler"),("SELECTED","Seçili ürünler")],default="ALL",max_length=10)),
            ("created_at",models.DateTimeField(auto_now_add=True)),("updated_at",models.DateTimeField(auto_now=True)),
            ("created_by",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="showroom_drafts",to=settings.AUTH_USER_MODEL)),
            ("customer",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="showroom_drafts",to="core.musteri")),
        ],options={"ordering":["-updated_at","-id"]}),
        migrations.CreateModel(name="ShowroomDraftItem",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("color",models.CharField(blank=True,default="",max_length=120)),("size",models.CharField(blank=True,default="",max_length=120)),
            ("quantity",models.PositiveIntegerField(default=1)),("unit_price",models.DecimalField(decimal_places=2,max_digits=16)),
            ("discount_selected",models.BooleanField(default=True)),("created_at",models.DateTimeField(auto_now_add=True)),("updated_at",models.DateTimeField(auto_now=True)),
            ("draft",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="items",to="product_cards.showroomdraft")),
            ("product_card",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="showroom_draft_items",to="product_cards.productcard")),
        ],options={"ordering":["created_at","id"]}),
    ]
