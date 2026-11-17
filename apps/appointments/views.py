from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from .availability import get_available_slots
from .serializers import AvailabilityQuerySerializer, AvailabilitySerializer


class AvailabilityView(APIView):
    """Horarios disponibles de un peluquero para una fecha y un servicio."""

    @extend_schema(
        tags=["availability"],
        summary="Horarios disponibles",
        parameters=[
            OpenApiParameter("barber", int, description="ID del peluquero"),
            OpenApiParameter("service", int, description="ID del servicio"),
            OpenApiParameter("date", str, description="Fecha en formato YYYY-MM-DD"),
        ],
        responses=AvailabilitySerializer,
    )
    def get(self, request):
        query = AvailabilityQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        barber = query.validated_data["barber"]
        service = query.validated_data["service"]
        day = query.validated_data["date"]

        slots = get_available_slots(barber, day, service)
        payload = {
            "barber": barber.id,
            "service": service.id,
            "date": day,
            "slots": [{"start": s, "end": e} for s, e in slots],
        }
        return Response(AvailabilitySerializer(payload).data)
