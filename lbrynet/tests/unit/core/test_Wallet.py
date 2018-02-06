import os
import shutil
import tempfile
import lbryum.wallet

from decimal import Decimal
from collections import defaultdict
from twisted.trial import unittest
from twisted.internet import threads, defer
from lbrynet.database.storage import SQLiteStorage
from lbrynet.tests.mocks import FakeNetwork
from lbrynet.core.Error import InsufficientFundsError
from lbrynet.core.Wallet import LBRYumWallet, ReservedPoints
from lbryum.commands import Commands
from lbryum.simple_config import SimpleConfig
from lbryschema.claim import ClaimDict

test_metadata = {
'license': 'NASA',
'version': '_0_1_0',
'description': 'test',
'language': 'en',
'author': 'test',
'title': 'test',
'nsfw': False,
'thumbnail': 'test'
}

test_claim_dict = {
    'version':'_0_0_1',
    'claimType':'streamType',
    'stream':{'metadata':test_metadata, 'version':'_0_0_1', 'source':
        {'source': '8655f713819344980a9a0d67b198344e2c462c90f813e86f'
                   '0c63789ab0868031f25c54d0bb31af6658e997e2041806eb',
         'sourceType': 'lbry_sd_hash', 'contentType': 'video/mp4', 'version': '_0_0_1'},
}}


class MocLbryumWallet(LBRYumWallet):
    def __init__(self):
        # LBRYumWallet.__init__(self)
        self.config = SimpleConfig()
        self.wallet_balance = Decimal(10.0)
        self.total_reserved_points = Decimal(0.0)
        self.queued_payments = defaultdict(Decimal)
        self.network = FakeNetwork()
        self.db_dir = tempfile.mkdtemp()
        self.storage = SQLiteStorage(self.db_dir)

    def __del__(self):
        shutil.rmtree(self.db_dir)

    def setup(self):
        return self.storage.setup()

    def get_least_used_address(self, account=None, for_change=False, max_count=100):
        return defer.succeed(None)

    def get_name_claims(self):
        return threads.deferToThread(lambda: [])

    def _save_name_metadata(self, name, claim_outpoint, sd_hash):
        return defer.succeed(True)


