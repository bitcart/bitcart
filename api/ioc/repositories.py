from dishka import Provider, Scope, provide_all

from api.services.crud.repositories import (
    DiscountRepository,
    FileRepository,
    InvoiceRepository,
    NotificationRepository,
    PaymentMethodRepository,
    PayoutRepository,
    ProductRepository,
    RefundRepository,
    SettingRepository,
    StoreRepository,
    TemplateRepository,
    TokenRepository,
    UserRepository,
    WalletRepository,
)


class RepositoriesProvider(Provider):
    provides = provide_all(
        UserRepository,
        WalletRepository,
        NotificationRepository,
        TemplateRepository,
        StoreRepository,
        DiscountRepository,
        ProductRepository,
        TokenRepository,
        PaymentMethodRepository,
        InvoiceRepository,
        PayoutRepository,
        SettingRepository,
        FileRepository,
        RefundRepository,
        scope=Scope.SESSION,
    )
