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
