
import os
import requests

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


API_URL = os.environ.get("API_URL", "http://api:5000").rstrip("/")


@csrf_exempt
@require_http_methods(["GET", "POST", "PUT", "DELETE"])
def api_proxy(request, endpoint):
    url = f"{API_URL}/api/{endpoint}"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        response = requests.request(
            method=request.method,
            url=url,
            headers=headers,
            params=request.GET,
            data=request.body,
            timeout=15,
            allow_redirects=False,
        )

        return HttpResponse(
            content=response.content,
            status=response.status_code,
            content_type=response.headers.get(
                "Content-Type", "application/json"
            ),
        )

    except requests.exceptions.RequestException:
        return JsonResponse(
            {
                "error": "No se pudo conectar con la API Flask."
            },
            status=503,
        )
