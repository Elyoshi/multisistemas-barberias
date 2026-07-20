from django.contrib import admin

from .models import Barbero, BloqueoHorario, DisponibilidadBarbero, Reserva, Servicio


@admin.register(Barbero)
class BarberoAdmin(admin.ModelAdmin):
    list_display = ["nombre", "rol", "activo"]
    list_filter = ["activo"]
    search_fields = ["nombre"]


@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ["nombre", "categoria", "precio", "duracion_minutos", "activo"]
    list_filter = ["categoria", "activo"]
    search_fields = ["nombre"]


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = [
        "cliente_nombre",
        "cliente_telefono",
        "barbero",
        "servicio",
        "fecha",
        "hora",
        "estado",
    ]
    list_filter = ["estado", "fecha", "barbero"]
    search_fields = ["cliente_nombre", "cliente_telefono", "cliente_email"]
    date_hierarchy = "fecha"
    actions = ["marcar_confirmada", "marcar_completada", "marcar_cancelada"]

    @admin.action(description="Marcar seleccionadas como confirmada")
    def marcar_confirmada(self, request, queryset):
        queryset.update(estado=Reserva.Estado.CONFIRMADA)

    @admin.action(description="Marcar seleccionadas como completada")
    def marcar_completada(self, request, queryset):
        queryset.update(estado=Reserva.Estado.COMPLETADA)

    @admin.action(description="Marcar seleccionadas como cancelada")
    def marcar_cancelada(self, request, queryset):
        queryset.update(estado=Reserva.Estado.CANCELADA)


@admin.register(BloqueoHorario)
class BloqueoHorarioAdmin(admin.ModelAdmin):
    list_display = ["barbero", "fecha", "hora_inicio", "hora_fin", "motivo"]
    list_filter = ["fecha", "barbero"]
    date_hierarchy = "fecha"


@admin.register(DisponibilidadBarbero)
class DisponibilidadBarberoAdmin(admin.ModelAdmin):
    list_display = ["barbero", "fecha", "hora_inicio", "hora_fin"]
    list_filter = ["fecha", "barbero"]
    date_hierarchy = "fecha"
