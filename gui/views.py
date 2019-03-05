#pylint: disable=no-member
from django.shortcuts import render,get_object_or_404,redirect,reverse
from django.conf import settings
from . import models, forms, tasks
from django import forms as django_forms
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login as django_login,logout as django_logout
from django.contrib.auth.decorators import login_required
import csv
import time
import io
from datetime import datetime, timedelta
from bitcart.coins.btc import BTC
import secrets
try:
    import ujson as json
except:
    import json

RPC_USER=settings.RPC_USER
RPC_PASS=settings.RPC_PASS

RPC_URL=settings.RPC_URL

btc=BTC(RPC_URL)

# Create your views here.

def main(request):
    return render(request,"gui/main.html",{})

@login_required
def stores(request):
    t=models.Store.objects.all()
    t=t.filter(user=request.user)
    return render(request,"gui/stores.html",{"t":t})

@login_required
def store_settings(request,store):
    model=get_object_or_404(models.Store,id=store)
    if request.method == "POST":
        form = forms.StoreForm(request.POST, instance=model)
        print(form.errors)
        if form.is_valid():
            form.save()
            return redirect(reverse('store_settings', kwargs={"store":store})+"?ok=True")
        else:
            return redirect(reverse('store_settings', kwargs={"store":store})+"?ok=False")
    else:
        fee_text=""
        ok=request.GET.get("ok",False)
        if model.fee_mode == 1:
            fee_text="MultiplePaymentsOnly"
        elif model.fee_mode == 2:
            fee_text="Always"
        elif model.fee_mode == 3:
            fee_text="Never"

        form=forms.StoreForm(instance=model)
        return render(request,"gui/store_settings.html",{"model":model,"fee_text":fee_text,"form":form,"is_ok":ok})

def filter_products(p_val,products):
    p={}
    for i in p_val.split():
        stripped=i.split(":")
        if len(stripped) != 2:
            continue
        else:
            try:
                p[stripped[0]].append(stripped[1])
            except KeyError:
                p[stripped[0]]=[stripped[1]]
    store_id=p.get("storeid")
    order_id=p.get("orderid")
    status=p.get("status")
    params={"store":store_id,"order_id":order_id,"status":status}
    kwargs={}
    for i in params:
        if params[i]:
            try:
                kwargs[i+"__in"].update(params[i])
            except KeyError:
                kwargs[i+"__in"]=params[i]
    products=products.filter(**kwargs)
    return products

@login_required
def products(request):
    products=models.Product.objects.all()
    products=products.filter(store__user=request.user)
    products=products.order_by("-date")
    if request.method == "POST":
        p_val=request.POST.get("search_term","")
    else:
        p_val=request.GET.get("search_term","")
    products=filter_products(p_val,products)
    ok=request.GET.get("ok",False)
    return render(request,"gui/products.html",{"products":products,"ok":ok})

def invoice_buy(request,invoice):
    obj=get_object_or_404(models.Product,id=invoice)
    obj_j=json.loads(invoice_status(request,invoice).content)
    '''obj=get_object_or_404(models.Product,id=invoice)
    creation_date=obj.date
    expire_date=creation_date+timedelta(minutes=obj.store.invoice_expire)
    expire_date_seconds=time.mktime(expire_date.timetuple())
    time_passed=time.time()-expire_date_seconds
    if time_passed >= 0:
        expire_at=0
    else:
        expire_at=abs(time_passed)
    time_left="{:02d}:{:02d}".format(*divmod(expire_at*60,60))'''
    return render(request,"gui/invoice_buy.html",{"invoice":obj.id,"address":obj.bitcoin_address,"obj":obj,"obj_j":obj_j,"dumped_j":json.dumps(obj_j)})

@login_required
def product_info(request,product):
    model=get_object_or_404(models.Product,id=product)
    return render(request,"gui/product_info.html",{"product":model})

def get_product_dict(i):
    image=i.image.url if i.image else ""
    data_dict={"id":i.id,
    "amount":i.amount,
    "quantity":i.quantity,
    "title":i.title,
    "status":i.status,
    "order_id":i.order_id,
    "date":i.date,
    "description":i.description,
    "image":image,
    "video":i.video}
    return data_dict

