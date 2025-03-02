from django.shortcuts import render
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponseRedirect, JsonResponse, HttpResponse
from .models import *
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.core.exceptions import ValidationError
import json
import threading

# Create your views here.
def home(request):
    return render(request, 'home.html')

def start(request):
    return render(request, 'challenge_start.html')