# pylint: disable=no-member
from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.conf import settings
from django.core.mail import send_mail
from . import models, forms, tasks
from django import forms as django_forms
from django.http import JsonResponse, HttpResponse
from .models import User
import decimal
from django.contrib.auth import authenticate, login as django_login, logout as django_logout
from django.contrib.auth.decorators import login_required
import csv
import time
import io
from datetime import datetime, timedelta
from bitcart.coins.btc import BTC
import secrets

try:
    import ujson as json
except BaseException:
    import json

RPC_USER = settings.RPC_USER
RPC_PASS = settings.RPC_PASS

RPC_URL = settings.RPC_URL

btc = BTC(RPC_URL)


# misc
def truncate(text: str, chars: int, endchar=".."):
    return (text[:chars] + endchar) if len(text) > chars else text


# Create your views here.
@login_required
def main(request):
    return render(request, "gui/main.html",
                  {"main_active": "active", "setting_active": "", })


@login_required
def stores(request):
    if request.method == "POST":
        form = forms.StoreForm(json.loads(request.body))
        form.fields["wallet"].queryset = models.Wallet.objects.filter(
            user=request.user)
        if form.is_valid():
            form = form.save(commit=False)
            form.id = secrets.token_urlsafe(32)
            form.save()
            return JsonResponse({"id": form.id})
        else:
            return render(request, "gui/stores.html", {"form": form})
    else:
        stores = models.Store.objects.select_related(
            "wallet").filter(wallet__user=request.user)
        form = forms.StoreForm()
        form.fields["wallet"].queryset = models.Wallet.objects.filter(
            user=request.user)
        return render(request, "gui/stores.html",
                      {"stores": stores, "stores_active": True, "form": form})


def filter_products(p_val, products):
    p = {}
    for i in p_val.split():
        stripped = i.split(":")
        if len(stripped) != 2:
            continue
        else:
            try:
                p[stripped[0]].append(stripped[1])
            except KeyError:
                p[stripped[0]] = [stripped[1]]
    store_id = p.get("storeid")
    order_id = p.get("orderid")
    status = p.get("status")
    params = {"store": store_id, "order_id": order_id, "status": status}
    kwargs = {}
    for i in params:
        if params[i]:
            try:
                kwargs[i + "__in"].update(params[i])
            except KeyError:
                kwargs[i + "__in"] = params[i]
    products = products.filter(**kwargs)
    return products


@login_required
def products(request):
    ok = request.GET.get("ok", False)
    form = forms.ProductForm()
    form.fields["store"].queryset = models.Store.objects.filter(
        wallet__user=request.user)
    return render(request, "gui/products.html",
                  {"ok": ok, "products_active": True, "form": form})


def get_product_dict(i):
    image = i.image.url if i.image else ""
    data_dict = {"id": i.id,
                 "amount": i.amount,
                 "quantity": i.quantity,
                 "title": i.title,
                 "status": i.status,
                 "order_id": i.order_id,
                 "date": i.date,
                 "description": i.description,
                 "image": image}
    return data_dict


@login_required
def product_export(request):
    format_ = request.GET.get("format", "json")
    products = models.Product.objects.filter(store__wallet__user=request.user)
    lst = []

    if format_ == "json":
        for i in products:
            lst.append(get_product_dict(i))
        return JsonResponse(lst, safe=False)
    elif format_ == "csv":
        result = io.StringIO()
        fieldnames = [
            'id',
            'amount',
            'quantity',
            'title',
            'status',
            'order_id',
            'date',
            'description',
            'image']
        writer = csv.DictWriter(result, fieldnames=fieldnames)
        writer.writeheader()
        for i in products:
            writer.writerow(get_product_dict(i))
        date = datetime.now()
        filename = date.strftime("bitcart-export-%Y%m%d-%H%M%S.csv")
        response = HttpResponse(
            result.getvalue(),
            content_type='application/csv')
        response['Content-Type'] = 'application/sv'
        response['Content-Disposition'] = 'attachment; filename=' + filename
        return response
    else:
        return render(request, "gui/main.html", {})


