"""Sign in with WitUS: three routes under /auth/witus/. The ecosystem's client registry names the
callback path exactly (`/auth/witus/callback/`), and its product list names the login route; the
URL names are what the templates use."""

from django.urls import path

from invest_witus_site.accounts import views

urlpatterns = [
    path("login/", views.login, name="sign-in"),
    path("callback/", views.callback, name="witus-callback"),
    path("logout/", views.logout, name="sign-out"),
]
