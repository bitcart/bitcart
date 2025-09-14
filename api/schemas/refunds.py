from api.schemas.base import DecimalAsFloat, MetadataInput, MetadataOutput, Schema, TimestampedSchema


class CreateRefund(MetadataInput):
    amount: DecimalAsFloat
    currency: str
    wallet_id: str
    invoice_id: str


class UpdateRefund(CreateRefund):
    pass


class DisplayRefund(MetadataOutput, CreateRefund, TimestampedSchema):
    id: str
    user_id: str
    destination: str | None
    wallet_currency: str | None = None  # added at runtime
    payout_id: str | None
    payout_status: str | None = None
    tx_hash: str | None = None


class RefundData(Schema):
    amount: DecimalAsFloat
    currency: str
    admin_host: str  # TODO: remove
    send_email: bool = True


class SubmitRefundData(Schema):
    destination: str
