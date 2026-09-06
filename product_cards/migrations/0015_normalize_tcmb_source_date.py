from django.db import migrations


FORWARD_SQL = r'''
CREATE OR REPLACE FUNCTION product_cards_normalize_source_date()
RETURNS trigger AS $$
BEGIN
    IF NEW.source_date ~ '^[0-9]{2}/[0-9]{2}/[0-9]{4}$' THEN
        NEW.source_date := split_part(NEW.source_date, '/', 2) || '.' || split_part(NEW.source_date, '/', 1) || '.' || split_part(NEW.source_date, '/', 3);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_product_cards_normalize_source_date ON product_cards_exchangerate;
CREATE TRIGGER trg_product_cards_normalize_source_date
BEFORE INSERT OR UPDATE OF source_date ON product_cards_exchangerate
FOR EACH ROW
EXECUTE FUNCTION product_cards_normalize_source_date();

UPDATE product_cards_exchangerate
SET source_date = split_part(source_date, '/', 2) || '.' || split_part(source_date, '/', 1) || '.' || split_part(source_date, '/', 3)
WHERE source_date ~ '^[0-9]{2}/[0-9]{2}/[0-9]{4}$';
'''

REVERSE_SQL = r'''
DROP TRIGGER IF EXISTS trg_product_cards_normalize_source_date ON product_cards_exchangerate;
DROP FUNCTION IF EXISTS product_cards_normalize_source_date();
'''


class Migration(migrations.Migration):
    dependencies = [
        ("product_cards", "0014_repair_incomplete_financial_snapshots"),
    ]

    operations = [
        migrations.RunSQL(FORWARD_SQL, REVERSE_SQL),
    ]
