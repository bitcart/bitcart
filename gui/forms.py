from django import forms
from django.conf import settings
from . import models

class StoreForm(forms.ModelForm):

    class Meta:
        model = models.Store
        fields = ("name","wallet","domain","template","email")

    def __init__(self,*args, **kwargs):
        super().__init__(*args, **kwargs)
        for visible in self.visible_fields():
            visible.field.widget.attrs['class'] = 'form-control'
        #self.fields["wallet"].widget.attrs['class'] = 'form-check'
        #self.fields["id"].widget.attrs["readonly"]=True

class UpdateStoreForm(forms.ModelForm):

    class Meta:
        model = models.Store
        fields = ("name","wallet","domain","template","email")

    def __init__(self,*args, **kwargs):
        super().__init__(*args, **kwargs)
        for visible in self.visible_fields():
            visible.field.widget.attrs['class'] = 'form-control'
            #visible.field.required=False
        #print(self.visible_fields())
        #self.fields["wallet"].widget.attrs['class'] = 'form-check'
        #self.fields["id"].widget.attrs["readonly"]=True
        
class ProductForm(forms.ModelForm):

    class Meta:
        model = models.Product
        fields = ("amount","quantity","title","description","order_id","image","video","store")

class CreateStoreForm(forms.Form):
    name=forms.CharField(max_length=255,widget=forms.TextInput(attrs={"class":"form-control"}))

class RegisterForm(forms.ModelForm):
    confirm_password = forms.CharField(max_length=255,widget=forms.PasswordInput())
    class Meta:
        model = models.User
        fields = ("username","email","password")
        widgets={
        "confirm_password":forms.PasswordInput(),
        "password":forms.PasswordInput()
    }
    
    def __init__(self,*args, **kwargs):
        super().__init__(*args, **kwargs)
        for visible in self.visible_fields():
            visible.field.widget.attrs['class'] = 'form-control'

class LoginForm(forms.Form):
    username = forms.CharField(max_length=255)
    password = forms.CharField(max_length=255,widget=forms.PasswordInput())
    class Meta:
        fields = ("username","password")
        widgets={
        "password":forms.PasswordInput()
    }

    def __init__(self,*args, **kwargs):
        super().__init__(*args, **kwargs)
        for visible in self.visible_fields():
            visible.field.widget.attrs['class'] = 'form-control'

class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(max_length=255,widget=forms.PasswordInput())
    new_password = forms.CharField(max_length=255,widget=forms.PasswordInput())
    confirm_password = forms.CharField(max_length=255,widget=forms.PasswordInput())
    class Meta:
        widgets={
        "old_password":forms.PasswordInput(),
        "new_password":forms.PasswordInput(),
        "confirm_password":forms.PasswordInput()
    }

    def __init__(self,*args, **kwargs):
        super().__init__(*args, **kwargs)
        for visible in self.visible_fields():
            visible.field.widget.attrs['class'] = 'form-control'

class WalletForm(forms.ModelForm):

    class Meta:
        model = models.Wallet
        fields = ("name","xpub")