@login_required
def delete_store(request, store):
    if request.method == "POST":
        obj = get_object_or_404(models.Store, id=store)
        obj.delete()
        return redirect("stores")
    else:
        return render(request, "gui/delete_store.html", {"store": store})


def register(request):
    if request.method == "POST":
        form = forms.RegisterForm(request.POST)
        if request.POST.get("password") != request.POST.get(
                "confirm_password"):
            form.add_error("confirm_password", "Passwords must match!")
        if form.is_valid():
            User.objects.create_user(request.POST.get("username"), request.POST.get("email"),
                                     request.POST.get("password"))
            return redirect("main")
        else:
            return render(request, "gui/register.html", {"form": form})

    else:
        form = forms.RegisterForm()
        return render(request, "gui/register.html", {"form": form})


def login(request):
    if request.method == "POST":
        form = forms.LoginForm(request.POST)
        remember_me = request.POST.get("remember_me", False)
        if form.is_valid():
            user = authenticate(request, username=request.POST.get(
                "username"), password=request.POST.get("password"))
            if user is not None:
                django_login(request, user)
                if not remember_me:
                    request.session.set_expiry(0)
                redirect_to = request.POST.get(
                    "redirect_to", "account_settings")
                if not redirect_to:
                    redirect_to = "account_settings"
                return redirect(redirect_to)
            else:
                return render(request, "gui/login.html",
                              {"form": form, "error": True})

        else:
            return render(request, "gui/login.html",
                          {"form": form, "error": False})
    else:
        redirect_to = request.GET.get("next", "account_settings")
        form = forms.LoginForm()
        return render(request, "gui/login.html",
                      {"form": form, "error": False, "redirect_to": redirect_to})


@login_required
def logout(request):
    django_logout(request)
    return redirect("main")


@login_required
def account_settings(request):
    if request.method == "POST":
        email = request.POST.get("email")
        user = request.user
        user.email = email
        user.save()
        return redirect(reverse("account_settings") + "?ok=true")
    else:
        ok = request.GET.get("ok", False)
        return render(request, "gui/account_settings.html",
                      {"ok": ok, "main_active": "", "setting_active": "active"})


@login_required
def change_password(request):
    if request.method == "POST":
        form = forms.ChangePasswordForm(request.POST)
        user = request.user
        if not user.check_password(request.POST.get("old_password")):
            form.add_error("old_password", "Invalid password!")
        if request.POST.get("new_password") != request.POST.get(
                "confirm_password"):
            form.add_error("confirm_password", "Passwords must match!")
        if form.is_valid():
            user.set_password(request.POST.get("new_password"))
            user.save()
            return redirect("main")
        else:
            return render(request, "gui/change_password.html", {"form": form})
    form = forms.ChangePasswordForm()
    return render(request, "gui/change_password.html", {"form": form})


@login_required
def wallets(request):
    ok = request.GET.get("ok", False)
    return render(request, "gui/wallets.html",
                  {"success": ok, "wallets_active": True})


@login_required
def wallet_history(request, wallet):
    model = get_object_or_404(models.Wallet, id=wallet)
    transactions = BTC(
        RPC_URL,
        xpub=model.xpub,
        rpc_user=RPC_USER,
        rpc_pass=RPC_PASS).server.history()["transactions"]
    return render(request, "gui/wallet_history.html",
                  {"model": model, "transactions": transactions})


@login_required
def delete_wallet(request, wallet):
    obj = get_object_or_404(models.Wallet, id=wallet)
    if request.method == "POST":
        obj.delete()
        return redirect("wallets")
    else:
        return render(request, "gui/delete_wallet.html", {"wallet": wallet})


def invoice_status(request, invoice):
    get_object_or_404(models.Product, id=invoice)
    response_json = {}
    return JsonResponse(response_json)
