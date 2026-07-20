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


def send_confirmation_email_multiple(reservas):
    """Envia un unico email de confirmacion para varias Reserva creadas
    juntas (mismo cliente, barbero y fecha -- visita con 2 servicios
    consecutivos). Mandar un email por Reserva individual leeria como
    2 confirmaciones separadas para lo que el cliente percibe como una
    sola visita.
    """
    primera = reservas[0]
    if not primera.cliente_email:
        return

    lineas_servicios = "\n".join(
        f"  - {r.servicio.nombre} a las {r.hora.strftime('%H:%M')}" for r in reservas
    )

    asunto = f"Confirmacion de tu hora en {settings.BARBERIA_NOMBRE}"
    cuerpo = (
        f"Hola {primera.cliente_nombre},\n\n"
        f"Tu hora en {settings.BARBERIA_NOMBRE} quedo registrada:\n\n"
        f"Servicios:\n{lineas_servicios}\n\n"
        f"Barbero: {primera.barbero.nombre}\n"
        f"Fecha: {primera.fecha.strftime('%d-%m-%Y')}\n"
        f"Estado: {primera.get_estado_display()}\n\n"
        f"Te confirmaremos apenas la barberia acepte tu hora.\n"
    )

    try:
        send_mail(
            subject=asunto,
            message=cuerpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[primera.cliente_email],
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            "Fallo el envio del email de confirmacion multiple para reservas %s",
            [r.pk for r in reservas],
        )
