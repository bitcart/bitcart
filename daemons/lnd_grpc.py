"""gRPC client wrapper for communicating with LND instances.

Provides an async Python interface to LND's gRPC services with
TLS certificate and macaroon-based authentication.
"""

import codecs
import os

import grpc

from lnd_proto import (
    chainnotifier_pb2,
    chainnotifier_pb2_grpc,
    invoices_pb2,
    invoices_pb2_grpc,
    lightning_pb2,
    lightning_pb2_grpc,
    router_pb2,
    router_pb2_grpc,
    walletkit_pb2,
    walletkit_pb2_grpc,
    walletunlocker_pb2,
    walletunlocker_pb2_grpc,
)
from logger import get_logger

logger = get_logger(__name__)

# Maximum gRPC message size (50MB) - needed for large responses
MAX_MSG_SIZE = 50 * 1024 * 1024


class LNDGrpcClient:
    """Async gRPC client for a single LND instance.

    Handles TLS/macaroon credential setup and provides convenience
    methods for all LND gRPC calls used by the daemon.

    Args:
        host: LND gRPC hostname
        port: LND gRPC port
        tls_cert_path: Path to tls.cert file
        macaroon_path: Path to admin.macaroon file
        network: Bitcoin network name (for macaroon path resolution)
    """

    def __init__(self, host: str, port: int, tls_cert_path: str, macaroon_path: str):
        self.host = host
        self.port = port
        self.tls_cert_path = tls_cert_path
        self.macaroon_path = macaroon_path
        self.channel: grpc.aio.Channel | None = None
        # Service stubs
        self.lightning: lightning_pb2_grpc.LightningStub | None = None
        self.wallet_unlocker: walletunlocker_pb2_grpc.WalletUnlockerStub | None = None
        self.wallet_kit: walletkit_pb2_grpc.WalletKitStub | None = None
        self.chain_notifier: chainnotifier_pb2_grpc.ChainNotifierStub | None = None
        self.invoices_rpc: invoices_pb2_grpc.InvoicesStub | None = None
        self.router: router_pb2_grpc.RouterStub | None = None

    def _read_macaroon(self) -> str:
        """Read and hex-encode the admin macaroon."""
        with open(self.macaroon_path, "rb") as f:
            return codecs.encode(f.read(), "hex").decode()

    def _build_credentials(self) -> grpc.ChannelCredentials:
        """Build composite TLS + macaroon credentials for the gRPC channel."""
        with open(self.tls_cert_path, "rb") as f:
            cert = f.read()
        ssl_creds = grpc.ssl_channel_credentials(root_certificates=cert)
        macaroon_hex = self._read_macaroon()

        def metadata_callback(context, callback):
            callback([("macaroon", macaroon_hex)], None)

        auth_creds = grpc.metadata_call_credentials(metadata_callback)
        return grpc.composite_channel_credentials(ssl_creds, auth_creds)

    async def connect(self):
        """Establish the gRPC channel and create all service stubs."""
        combined_creds = self._build_credentials()
        self.channel = grpc.aio.secure_channel(
            f"{self.host}:{self.port}",
            combined_creds,
            options=[
                ("grpc.max_receive_message_length", MAX_MSG_SIZE),
                ("grpc.max_send_message_length", MAX_MSG_SIZE),
            ],
        )
        self.lightning = lightning_pb2_grpc.LightningStub(self.channel)
        self.wallet_kit = walletkit_pb2_grpc.WalletKitStub(self.channel)
        self.chain_notifier = chainnotifier_pb2_grpc.ChainNotifierStub(self.channel)
        self.invoices_rpc = invoices_pb2_grpc.InvoicesStub(self.channel)
        self.router = router_pb2_grpc.RouterStub(self.channel)
        logger.info(f"gRPC connected to {self.host}:{self.port}")

    async def connect_unlocker(self):
        """Connect with only TLS (no macaroon) for wallet unlock/init.

        The WalletUnlocker service is available before the wallet is unlocked,
        at which point no macaroon exists yet.
        """
        with open(self.tls_cert_path, "rb") as f:
            cert = f.read()
        ssl_creds = grpc.ssl_channel_credentials(root_certificates=cert)
        channel = grpc.aio.secure_channel(
            f"{self.host}:{self.port}",
            ssl_creds,
            options=[
                ("grpc.max_receive_message_length", MAX_MSG_SIZE),
                ("grpc.max_send_message_length", MAX_MSG_SIZE),
            ],
        )
        self.wallet_unlocker = walletunlocker_pb2_grpc.WalletUnlockerStub(channel)
        logger.info(f"WalletUnlocker connected to {self.host}:{self.port}")

    async def close(self):
        """Close the gRPC channel."""
        if self.channel:
            await self.channel.close()
            self.channel = None

    # -------------------------------------------------------------------------
    # WalletUnlocker service methods
    # -------------------------------------------------------------------------

    async def gen_seed(self, passphrase: bytes = b"") -> list[str]:
        """Generate a new wallet seed (aezeed mnemonic).

        Args:
            passphrase: Optional aezeed passphrase

        Returns:
            List of 24 mnemonic words
        """
        request = walletunlocker_pb2.GenSeedRequest(aezeed_passphrase=passphrase)
        response = await self.wallet_unlocker.GenSeed(request)
        return list(response.cipher_seed_mnemonic)

    async def init_wallet(self, password: bytes, seed_words: list[str], passphrase: bytes = b"") -> bytes:
        """Initialize a new wallet with the given seed.

        Args:
            password: Wallet encryption password
            seed_words: 24-word aezeed mnemonic
            passphrase: Optional aezeed passphrase

        Returns:
            Admin macaroon bytes
        """
        request = walletunlocker_pb2.InitWalletRequest(
            wallet_password=password,
            cipher_seed_mnemonic=seed_words,
            aezeed_passphrase=passphrase,
        )
        response = await self.wallet_unlocker.InitWallet(request)
        return response.admin_macaroon

    async def unlock_wallet(self, password: bytes) -> None:
        """Unlock an existing wallet.

        Args:
            password: Wallet encryption password
        """
        request = walletunlocker_pb2.UnlockWalletRequest(wallet_password=password)
        await self.wallet_unlocker.UnlockWallet(request)

    # -------------------------------------------------------------------------
    # Lightning service methods
    # -------------------------------------------------------------------------

    async def get_info(self) -> lightning_pb2.GetInfoResponse:
        """Get node information including sync status, identity, etc."""
        return await self.lightning.GetInfo(lightning_pb2.GetInfoRequest())

    async def wallet_balance(self) -> lightning_pb2.WalletBalanceResponse:
        """Get on-chain wallet balance."""
        return await self.lightning.WalletBalance(lightning_pb2.WalletBalanceRequest())

    async def channel_balance(self) -> lightning_pb2.ChannelBalanceResponse:
        """Get total channel balance across all channels."""
        return await self.lightning.ChannelBalance(lightning_pb2.ChannelBalanceRequest())

    async def new_address(self, addr_type: int = 0) -> str:
        """Generate a new on-chain address.

        Args:
            addr_type: 0=WITNESS_PUBKEY_HASH, 1=NESTED_PUBKEY_HASH, 4=TAPROOT_PUBKEY

        Returns:
            New Bitcoin address string
        """
        request = lightning_pb2.NewAddressRequest(type=addr_type)
        response = await self.lightning.NewAddress(request)
        return response.address

    async def send_coins(
        self, addr: str, amount: int, sat_per_vbyte: int = 0, send_all: bool = False
    ) -> str:
        """Send on-chain Bitcoin.

        Args:
            addr: Destination address
            amount: Amount in satoshis (ignored if send_all=True)
            sat_per_vbyte: Fee rate in sat/vbyte (0 for automatic)
            send_all: Send entire wallet balance

        Returns:
            Transaction hash
        """
        request = lightning_pb2.SendCoinsRequest(
            addr=addr,
            amount=amount,
            sat_per_vbyte=sat_per_vbyte,
            send_all=send_all,
        )
        response = await self.lightning.SendCoins(request)
        return response.txid

    async def get_transactions(self) -> list:
        """Get all on-chain transactions."""
        response = await self.lightning.GetTransactions(lightning_pb2.GetTransactionsRequest())
        return list(response.transactions)

    async def add_invoice(self, value: int, memo: str = "", expiry: int = 3600) -> lightning_pb2.AddInvoiceResponse:
        """Create a new lightning invoice.

        Args:
            value: Invoice amount in satoshis
            memo: Optional description
            expiry: Invoice expiry in seconds (default 1 hour)

        Returns:
            AddInvoiceResponse with r_hash, payment_request, etc.
        """
        request = lightning_pb2.Invoice(
            value=value,
            memo=memo,
            expiry=expiry,
        )
        return await self.lightning.AddInvoice(request)

    async def lookup_invoice(self, r_hash: bytes) -> lightning_pb2.Invoice:
        """Look up an invoice by its payment hash.

        Args:
            r_hash: Payment hash bytes

        Returns:
            Invoice details
        """
        request = lightning_pb2.PaymentHash(r_hash=r_hash)
        return await self.lightning.LookupInvoice(request)

    async def list_invoices(
        self, pending_only: bool = False, reversed: bool = False
    ) -> list:
        """List all invoices.

        Args:
            pending_only: Only return pending invoices
            reversed: Return in reverse chronological order

        Returns:
            List of Invoice objects
        """
        request = lightning_pb2.ListInvoiceRequest(
            pending_only=pending_only,
            reversed=reversed,
        )
        response = await self.lightning.ListInvoices(request)
        return list(response.invoices)

    async def send_payment_sync(self, payment_request: str) -> lightning_pb2.SendResponse:
        """Pay a lightning invoice synchronously.

        Args:
            payment_request: BOLT11 payment request string

        Returns:
            SendResponse with payment details
        """
        request = lightning_pb2.SendRequest(payment_request=payment_request)
        return await self.lightning.SendPaymentSync(request)

    async def list_payments(self, include_incomplete: bool = False) -> list:
        """List all outgoing payments.

        Args:
            include_incomplete: Include in-flight payments

        Returns:
            List of Payment objects
        """
        request = lightning_pb2.ListPaymentsRequest(
            include_incomplete=include_incomplete,
        )
        response = await self.lightning.ListPayments(request)
        return list(response.payments)

    async def list_channels(self, active_only: bool = False) -> list:
        """List all channels.

        Args:
            active_only: Only return active channels

        Returns:
            List of Channel objects
        """
        request = lightning_pb2.ListChannelsRequest(active_only=active_only)
        response = await self.lightning.ListChannels(request)
        return list(response.channels)

    async def pending_channels(self):
        """Get all pending channels (opening, closing, force-closing).

        Returns:
            PendingChannelsResponse with pending_open, pending_closing, etc.
        """
        return await self.lightning.PendingChannels(lightning_pb2.PendingChannelsRequest())

    async def open_channel_sync(
        self, node_pubkey: str, local_funding_amount: int,
        push_sat: int = 0, private: bool = False,
    ) -> lightning_pb2.ChannelPoint:
        """Open a channel synchronously.

        Args:
            node_pubkey: Remote node's public key (hex string)
            local_funding_amount: Amount in satoshis for our side
            push_sat: Amount to push to remote side
            private: If True, channel is not announced to the network

        Returns:
            ChannelPoint identifying the new channel
        """
        request = lightning_pb2.OpenChannelRequest(
            node_pubkey=bytes.fromhex(node_pubkey),
            local_funding_amount=local_funding_amount,
            push_sat=push_sat,
            private=private,
        )
        return await self.lightning.OpenChannelSync(request)

    async def close_channel(self, channel_point_str: str, force: bool = False):
        """Close a channel.

        Args:
            channel_point_str: Channel point in format "txid:output_index"
            force: Force close the channel

        Returns:
            Async iterator of CloseStatusUpdate messages
        """
        parts = channel_point_str.split(":")
        funding_txid = parts[0]
        output_index = int(parts[1]) if len(parts) > 1 else 0
        channel_point = lightning_pb2.ChannelPoint(
            funding_txid_str=funding_txid,
            output_index=output_index,
        )
        request = lightning_pb2.CloseChannelRequest(
            channel_point=channel_point,
            force=force,
        )
        return self.lightning.CloseChannel(request)

    async def connect_peer(self, pubkey: str, host: str) -> None:
        """Connect to a lightning network peer.

        Args:
            pubkey: Remote node's public key (hex)
            host: Remote node's address (host:port)
        """
        addr = lightning_pb2.LightningAddress(pubkey=pubkey, host=host)
        request = lightning_pb2.ConnectPeerRequest(addr=addr)
        await self.lightning.ConnectPeer(request)

    async def list_peers(self) -> list:
        """List connected peers."""
        response = await self.lightning.ListPeers(lightning_pb2.ListPeersRequest())
        return list(response.peers)

    async def list_unspent(self, min_confs: int = 0, max_confs: int = 2147483647) -> list:
        """List unspent transaction outputs.

        Args:
            min_confs: Minimum confirmations
            max_confs: Maximum confirmations

        Returns:
            List of Utxo objects
        """
        request = lightning_pb2.ListUnspentRequest(
            min_confs=min_confs,
            max_confs=max_confs,
        )
        response = await self.lightning.ListUnspent(request)
        return list(response.utxos)

    async def decode_pay_req(self, pay_req: str) -> lightning_pb2.PayReq:
        """Decode a BOLT11 payment request.

        Args:
            pay_req: BOLT11 encoded payment request

        Returns:
            Decoded payment request details
        """
        request = lightning_pb2.PayReqString(pay_req=pay_req)
        return await self.lightning.DecodePayReq(request)

    async def describe_graph(self) -> lightning_pb2.ChannelGraph:
        """Get the network graph."""
        return await self.lightning.DescribeGraph(
            lightning_pb2.ChannelGraphRequest(include_unannounced=False)
        )

    async def forwarding_history(self, start_time: int = 0, end_time: int = 0,
                                 num_max_events: int = 50000) -> list:
        """Get forwarding history (routed payments).

        Returns:
            List of ForwardingEvent objects
        """
        request = lightning_pb2.ForwardingHistoryRequest(
            start_time=start_time,
            end_time=end_time,
            num_max_events=num_max_events,
        )
        response = await self.lightning.ForwardingHistory(request)
        return list(response.forwarding_events)

    async def fee_report(self) -> list:
        """Get per-channel fee schedule.

        Returns:
            List of ChannelFeeReport objects
        """
        response = await self.lightning.FeeReport(lightning_pb2.FeeReportRequest())
        return list(response.channel_fees)

    # -------------------------------------------------------------------------
    # WalletKit service methods
    # -------------------------------------------------------------------------

    async def estimate_fee(self, conf_target: int = 6) -> int:
        """Estimate on-chain fee rate.

        Args:
            conf_target: Target number of blocks for confirmation

        Returns:
            Fee rate in sat/kw (satoshis per kilo-weight)
        """
        request = walletkit_pb2.EstimateFeeRequest(conf_target=conf_target)
        response = await self.wallet_kit.EstimateFee(request)
        return response.sat_per_kw

    async def publish_transaction(self, tx_hex: bytes) -> str:
        """Publish a raw transaction to the network.

        Args:
            tx_hex: Raw transaction bytes

        Returns:
            Error string (empty on success)
        """
        request = walletkit_pb2.Transaction(tx_hex=tx_hex)
        response = await self.wallet_kit.PublishTransaction(request)
        return response.publish_error

    async def finalize_psbt(self, funded_psbt: bytes) -> tuple[bytes, bytes]:
        """Finalize a PSBT and extract the final raw transaction.

        Args:
            funded_psbt: Funded PSBT bytes

        Returns:
            Tuple of (signed_psbt, raw_final_tx)
        """
        request = walletkit_pb2.FinalizePsbtRequest(funded_psbt=funded_psbt)
        response = await self.wallet_kit.FinalizePsbt(request)
        return response.signed_psbt, response.raw_final_tx

    # -------------------------------------------------------------------------
    # Invoices service methods (for hold invoices and cancellation)
    # -------------------------------------------------------------------------

    async def cancel_invoice(self, payment_hash: bytes) -> None:
        """Cancel an open invoice.

        Args:
            payment_hash: The payment hash of the invoice to cancel
        """
        request = invoices_pb2.CancelInvoiceMsg(payment_hash=payment_hash)
        await self.invoices_rpc.CancelInvoice(request)

    # -------------------------------------------------------------------------
    # Router service methods
    # -------------------------------------------------------------------------

    async def send_payment_v2(self, payment_request: str, timeout_seconds: int = 60):
        """Send a payment using the Router's SendPaymentV2 (streaming).

        Args:
            payment_request: BOLT11 payment request
            timeout_seconds: Payment timeout

        Returns:
            Async iterator of payment status updates
        """
        request = router_pb2.SendPaymentRequest(
            payment_request=payment_request,
            timeout_seconds=timeout_seconds,
            fee_limit_sat=1000000,  # generous default, can be parameterized later
        )
        return self.router.SendPaymentV2(request)

    # -------------------------------------------------------------------------
    # Streaming subscription methods (return async iterators)
    # -------------------------------------------------------------------------

    def subscribe_invoices(self):
        """Subscribe to invoice updates.

        Returns:
            Async iterator of Invoice objects
        """
        return self.lightning.SubscribeInvoices(lightning_pb2.InvoiceSubscription())

    def subscribe_transactions(self):
        """Subscribe to on-chain transaction updates.

        Returns:
            Async iterator of Transaction objects
        """
        return self.lightning.SubscribeTransactions(lightning_pb2.GetTransactionsRequest())

    def subscribe_channel_events(self):
        """Subscribe to channel state change events.

        Returns:
            Async iterator of ChannelEventUpdate objects
        """
        return self.lightning.SubscribeChannelEvents(lightning_pb2.ChannelEventSubscription())

    def register_block_epoch(self):
        """Subscribe to new block notifications.

        Returns:
            Async iterator of BlockEpoch objects (height + hash)
        """
        return self.chain_notifier.RegisterBlockEpochNtfn(
            chainnotifier_pb2.BlockEpoch()
        )
