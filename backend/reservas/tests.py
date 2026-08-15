from datetime import date, time
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings

from .models import Barbero, Reserva, Servicio


class _FakeThread:
    """views.py manda los emails en threading.Thread(daemon=True).start()
    para no bloquear la respuesta HTTP -- en produccion esta bien, pero en
    los tests eso es una condicion de carrera (la asercion puede correr
    antes de que el hilo termine). Este stub corre el target sincronico,
    en el mismo hilo, solo durante los tests.
    """

    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


class ConfirmacionEmailFlowTest(TestCase):
    def setUp(self):
        self.barbero = Barbero.objects.create(nombre="Juan", email="juan@example.com")
        self.servicio = Servicio.objects.create(nombre="Corte", precio=10000, duracion_minutos=30)
        patcher = patch("reservas.views.threading.Thread", _FakeThread)
        patcher.start()
        self.addCleanup(patcher.stop)

    @override_settings(HABILITAR_CONFIRMACION_EMAIL=True)
    def test_flujo_completo_confirmar(self):
        mail.outbox = []
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(
                "/api/reservas/",
                {
                    "barbero": self.barbero.id,
                    "servicio": self.servicio.id,
                    "cliente_nombre": "Pedro",
                    "cliente_telefono": "123",
                    "cliente_email": "pedro@example.com",
                    "fecha": "2026-09-01",
                    "hora": "10:00",
                },
            )
        self.assertEqual(resp.status_code, 201, resp.content)

        reserva = Reserva.objects.get(id=resp.data["id"])
        self.assertEqual(reserva.estado, "pendiente")
        self.assertTrue(reserva.token_confirmacion)

        # cliente (pendiente) + barbero (notificacion) = 2 emails
        self.assertEqual(len(mail.outbox), 2)
        asuntos = sorted(m.subject for m in mail.outbox)
        self.assertIn("pendiente de confirmacion", asuntos[1])

        confirm_url = f"/api/reservas/confirmar/{reserva.token_confirmacion}/"

        # GET: muestra el detalle + boton, pero NO ejecuta la transicion
        # (el link del email puede ser abierto por un scanner de seguridad
        # antes de que el humano haga click).
        resp = self.client.get(confirm_url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"confirmar esta reserva", resp.content)
        self.assertIn(b'method="POST"', resp.content)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, "pendiente")
        self.assertEqual(len(mail.outbox), 2)

        # POST (click real en el boton del form): ahi si se confirma.
        resp = self.client.post(confirm_url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"confirmada", resp.content)

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, "confirmada")
        self.assertEqual(len(mail.outbox), 3)
        self.assertIn("fue confirmada", mail.outbox[2].subject)

        # click de nuevo (GET) -> informativo, sin boton, sin nuevo email
        resp = self.client.get(confirm_url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"ya hab", resp.content)
        self.assertNotIn(b'method="POST"', resp.content)
        self.assertEqual(len(mail.outbox), 3)

    @override_settings(HABILITAR_CONFIRMACION_EMAIL=True)
    def test_get_nunca_cambia_estado_aunque_se_repita(self):
        # Simula un escaner de seguridad de email (Outlook Safe Links,
        # Barracuda, etc.) que visita el link varias veces solo por
        # abrirlo -- ninguna de esas visitas debe mover el estado.
        reserva = Reserva.objects.create(
            barbero=self.barbero,
            servicio=self.servicio,
            cliente_nombre="Pedro",
            cliente_telefono="123",
            cliente_email="pedro@example.com",
            fecha=date(2026, 9, 1),
            hora=time(10, 0),
        )
        confirm_url = f"/api/reservas/confirmar/{reserva.token_confirmacion}/"
        cancel_url = f"/api/reservas/cancelar/{reserva.token_confirmacion}/"

        for _ in range(5):
            self.assertEqual(self.client.get(confirm_url).status_code, 200)
            self.assertEqual(self.client.get(cancel_url).status_code, 200)

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, "pendiente")

    @override_settings(HABILITAR_CONFIRMACION_EMAIL=True)
    def test_cancelar_no_revive(self):
        reserva = Reserva.objects.create(
            barbero=self.barbero,
            servicio=self.servicio,
            cliente_nombre="Pedro",
            cliente_telefono="123",
            cliente_email="pedro@example.com",
            fecha=date(2026, 9, 1),
            hora=time(10, 0),
        )
        cancel_url = f"/api/reservas/cancelar/{reserva.token_confirmacion}/"

        # GET no cancela todavia.
        self.client.get(cancel_url)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, "pendiente")

        # POST si.
        self.client.post(cancel_url)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, "cancelada")

        confirm_url = f"/api/reservas/confirmar/{reserva.token_confirmacion}/"
        resp = self.client.get(confirm_url)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, "cancelada")
        self.assertIn(b"No se puede confirmar", resp.content)

    def test_endpoints_404_con_flag_apagado(self):
        reserva = Reserva.objects.create(
            barbero=self.barbero,
            servicio=self.servicio,
            cliente_nombre="Pedro",
            cliente_telefono="123",
            fecha=date(2026, 9, 1),
            hora=time(10, 0),
        )
        resp = self.client.get(f"/api/reservas/confirmar/{reserva.token_confirmacion}/")
        self.assertEqual(resp.status_code, 404)
        resp = self.client.post(f"/api/reservas/confirmar/{reserva.token_confirmacion}/")
        self.assertEqual(resp.status_code, 404)
        resp = self.client.get(f"/api/reservas/cancelar/{reserva.token_confirmacion}/")
        self.assertEqual(resp.status_code, 404)
        resp = self.client.post(f"/api/reservas/cancelar/{reserva.token_confirmacion}/")
        self.assertEqual(resp.status_code, 404)

    def test_texto_email_creacion_sin_cambios_con_flag_apagado(self):
        mail.outbox = []
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(
                "/api/reservas/",
                {
                    "barbero": self.barbero.id,
                    "servicio": self.servicio.id,
                    "cliente_nombre": "Pedro",
                    "cliente_telefono": "123",
                    "cliente_email": "pedro@example.com",
                    "fecha": "2026-09-01",
                    "hora": "10:00",
                },
            )
        self.assertEqual(resp.status_code, 201, resp.content)
        # sin barbero-email, texto identico al de siempre
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Confirmacion de tu hora", mail.outbox[0].subject)
        self.assertIn("quedo registrada", mail.outbox[0].body)
