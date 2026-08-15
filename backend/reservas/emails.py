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

    if settings.HABILITAR_CONFIRMACION_EMAIL:
        asunto = f"Tu hora en {settings.BARBERIA_NOMBRE} esta pendiente de confirmacion"
        cuerpo = (
            f"Hola {reserva.cliente_nombre},\n\n"
            f"Recibimos tu solicitud de hora en {settings.BARBERIA_NOMBRE}:\n\n"
            f"Servicio: {reserva.servicio.nombre}\n"
            f"Barbero: {reserva.barbero.nombre}\n"
            f"Fecha: {reserva.fecha.strftime('%d-%m-%Y')}\n"
            f"Hora: {reserva.hora.strftime('%H:%M')}\n"
            f"Estado: Pendiente de confirmacion\n\n"
            f"Te avisaremos por email apenas la barberia confirme tu hora.\n"
        )
    else:
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

    if settings.HABILITAR_CONFIRMACION_EMAIL:
        asunto = f"Tu hora en {settings.BARBERIA_NOMBRE} esta pendiente de confirmacion"
        cuerpo = (
            f"Hola {primera.cliente_nombre},\n\n"
            f"Recibimos tu solicitud de hora en {settings.BARBERIA_NOMBRE}:\n\n"
            f"Servicios:\n{lineas_servicios}\n\n"
            f"Barbero: {primera.barbero.nombre}\n"
            f"Fecha: {primera.fecha.strftime('%d-%m-%Y')}\n"
            f"Estado: Pendiente de confirmacion\n\n"
            f"Te avisaremos por email apenas la barberia confirme tu hora.\n"
        )
    else:
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


def send_confirmation_email_cliente(reservas):
    """Envia el email de "hora confirmada" al cliente cuando confirma su
    reserva desde el link del correo (ver confirmar_reserva en views.py).
    Solo se llama cuando HABILITAR_CONFIRMACION_EMAIL esta activo, que es
    la unica forma de llegar a ese endpoint.
    """
    primera = reservas[0]
    if not primera.cliente_email:
        return

    lineas_servicios = "\n".join(
        f"  - {r.servicio.nombre} a las {r.hora.strftime('%H:%M')}" for r in reservas
    )

    asunto = f"Tu hora en {settings.BARBERIA_NOMBRE} fue confirmada"
    cuerpo = (
        f"Hola {primera.cliente_nombre},\n\n"
        f"Tu hora en {settings.BARBERIA_NOMBRE} fue confirmada:\n\n"
        f"Servicio(s):\n{lineas_servicios}\n\n"
        f"Barbero: {primera.barbero.nombre}\n"
        f"Fecha: {primera.fecha.strftime('%d-%m-%Y')}\n\n"
        f"Te esperamos!\n"
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
            "Fallo el envio del email de confirmacion (via link) para reservas %s",
            [r.pk for r in reservas],
        )


def send_notificacion_barbero(reservas, confirm_url, cancel_url):
    """Notifica al barbero que tiene una reserva nueva pendiente, con los
    links para confirmarla o cancelarla sin login. Si el barbero no tiene
    email cargado (campo opcional -- ver Barbero.email, hay barberos reales
    sin este dato), no falla: solo loggea que no se pudo notificar.
    """
    primera = reservas[0]
    barbero = primera.barbero
    if not barbero.email:
        logger.info(
            "Barbero %s no tiene email cargado, no se le notifico la reserva %s",
            barbero.pk,
            primera.pk,
        )
        return

    lineas_servicios = "\n".join(
        f"  - {r.servicio.nombre} a las {r.hora.strftime('%H:%M')}" for r in reservas
    )

    asunto = f"Nueva reserva pendiente - {primera.cliente_nombre}"
    cuerpo = (
        f"Hola {barbero.nombre},\n\n"
        f"Tienes una nueva reserva pendiente de confirmacion:\n\n"
        f"Cliente: {primera.cliente_nombre}\n"
        f"Telefono: {primera.cliente_telefono}\n"
        f"Servicio(s):\n{lineas_servicios}\n\n"
        f"Fecha: {primera.fecha.strftime('%d-%m-%Y')}\n\n"
        f"Confirmar esta reserva:\n{confirm_url}\n\n"
        f"Cancelar esta reserva:\n{cancel_url}\n"
    )

    try:
        send_mail(
            subject=asunto,
            message=cuerpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[barbero.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            "Fallo el envio del email de notificacion al barbero para reservas %s",
            [r.pk for r in reservas],
        )
