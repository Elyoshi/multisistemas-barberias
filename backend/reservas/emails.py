import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_confirmation_email(reserva):
    """Envia el email de confirmacion de una reserva.

    Pensada para correr en un hilo aparte (ver views.py) asi la respuesta
    al cliente no espera a que Resend conteste. Si algo falla, se loguea
    pero no se propaga -- la reserva ya quedo guardada en la BD, que es
    lo que importa.
    """
    if not reserva.cliente_email:
        return

    asunto = f"Confirmacion de tu hora en {settings.BARBERIA_NOMBRE}"
    cuerpo = (
        f"Hola {reserva.cliente_nombre},\n\n"
        f"Tu hora en {settings.BARBERIA_NOMBRE} quedo registrada:\n\n"
        f"Servicio: {reserva.servicio.nombre}\n"
        f"Barbero: {reserva.barbero.nombre}\n"
        f"Fecha: {reserva.fecha.strftime('%d-%m-%Y')}\n"
        f"Hora: {reserva.hora.strftime('%H:%M')}\n"
        f"Estado: {reserva.get_estado_display()}\n\n"
        f"Te confirmaremos apenas la barberia acepte tu hora.\n"
    )

    try:
        send_mail(
            subject=asunto,
            message=cuerpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[reserva.cliente_email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Fallo el envio del email de confirmacion para reserva %s", reserva.pk)
