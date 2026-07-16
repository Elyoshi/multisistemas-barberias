from django.db import models


class Barbero(models.Model):
    nombre = models.CharField(max_length=100)
    rol = models.CharField(max_length=100, blank=True)
    especialidad = models.TextField(blank=True)
    avatar_url = models.URLField(blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Servicio(models.Model):
    nombre = models.CharField(max_length=150)
    precio = models.PositiveIntegerField()  # CLP, sin decimales
    duracion_minutos = models.PositiveIntegerField()
    descripcion = models.TextField(blank=True)
    categoria = models.CharField(max_length=50, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Reserva(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        CONFIRMADA = "confirmada", "Confirmada"
        COMPLETADA = "completada", "Completada"
        CANCELADA = "cancelada", "Cancelada"

    barbero = models.ForeignKey(Barbero, on_delete=models.PROTECT, related_name="reservas")
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, related_name="reservas")
    cliente_nombre = models.CharField(max_length=150)
    cliente_telefono = models.CharField(max_length=30)
    cliente_email = models.EmailField(blank=True)
    fecha = models.DateField()
    hora = models.TimeField()
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-hora"]
        constraints = [
            # Anti doble-reserva a nivel de base de datos: dos requests
            # simultaneos pueden pasar la validacion de Python al mismo tiempo,
            # asi que la garantia real tiene que vivir en el constraint de BD.
            # Una reserva cancelada no bloquea el horario para otro cliente.
            models.UniqueConstraint(
                fields=["barbero", "fecha", "hora"],
                condition=~models.Q(estado="cancelada"),
                name="unique_barbero_fecha_hora_activa",
            )
        ]

    def __str__(self):
        return f"{self.cliente_nombre} - {self.fecha} {self.hora} ({self.estado})"
