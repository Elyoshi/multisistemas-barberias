from django.core.management.base import BaseCommand

from reservas.models import Barbero, Servicio

# Placeholders para poder probar el flujo de reserva de punta a punta antes de
# tener los datos reales de la barberia. NO son los mismos nombres/precios que
# el mock de frontend/js/api.js a proposito -- eso evita confundirlos con
# datos "de verdad". Reemplazar via Django Admin (o editando este archivo)
# antes de considerar el ambiente listo para produccion.
BARBEROS_PLACEHOLDER = [
    {
        "nombre": "[PLACEHOLDER] Barbero 1",
        "rol": "Editar en /admin",
        "especialidad": "Reemplazar con la especialidad real",
        "avatar_url": "",
    },
    {
        "nombre": "[PLACEHOLDER] Barbero 2",
        "rol": "Editar en /admin",
        "especialidad": "Reemplazar con la especialidad real",
        "avatar_url": "",
    },
]

SERVICIOS_PLACEHOLDER = [
    {
        "nombre": "[PLACEHOLDER] Corte",
        "precio": 1,
        "duracion_minutos": 30,
        "descripcion": "Reemplazar con la descripcion y precio real",
        "categoria": "corte",
    },
    {
        "nombre": "[PLACEHOLDER] Barba",
        "precio": 1,
        "duracion_minutos": 20,
        "descripcion": "Reemplazar con la descripcion y precio real",
        "categoria": "barba",
    },
]


class Command(BaseCommand):
    help = (
        "Crea barberos y servicios PLACEHOLDER para probar el flujo de "
        "reserva localmente. No usar en produccion sin reemplazar los datos "
        "reales via /admin."
    )

    def handle(self, *args, **options):
        if Barbero.objects.exists() or Servicio.objects.exists():
            self.stdout.write(
                self.style.WARNING(
                    "Ya existen barberos o servicios en la base de datos. "
                    "No se sembraron datos placeholder para evitar duplicados."
                )
            )
            return

        for data in BARBEROS_PLACEHOLDER:
            Barbero.objects.create(**data)

        for data in SERVICIOS_PLACEHOLDER:
            Servicio.objects.create(**data)

        self.stdout.write(
            self.style.SUCCESS(
                f"Sembrados {len(BARBEROS_PLACEHOLDER)} barberos y "
                f"{len(SERVICIOS_PLACEHOLDER)} servicios PLACEHOLDER. "
                "Reemplaza estos datos con los reales en /admin antes de "
                "usar este ambiente para algo que no sea pruebas locales."
            )
        )