class WalletTest(unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        wallet = MocLbryumWallet()
        yield wallet.setup()
        seed_text = "travel nowhere air position hill peace suffer parent beautiful rise " \
                    "blood power home crumble teach"
        password = "secret"
        user_dir = tempfile.mkdtemp()
        path = os.path.join(user_dir, "somewallet")
        storage = lbryum.wallet.WalletStorage(path)
        wallet.wallet = lbryum.wallet.NewWallet(storage)
        wallet.wallet.add_seed(seed_text, password)
        wallet.wallet.create_master_keys(password)
        wallet.wallet.create_main_account()

        self.wallet_path = path
        self.enc_wallet = wallet
        self.enc_wallet_password = password

    def tearDown(self):
        shutil.rmtree(os.path.dirname(self.wallet_path))

    def test_failed_send_name_claim(self):
        def not_enough_funds_send_name_claim(self, name, val, amount):
            claim_out = {'success':False, 'reason':'Not enough funds'}
            return claim_out

        MocLbryumWallet._send_name_claim = not_enough_funds_send_name_claim
        wallet = MocLbryumWallet()
        d = wallet.setup()
        d.addCallback(lambda _: wallet.claim_name('test', 1, test_claim_dict))
        self.assertFailure(d, Exception)
        return d

    def test_successful_send_name_claim(self):
        expected_claim_out = {
            "claim_id": "f43dc06256a69988bdbea09a58c80493ba15dcfa",
            "fee": "0.00012",
            "nout": 0,
            "success": True,
            "txid": "6f8180002ef4d21f5b09ca7d9648a54d213c666daf8639dc283e2fd47450269e",
            "value": ClaimDict.load_dict(test_claim_dict).serialized.encode('hex'),
            "claim_address": "",
            "channel_claim_id": "",
            "channel_name": ""
        }

        def check_out(claim_out):
            self.assertTrue('success' not in claim_out)
            self.assertEqual(expected_claim_out['claim_id'], claim_out['claim_id'])
            self.assertEqual(expected_claim_out['fee'], claim_out['fee'])
            self.assertEqual(expected_claim_out['nout'], claim_out['nout'])
            self.assertEqual(expected_claim_out['txid'], claim_out['txid'])
            self.assertEqual(expected_claim_out['value'], claim_out['value'])

        def success_send_name_claim(self, name, val, amount, certificate_id=None,
                                    claim_address=None, change_address=None):
            return expected_claim_out

        MocLbryumWallet._send_name_claim = success_send_name_claim
        wallet = MocLbryumWallet()
        d = wallet.setup()
        d.addCallback(lambda _: wallet.claim_name('test', 1, test_claim_dict))
        d.addCallback(lambda claim_out: check_out(claim_out))
        return d

    def test_failed_support(self):
        def failed_support_claim(self, name, claim_id, amount):
            claim_out = {'success':False, 'reason':'Not enough funds'}
            return threads.deferToThread(lambda: claim_out)
        MocLbryumWallet._support_claim = failed_support_claim
        wallet = MocLbryumWallet()
        d = wallet.setup()
        d.addCallback(lambda _: wallet.support_claim('test', "f43dc06256a69988bdbea09a58c80493ba15dcfa", 1))
        self.assertFailure(d, Exception)
        return d

    def test_succesful_support(self):
        expected_support_out = {
            "fee": "0.000129",
            "nout": 0,
            "success": True,
            "txid": "11030a76521e5f552ca87ad70765d0cc52e6ea4c0dc0063335e6cf2a9a85085f"
        }

        def check_out(claim_out):
            self.assertTrue('success' not in claim_out)
            self.assertEqual(expected_support_out['fee'], claim_out['fee'])
            self.assertEqual(expected_support_out['nout'], claim_out['nout'])
            self.assertEqual(expected_support_out['txid'], claim_out['txid'])

        def success_support_claim(self, name, val, amount):
            return threads.deferToThread(lambda: expected_support_out)
        MocLbryumWallet._support_claim = success_support_claim
        wallet = MocLbryumWallet()
        d = wallet.setup()
        d.addCallback(lambda _: wallet.support_claim('test', "f43dc06256a69988bdbea09a58c80493ba15dcfa", 1))
        d.addCallback(lambda claim_out: check_out(claim_out))
        return d

    def test_failed_abandon(self):
        def failed_abandon_claim(self, claim_outpoint):
            claim_out = {'success':False, 'reason':'Not enough funds'}
            return threads.deferToThread(lambda: claim_out)
        MocLbryumWallet._abandon_claim = failed_abandon_claim
        wallet = MocLbryumWallet()
        d = wallet.setup()
        d.addCallback(lambda _: wallet.abandon_claim("f43dc06256a69988bdbea09a58c80493ba15dcfa", None, None))
        self.assertFailure(d, Exception)
        return d

    def test_successful_abandon(self):
        expected_abandon_out = {
            "fee": "0.000096",
            "success": True,
            "txid": "0578c161ad8d36a7580c557d7444f967ea7f988e194c20d0e3c42c3cabf110dd"
        }

        def check_out(claim_out):
            self.assertTrue('success' not in claim_out)
            self.assertEqual(expected_abandon_out['fee'], claim_out['fee'])
            self.assertEqual(expected_abandon_out['txid'], claim_out['txid'])

        def success_abandon_claim(self, claim_outpoint, txid, nout):
            return threads.deferToThread(lambda: expected_abandon_out)

        MocLbryumWallet._abandon_claim = success_abandon_claim
        wallet = MocLbryumWallet()
        d = wallet.storage.setup()
        d.addCallback(lambda _: wallet.abandon_claim("f43dc06256a69988bdbea09a58c80493ba15dcfa", None, None))
        d.addCallback(lambda claim_out: check_out(claim_out))
        return d

    def test_point_reservation_and_balance(self):
        # check that point reservations and cancellation changes the balance
        # properly
        def update_balance():
            return defer.succeed(5)
        wallet = MocLbryumWallet()
        wallet._update_balance = update_balance
        d = wallet.setup()
        d.addCallback(lambda _: wallet.update_balance())
        # test point reservation
        d.addCallback(lambda _: self.assertEqual(5, wallet.get_balance()))
        d.addCallback(lambda _: wallet.reserve_points('testid', 2))
        d.addCallback(lambda _: self.assertEqual(3, wallet.get_balance()))
        d.addCallback(lambda _: self.assertEqual(2, wallet.total_reserved_points))
        # test reserved points cancellation
        d.addCallback(lambda _: wallet.cancel_point_reservation(ReservedPoints('testid', 2)))
        d.addCallback(lambda _: self.assertEqual(5, wallet.get_balance()))
        d.addCallback(lambda _: self.assertEqual(0, wallet.total_reserved_points))
        # test point sending
        d.addCallback(lambda _: wallet.reserve_points('testid', 2))
        d.addCallback(lambda reserve_points: wallet.send_points_to_address(reserve_points, 1))
        d.addCallback(lambda _: self.assertEqual(3, wallet.get_balance()))
        # test failed point reservation
        d.addCallback(lambda _: wallet.reserve_points('testid', 4))
        d.addCallback(lambda out: self.assertEqual(None, out))
        return d

    def test_point_reservation_and_claim(self):
        # check that claims take into consideration point reservations
        def update_balance():
            return defer.succeed(5)
        wallet = MocLbryumWallet()
        wallet._update_balance = update_balance
        d = wallet.setup()
        d.addCallback(lambda _: wallet.update_balance())
        d.addCallback(lambda _: self.assertEqual(5, wallet.get_balance()))
        d.addCallback(lambda _: wallet.reserve_points('testid', 2))
        d.addCallback(lambda _: wallet.claim_name('test', 4, test_claim_dict))
        self.assertFailure(d, InsufficientFundsError)
        return d

    def test_point_reservation_and_support(self):
        # check that supports take into consideration point reservations
        def update_balance():
            return defer.succeed(5)
        wallet = MocLbryumWallet()
        wallet._update_balance = update_balance
        d = wallet.setup()
        d.addCallback(lambda _: wallet.update_balance())
        d.addCallback(lambda _: self.assertEqual(5, wallet.get_balance()))
        d.addCallback(lambda _: wallet.reserve_points('testid', 2))
        d.addCallback(lambda _: wallet.support_claim(
            'test', "f43dc06256a69988bdbea09a58c80493ba15dcfa", 4))
        self.assertFailure(d, InsufficientFundsError)
        return d

    def test_unlock_wallet(self):
        wallet = self.enc_wallet
        wallet._cmd_runner = Commands(
            wallet.config, wallet.wallet, wallet.network, None, self.enc_wallet_password)
        cmd_runner = wallet.get_cmd_runner()
        cmd_runner.unlock_wallet(self.enc_wallet_password)
        self.assertIsNone(cmd_runner.new_password)
        self.assertEqual(cmd_runner._password, self.enc_wallet_password)

    def test_encrypt_decrypt_wallet(self):
        wallet = self.enc_wallet
        wallet._cmd_runner = Commands(
            wallet.config, wallet.wallet, wallet.network, None, self.enc_wallet_password)
        wallet.encrypt_wallet("secret2", False)
        wallet.decrypt_wallet()

    def test_update_password_keyring_off(self):
        wallet = self.enc_wallet
        wallet.config.use_keyring = False
        wallet._cmd_runner = Commands(
            wallet.config, wallet.wallet, wallet.network, None, self.enc_wallet_password)

        # no keyring available, so ValueError is expected
        with self.assertRaises(ValueError):
            wallet.encrypt_wallet("secret2", True)