@login_required
def product_export(request):
    format_=request.GET.get("format","json")
    products=models.Product.objects.filter(store__user=request.user)
    lst=[]
        
    if format_ == "json":
        for i in products:
            lst.append(get_product_dict(i))
        return JsonResponse(lst,safe=False)
    elif format_ == "csv":
        result=io.StringIO()
        fieldnames = ['id', 'amount', 'quantity', 'title', 'status', 'order_id', 'date', 'description', 'image', 'video']
        writer = csv.DictWriter(result, fieldnames=fieldnames)
        writer.writeheader()
        for i in products:
            writer.writerow(get_product_dict(i))
        date=datetime.now()
        filename=date.strftime("bitcart-export-%Y%m%d-%H%M%S.csv")
        response = HttpResponse(result.getvalue(), content_type='application/csv')
        response['Content-Type'] = 'application/sv'
        response['Content-Disposition'] = 'attachment; filename='+filename
        return response
    else:
        return render(request,"gui/main.html",{})

@login_required
def create_store(request):
    if request.method == "POST":
        form=forms.CreateStoreForm(request.POST)
        if form.is_valid():
            if request.user.is_authenticated:
                user=request.user
            models.Store().create(name=form.cleaned_data["name"],user=user)
            return redirect("stores")
        else:
            return render(request,"gui/create_store.html",{"form":form})
    else:
        form=forms.CreateStoreForm()
        return render(request,"gui/create_store.html",{"form":form})

@login_required
def delete_store(request, store):
    if request.method == "POST":
        obj=get_object_or_404(models.Store,id=store)
        obj.delete()
        return redirect("stores")
    else:
        return render(request,"gui/delete_store.html",{"store":store})

def register(request):
    if request.method == "POST":
        form=forms.RegisterForm(request.POST)
        if request.POST.get("password") != request.POST.get("confirm_password"):
            form.add_error("confirm_password","Passwords must match!")
        if form.is_valid():
            User.objects.create_user(request.POST.get("username"),request.POST.get("email"),request.POST.get("password"))
            return redirect("main")
        else:
            print(form.errors)
            #form.add_error("confirm_password","Passwords must match!")
            return render(request,"gui/register.html",{"form":form})
        
    else:
        form=forms.RegisterForm()
        return render(request,"gui/register.html",{"form":form})

def login(request):
    if request.method == "POST":
        form=forms.LoginForm(request.POST)
        remember_me=request.POST.get("remember_me",False)
        if form.is_valid():
            print('y')
            user = authenticate(request, username=request.POST.get("username"), password=request.POST.get("password"))
            print(user)
            if user is not None:
                django_login(request, user)
                if not remember_me:
                    request.session.set_expiry(0)
                redirect_to=request.POST.get("redirect_to","account_settings")
                if not redirect_to:
                    redirect_to="account_settings"
                print(redirect_to)
                print(request.GET)
                print(request.POST)
                return redirect(redirect_to)
            else:
                print(form)
                return render(request,"gui/login.html",{"form":form,"error":True})
            
        else:
            print(form.errors)
            return render(request,"gui/login.html",{"form":form,"error":False})
    else:
        redirect_to=request.GET.get("next","account_settings")
        form=forms.LoginForm()
        return render(request,"gui/login.html",{"form":form,"error":False,"redirect_to":redirect_to})

@login_required
def logout(request):
    django_logout(request)
    return redirect("main")

@login_required
def account_settings(request):
    if request.method == "POST":
        email=request.POST.get("email")
        user=request.user
        user.email=email
        user.save()
        return redirect(reverse("account_settings")+"?ok=true")
    else:
        ok=request.GET.get("ok",False)
        return render(request,"gui/account_settings.html",{"ok":ok})

@login_required
def change_password(request):
    if request.method == "POST":
        form=forms.ChangePasswordForm(request.POST)
        user=request.user
        if not user.check_password(request.POST.get("old_password")):
            form.add_error("old_password","Invalid password!")
        if request.POST.get("new_password") != request.POST.get("confirm_password"):
            form.add_error("confirm_password","Passwords must match!")
        if form.is_valid():
            user.set_password(request.POST.get("new_password"))
            user.save()
            return redirect("main")
        else:
            return render(request,"gui/change_password.html",{"form":form})
    form=forms.ChangePasswordForm()
    return render(request,"gui/change_password.html",{"form":form})

