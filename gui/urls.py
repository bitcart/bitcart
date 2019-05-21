from django.contrib import admin
from django.urls import path, include
from django.contrib.staticfiles.urls import static, staticfiles_urlpatterns
from django.conf import settings
from rest_framework import routers
from rest_framework.authtoken import views as rest_views
from rest_framework.documentation import include_docs_urls
from django.views.static import serve
from . import views
from . import api
from two_factor.urls import urlpatterns as tf_urls
from rest_framework.urlpatterns import format_suffix_patterns


router = routers.DefaultRouter()
router.register('product', api.ProductViewSet)
router.register('store', api.StoreViewSet)
router.register('wallet', api.WalletViewSet)

urlpatterns = [
    path("", views.main, name="main"),
    path("", include(tf_urls)),
    path("stores/", views.stores, name="stores"),
    path("stores/<store>/delete/", views.delete_store, name="delete_store"),
    path("products/", views.products, name="products"),
    path("products/export/", views.product_export, name="product_export"),
    path("account/register/", views.register, name="register"),
    path("account/login/", views.login, name="login"),
    path("logout/", views.logout, name='logout'),
    path("account/settings/", views.account_settings, name="account_settings"),
    path(
        "account/change_password/",
        views.change_password,
        name="change_password"),
    path("wallets/", views.wallets, name="wallets"),
    path(
        "wallets/<wallet>/delete/",
        views.delete_wallet,
        name="delete_wallet"),
    path("wallets/<wallet>/", views.wallet_history, name="wallet_history"),
    path("i/<invoice>/status/", views.invoice_status, name="invoice_status"),

]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls))
    ]


urlpatterns += staticfiles_urlpatterns()
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += (
    # urls for Django Rest Framework API
    path("api/v1/token/", rest_views.obtain_auth_token),
    path('api/v1/', include(router.urls)),
    path('api/v1/rate', api.USDPriceView.as_view()),
    path('api/v1/wallet_history/<wallet>', api.WalletHistoryView.as_view()),
    path('api/docs', include_docs_urls(title="Bitcart docs"))
)

#urlpatterns = format_suffix_patterns(urlpatterns)
