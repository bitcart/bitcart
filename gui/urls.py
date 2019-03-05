from django.contrib import admin
from django.urls import path,include
from django.contrib.staticfiles.urls import static,staticfiles_urlpatterns
from django.conf import settings
from rest_framework import routers
from rest_framework.authtoken import views as rest_views
from rest_framework.documentation import include_docs_urls
from django.views.static import serve
from . import views
from . import api


router = routers.DefaultRouter()
router.register('product', api.ProductViewSet)
router.register('store', api.StoreViewSet)

urlpatterns = [
    path("",views.main,name="main"),
    path("stores/",views.stores,name="stores"),
    path("stores/create/",views.create_store,name="create_store"),
    path("stores/<store>/",views.store_settings,name="store_settings"),
    path("stores/<store>/delete/",views.delete_store,name="delete_store"),
    path("products/",views.products,name="products"),
    path("i/<invoice>/",views.invoice_buy,name="invoice_buy"),
    path("products/export/",views.product_export,name="product_export"),
    path("products/create/",views.create_product,name="create_product"),
    path("products/<product>/",views.product_info,name="product_info"),
    path("account/register/",views.register,name="register"),
    path("account/login/",views.login,name="login"),
    path("logout/",views.logout,name='logout'),
    path("account/settings/",views.account_settings,name="account_settings"),
    path("account/change_password/",views.change_password,name="change_password"),
    path("wallets/",views.wallets,name="wallets"),
    path("apps/",views.apps,name="apps"),
    path("wallets/<wallet>/",views.wallet_history,name="wallet_history"),
    path("locales/<path>/",serve,{"document_root":"gui/locales"}),
    path("i/<invoice>/status/",views.invoice_status,name="invoice_status")
]


urlpatterns += staticfiles_urlpatterns()
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += (
    # urls for Django Rest Framework API
    path("api/v1/token/", rest_views.obtain_auth_token),
    path('api/v1/', include(router.urls)),
    path('api/docs', include_docs_urls(title="Bitcart docs"))
)