@login_required
def wallets(request):
    stores=models.Store.objects.all()
    stores=stores.filter(user=request.user)
    stores=stores.exclude(xpub__exact="")
    for i in stores:
        i.balance=BTC(RPC_URL,xpub=i.xpub, rpc_user=RPC_USER, rpc_pass=RPC_PASS).balance()['confirmed']
    return render(request,"gui/wallets.html",{"stores":stores})

@login_required
def apps(request):
    return render(request,"gui/apps.html",{})

@login_required
def wallet_history(request,wallet):
    model=get_object_or_404(models.Store,id=wallet)
    transactions=BTC(RPC_URL,xpub=model.xpub, rpc_user=RPC_USER, rpc_pass=RPC_PASS).server.history()["transactions"]
    return render(request,"gui/wallet_history.html",{"model":model,"transactions":transactions})

def locales(request,path):
    from django.views.static import serve
    return serve(request, path,show_indexes=True)

@login_required
def create_product(request):
    if request.method == "POST":
        form=forms.ProductForm(request.POST)
        if form.is_valid():
            form=form.save(commit=False)
            form.id=secrets.token_urlsafe(22)
            form.status="new"
            data_got=BTC(RPC_URL, xpub=form.store.xpub, rpc_user=RPC_USER, rpc_pass=RPC_PASS).addrequest(form.amount, description=form.description, expire=form.store.invoice_expire)
            print(data_got)
            form.bitcoin_address=data_got["address"]
            form.bitcoin_url=data_got["URI"]
            form.save()
            tasks.poll_updates.delay(form.id)
            return redirect(reverse("products")+"?ok=true")
        else:
            return render(request,"gui/create_product.html",{"form":form})
    else:
        form=forms.ProductForm()
        form.fields["store"].queryset=models.Store.objects.filter(user=request.user)
        return render(request,"gui/create_product.html",{"form":form})

def invoice_status(request,invoice):
    obj=get_object_or_404(models.Product,id=invoice)
    creation_date=obj.date
    expire_date=creation_date+timedelta(minutes=obj.store.invoice_expire)
    expire_date_seconds=time.mktime(expire_date.timetuple())
    time_passed=time.time()-expire_date_seconds
    if time_passed >= 0:
        expire_at=0
    else:
        expire_at=abs(time_passed)
    response_json={"availableCryptos": [{"cryptoCode": "BTC",
                       "cryptoImage": "/imlegacy/bitcoin.svg",
                       "isLightning": False,
                       "link": "/i/{}/BTC".format(obj.id),
                       "paymentMethodId": "BTC",
                       "paymentMethodName": "Bitcoin"}],
 "btcAddress": obj.bitcoin_address,
 "btcDue": obj.amount,
 "btcPaid": "0.00000000" if obj.status != "completed" else obj.amount,
 "changellyAmountDue": None,
 "changellyEnabled": False,
 "changellyMerchantId": None,
 "coinSwitchEnabled": False,
 "coinSwitchMerchantId": None,
 "coinSwitchMode": None,
 "cryptoCode": "BTC",
 "cryptoImage": "/imlegacy/bitcoin.svg",
 "customCSSLink": None,
 "customLogoLink": None,
 "customerEmail": None,
 "defaultLang": "en",
 "expirationSeconds": expire_at,
 "htmlTitle": "Bitcart Invoice",
 "invoiceBitcoinUrl": obj.bitcoin_url,
 "invoiceBitcoinUrlQR": obj.bitcoin_url,
 "invoiceId": obj.id,
 "isLightning": False,
 "isModal": False,
 "isMultiCurrency": False,
 "itemDesc": obj.description,
 "maxTimeMinutes": obj.store.invoice_expire,
 "maxTimeSeconds": obj.store.invoice_expire*60,
 "merchantRefLink": None,
 "networkFee": 0.0,
 "orderAmount": obj.amount,
 "orderAmountFiat": None,
 "orderId": obj.order_id,
 "paymentMethodId": "BTC",
 "paymentMethodName": "Bitcoin",
 "paymentType": None,
 "peerInfo": None,
 "rate": "1.00000000 BTC",
 "requiresRefundEmail": False,
 "status": obj.status,
 "storeEmail": None,
 "storeId": obj.store.id,
 "storeName": obj.store.name,
 "timeLeft": "{:02d}:{:02d}".format(*divmod(int(expire_at),60)),
 "txCount": 1}
    return JsonResponse(response_json)
