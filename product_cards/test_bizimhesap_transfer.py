from django.test import SimpleTestCase
from .bizimhesap_transfer import payload_digest, parse_addinvoice_response, TransferResponseError

class TransferTests(SimpleTestCase):
    def test_digest(self):
        self.assertEqual(payload_digest({'a': 1, 'b': 2}), payload_digest({'b': 2, 'a': 1}))
        self.assertNotEqual(payload_digest({'a': 1}), payload_digest({'a': 2}))

    def test_response(self):
        self.assertEqual(parse_addinvoice_response({'error': '', 'guid': 'abc'})['guid'], 'abc')
        with self.assertRaises(TransferResponseError):
            parse_addinvoice_response({'error': '', 'guid': ''})

    def test_invoice_export_disabled_by_default(self):
        from unittest.mock import patch
        from .bizimhesap_export_service import prepare_transfer, TransferBlocked
        with patch.dict('os.environ', {'BIZIMHESAP_INVOICE_EXPORT_ENABLED': 'false'}):
            with self.assertRaises(TransferBlocked):
                prepare_transfer(9)
