from rest_framework import serializers

from .models import Barbero, Reserva, Servicio


class BarberoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Barbero
        fields = [
            "id",
            "nombre",
            "rol",
            "especialidad",
            "avatar_url",
            "activo",
        ]


class ServicioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Servicio
        fields = [
            "id",
            "nombre",
            "precio",
            "duracion_minutos",
            "descripcion",
            "categoria",
            "es_combo",
            "activo",
        ]


class ReservaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reserva
        fields = [
            "id",
            "barbero",
            "servicio",
            "cliente_nombre",
            "cliente_telefono",
            "cliente_email",
            "fecha",
            "hora",
            "estado",
            "creado_en",
        ]
        read_only_fields = ["id", "creado_en"]

    def get_unique_together_validators(self):
        # DRF genera automaticamente un validador Python a partir del
        # UniqueConstraint del modelo, lo que devolveria un 400 ANTES de
        # tocar la base de datos -- reintroduciendo la misma condicion de
        # carrera que el constraint de BD existe para evitar. Se desactiva
        # a proposito: la garantia real vive en el IntegrityError que
        # captura ReservaViewSet.create() y responde 409.
        return []


class ReservaUpdateEstadoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reserva
        fields = ["estado"]
