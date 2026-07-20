// ============================================================================
// api.js — CAPA DE DATOS (Data Access Layer)
// ============================================================================
// Único archivo que sabe si los datos vienen de localStorage o de la API real
// de Django. booking.js y admin.js no necesitan saber qué modo está activo:
// todas las funciones públicas (getBarbers, getServices, getReservations,
// createReservation, updateReservationStatus) devuelven SIEMPRE una Promise,
// sin importar DATA_MODE, así que siempre se consumen con await/.then().
//
// DATA_MODE = 'LOCAL' -> localStorage (datos MOCK, para probar sin backend)
// DATA_MODE = 'API'   -> fetch() contra el backend Django en API_BASE_URL
//
// AUTENTICACIÓN (solo panel admin): getReservations() y
// updateReservationStatus() requieren token (el backend las protege con
// IsAuthenticated). booking.js nunca llama a estas dos ni necesita login:
// usa getHorariosOcupados(), que es pública. Ver adminLogin()/authHeaders()
// más abajo y la NOTA DE SEGURIDAD en admin.js.
// ============================================================================

const DATA_MODE = 'API'; // 'LOCAL' | 'API'
const API_BASE_URL =  'https://backend-veltrix-production.up.railway.app/api'; // ej: 'https://tu-backend.up.railway.app/api' (se configura por rama de deploy)

const BARBERIA_NOMBRE = 'Legend Barber'; // se configura por rama de deploy
const BARBERIA_TAGLINE = 'Cortes & Estilo Premium'; // idem
const BARBERIA_COLOR_PRIMARIO = '#C9A961'; // idem, hex

// ----------------------------------------------------------------------------
// DATOS DE PRUEBA (MOCK) — solo se usan en modo LOCAL
// ----------------------------------------------------------------------------
const defaultBarbers = [
    {
        id: "b_1",
        name: "Carlos Gómez",
        role: "Master Barber",
        rating: "4.9",
        reviews: "142 reviews",
        avatar: "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=150&auto=format&fit=crop&q=80",
        specialty: "Cortes clásicos, Navaja libre y Degradados perfectos."
    },
    {
        id: "b_2",
        name: "Sebastián Rojas",
        role: "Especialista en Barbas",
        rating: "4.8",
        reviews: "98 reviews",
        avatar: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150&auto=format&fit=crop&q=80",
        specialty: "Perfilado con navaja, toalla caliente y tratamientos de crecimiento."
    },
    {
        id: "b_3",
        name: "Matías Silva",
        role: "Estilista Urbano",
        rating: "4.7",
        reviews: "115 reviews",
        avatar: "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=150&auto=format&fit=crop&q=80",
        specialty: "Cortes con diseño (Hair Tattoo), tintes modernos y Freestyle."
    }
];

const defaultServices = [
    {
        id: "s_1",
        name: "Corte de Cabello Tradicional",
        price: 12000,
        duration: "30 min",
        durationMinutes: 30,
        desc: "Lavado, corte con tijera o máquina y peinado con cera premium.",
        category: "corte"
    },
    {
        id: "s_2",
        name: "Perfilado de Barba Real",
        price: 8000,
        duration: "25 min",
        durationMinutes: 25,
        desc: "Diseño de barba, afeitado a navaja con toalla caliente y aceites hidratantes.",
        category: "barba"
    },
    {
        id: "s_3",
        name: "Combo Legendario (Corte + Barba)",
        price: 18000,
        duration: "55 min",
        durationMinutes: 55,
        desc: "Servicio completo estrella: Corte a elección, perfilado de barba y toalla caliente aromática.",
        category: "premium"
    },
    {
        id: "s_4",
        name: "Corte de Cabello + Diseño Urbano",
        price: 15000,
        duration: "45 min",
        durationMinutes: 45,
        desc: "Corte clásico o degradado sumado a líneas o diseño artístico (Hair Tattoo).",
        category: "corte"
    },
    {
        id: "s_5",
        name: "Tratamiento Facial e Hidratación",
        price: 10000,
        duration: "20 min",
        durationMinutes: 20,
        desc: "Limpieza facial con vapor, mascarilla negra exfoliante y masaje capilar.",
        category: "facial"
    }
];

const defaultReservations = [
    {
        id: "res_9182",
        clientName: "Fernando Alarcón",
        clientPhone: "987654321",
        barberId: "b_1",
        serviceId: "s_3",
        date: "2026-07-04",
        time: "10:00",
        status: "confirmada",
        createdAt: "2026-07-01T12:00:00Z"
    },
    {
        id: "res_3214",
        clientName: "Ignacio Pérez",
        clientPhone: "956321478",
        barberId: "b_2",
        serviceId: "s_2",
        date: "2026-07-04",
        time: "11:30",
        status: "pendiente",
        createdAt: "2026-07-02T10:15:00Z"
    },
    {
        id: "res_8492",
        clientName: "Felipe Oyarzún",
        clientPhone: "963258741",
        barberId: "b_3",
        serviceId: "s_1",
        date: "2026-07-05",
        time: "15:00",
        status: "completada",
        createdAt: "2026-07-02T14:30:00Z"
    }
];

// ----------------------------------------------------------------------------
// INICIALIZACIÓN LOCAL (solo aplica en modo LOCAL)
// ----------------------------------------------------------------------------
function initLocalStorageDB() {
    if (!localStorage.getItem('bb_barbers')) {
        localStorage.setItem('bb_barbers', JSON.stringify(defaultBarbers));
    }
    if (!localStorage.getItem('bb_services')) {
        localStorage.setItem('bb_services', JSON.stringify(defaultServices));
    }
    if (!localStorage.getItem('bb_reservations')) {
        localStorage.setItem('bb_reservations', JSON.stringify(defaultReservations));
    }
}

function readLocalReservations() {
    initLocalStorageDB();
    return JSON.parse(localStorage.getItem('bb_reservations'));
}

function saveReservations(resList) {
    localStorage.setItem('bb_reservations', JSON.stringify(resList));
}

// ----------------------------------------------------------------------------
// AUTENTICACIÓN DEL PANEL ADMIN
// Token guardado en sessionStorage (se borra al cerrar la pestaña, a
// diferencia de localStorage). Solo lo usa admin.js -- booking.js (portal
// cliente) no requiere login y nunca llama a nada de este bloque.
// ----------------------------------------------------------------------------
const ADMIN_TOKEN_KEY = 'bb_admin_token';

function getAdminToken() {
    return sessionStorage.getItem(ADMIN_TOKEN_KEY);
}

function setAdminToken(token) {
    sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
}

function clearAdminToken() {
    sessionStorage.removeItem(ADMIN_TOKEN_KEY);
}

// Error dedicado para 401: le permite a admin.js distinguir "la sesión
// es inválida o expiró" (hay que mandar al login) de cualquier otro
// fallo de red/servidor (que solo debe mostrarse como error genérico).
class AuthError extends Error {
    constructor(message) {
        super(message);
        this.name = 'AuthError';
    }
}

function authHeaders() {
    const token = getAdminToken();
    return token ? { 'Authorization': `Token ${token}` } : {};
}

function adminLogin(username, password) {
    return fetch(`${API_BASE_URL}/auth/login/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
    }).then(r => {
        if (!r.ok) {
            return r.json().catch(() => ({})).then(body => {
                throw new Error(body.detail || 'No pudimos iniciar sesión.');
            });
        }
        return r.json();
    }).then(body => {
        setAdminToken(body.token);
        return body.token;
    });
}

// ----------------------------------------------------------------------------
// MAPEO API (Django, español) -> contrato interno (inglés) que ya usan
// booking.js y admin.js, definido por defaultBarbers/defaultServices/
// defaultReservations arriba. Solo aplica en modo API: en modo LOCAL los
// datos ya nacen en este formato.
// ----------------------------------------------------------------------------

function mapBarbero(b) {
    return {
        id: b.id,
        name: b.nombre,
        role: b.rol,
        specialty: b.especialidad,
        avatar: b.avatar_url
    };
}

function mapServicio(s) {
    return {
        id: s.id,
        name: s.nombre,
        price: s.precio,
        duration: `${s.duracion_minutos} min`,
        durationMinutes: s.duracion_minutos,
        desc: s.descripcion,
        category: s.categoria
    };
}

function mapReserva(r) {
    return {
        id: r.id,
        clientName: r.cliente_nombre,
        clientPhone: r.cliente_telefono,
        barberId: r.barbero,
        serviceId: r.servicio,
        date: r.fecha,
        time: r.hora,
        status: r.estado,
        createdAt: r.creado_en
    };
}

// -----------------------------------------------------------------------
// FUNCIONES PÚBLICAS — firma estable, usadas por booking.js y admin.js.
// Devuelven SIEMPRE una Promise: en LOCAL se envuelve el valor síncrono con
// Promise.resolve(...); en API es el resultado real de fetch().
// ----------------------------------------------------------------------------

function getBarbers() {
    if (DATA_MODE === 'LOCAL') {
        initLocalStorageDB();
        return Promise.resolve(JSON.parse(localStorage.getItem('bb_barbers')));
    }
    return fetch(`${API_BASE_URL}/barberos/`).then(r => {
        if (!r.ok) {
            throw new Error(`Error al obtener barberos (status ${r.status})`);
        }
        return r.json();
    }).then(data => data.map(mapBarbero));
}

function getServices() {
    if (DATA_MODE === 'LOCAL') {
        initLocalStorageDB();
        return Promise.resolve(JSON.parse(localStorage.getItem('bb_services')));
    }
    return fetch(`${API_BASE_URL}/servicios/`).then(r => {
        if (!r.ok) {
            throw new Error(`Error al obtener servicios (status ${r.status})`);
        }
        return r.json();
    }).then(data => data.map(mapServicio));
}

function getReservations() {
    if (DATA_MODE === 'LOCAL') {
        return Promise.resolve(readLocalReservations());
    }
    return fetch(`${API_BASE_URL}/reservas/`, {
        headers: authHeaders()
    }).then(r => {
        if (r.status === 401) {
            throw new AuthError('Sesión inválida o expirada.');
        }
        if (!r.ok) {
            throw new Error(`Error al obtener reservas (status ${r.status})`);
        }
        return r.json();
    }).then(data => data.map(mapReserva));
}

// Versión pública (sin login) para booking.js: solo horarios ocupados,
// sin nombre/teléfono de clientes. El backend expone esto en una acción
// separada (AllowAny) precisamente para no tener que abrir /reservas/
// (list) completo -- ese ahora requiere token porque trae datos de
// clientes (ver GET /api/reservas/ vs /api/reservas/horarios_ocupados/).
function getHorariosOcupados() {
    if (DATA_MODE === 'LOCAL') {
        initLocalStorageDB();
        const services = JSON.parse(localStorage.getItem('bb_services')) || defaultServices;
        const ocupados = readLocalReservations()
            .filter(r => r.status !== 'cancelada')
            .map(r => {
                const service = services.find(s => s.id === r.serviceId);
                return {
                    barberId: r.barberId,
                    date: r.date,
                    time: r.time,
                    durationMinutes: service ? service.durationMinutes : 0
                };
            });
        return Promise.resolve(ocupados);
    }
    return fetch(`${API_BASE_URL}/reservas/horarios_ocupados/`).then(r => {
        if (!r.ok) {
            throw new Error(`Error al obtener horarios ocupados (status ${r.status})`);
        }
        return r.json();
    }).then(data => data.map(item => ({
        barberId: item.barbero_id,
        date: item.fecha,
        time: item.hora.slice(0, 5), // backend devuelve "HH:MM:SS"; el wizard compara contra "HH:MM"
        durationMinutes: item.servicio__duracion_minutos
    })));
}

// Versión pública (sin login) para booking.js: solo horarios ocupados,
// sin nombre/teléfono de clientes. El backend expone esto en una acción
// separada (AllowAny) precisamente para no tener que abrir /reservas/
// (list) completo -- ese ahora requiere token porque trae datos de
// clientes (ver GET /api/reservas/ vs /api/reservas/horarios_ocupados/).


function createReservation(clientName, clientPhone, barberId, serviceId, date, time) {
    if (DATA_MODE === 'LOCAL') {
        const list = readLocalReservations();
        const newRes = {
            id: "res_" + Math.floor(Math.random() * 9000 + 1000),
            clientName: clientName,
            clientPhone: clientPhone,
            barberId: barberId,
            serviceId: serviceId,
            date: date,
            time: time,
            status: "pendiente",
            createdAt: new Date().toISOString()
        };
        list.push(newRes);
        saveReservations(list);
        return Promise.resolve(newRes);
    }

    // La validación de horario ocupado (anti doble-reserva) vive en el
    // backend con un constraint de base de datos, no acá. Si el backend
    // responde 409, se devuelve un objeto identificable en vez de lanzar
    // una excepción genérica, para que booking.js pueda distinguir
    // "horario ocupado" de cualquier otro error y mostrarle al cliente
    // el mensaje correcto en vez de la pantalla de éxito.
    return fetch(`${API_BASE_URL}/reservas/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            cliente_nombre: clientName,
            cliente_telefono: clientPhone,
            barbero: barberId,
            servicio: serviceId,
            fecha: date,
            hora: time
        })
    }).then(r => {
        if (r.status === 409) {
            return r.json().then(body => ({
                error: 'HORARIO_OCUPADO',
                message: body.detail || 'Ese horario ya fue reservado.'
            }));
        }
        if (!r.ok) {
            throw new Error(`Error al crear la reserva (status ${r.status})`);
        }
        return r.json();
    });
}

// Reserva de 1-2 servicios consecutivos en la misma visita (mismo barbero,
// misma fecha). serviciosConHora: [{ serviceId, time }, ...] ya con la hora
// de inicio de cada bloque calculada por booking.js (sumando duraciones).
// El backend sigue creando un registro por servicio (POST /reservas/multiples/),
// pero todo dentro de una sola transacción -- ver ReservaViewSet.multiples().
function createReservationMultiple(clientName, clientPhone, barberId, date, serviciosConHora) {
    if (DATA_MODE === 'LOCAL') {
        const list = readLocalReservations();
        const createdAt = new Date().toISOString();
        const created = serviciosConHora.map(({ serviceId, time }) => {
            const newRes = {
                id: "res_" + Math.floor(Math.random() * 9000 + 1000),
                clientName: clientName,
                clientPhone: clientPhone,
                barberId: barberId,
                serviceId: serviceId,
                date: date,
                time: time,
                status: "pendiente",
                createdAt: createdAt
            };
            list.push(newRes);
            return newRes;
        });
        saveReservations(list);
        return Promise.resolve(created);
    }

    return fetch(`${API_BASE_URL}/reservas/multiples/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            cliente_nombre: clientName,
            cliente_telefono: clientPhone,
            barbero: barberId,
            fecha: date,
            servicios: serviciosConHora.map(({ serviceId, time }) => ({
                servicio: serviceId,
                hora: time
            }))
        })
    }).then(r => {
        if (r.status === 409) {
            return r.json().then(body => ({
                error: 'HORARIO_OCUPADO',
                message: body.detail || 'Ese horario ya fue reservado.'
            }));
        }
        if (!r.ok) {
            throw new Error(`Error al crear la reserva (status ${r.status})`);
        }
        return r.json();
    });
}

function updateReservationStatus(resId, newStatus) {
    if (DATA_MODE === 'LOCAL') {
        const list = readLocalReservations();
        const index = list.findIndex(r => r.id === resId);
        if (index !== -1) {
            list[index].status = newStatus;
            saveReservations(list);
            return Promise.resolve(true);
        }
        return Promise.resolve(false);
    }

    return fetch(`${API_BASE_URL}/reservas/${resId}/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ estado: newStatus })
    }).then(r => {
        if (r.status === 401) {
            throw new AuthError('Sesión inválida o expirada.');
        }
        if (!r.ok) {
            throw new Error(`Error al actualizar el estado de la reserva (status ${r.status})`);
        }
        return true;
    });
}

// ----------------------------------------------------------------------------
// BRANDING POR RAMA — aplica BARBERIA_NOMBRE/TAGLINE/COLOR_PRIMARIO al DOM.
// Corre en ambas páginas (client.html y admin.html, ambas cargan api.js) y en
// ambos DATA_MODE -- esto no depende del backend, es puro dato de branch.
// Los <h1> mantienen un texto default hardcodeado en el HTML como fallback
// visual; esta función lo sobrescribe apenas carga el script.
// ----------------------------------------------------------------------------
function applyBranding() {
    document.documentElement.style.setProperty('--color-gold', BARBERIA_COLOR_PRIMARIO);

    // client.html: nombre a dos tonos, ej. "Legend" (plano) + "Barber" (oro).
    // Si el nombre es de una sola palabra, va completo en el acento.
    const brandHeading = document.getElementById('brand-name-heading');
    const brandAccent = document.getElementById('brand-name-accent');
    if (brandHeading && brandAccent) {
        const parts = BARBERIA_NOMBRE.trim().split(/\s+/);
        const accent = parts.length > 1 ? parts.pop() : parts[0];
        const plain = parts.join(' ');
        brandHeading.firstChild.textContent = plain ? `${plain} ` : '';
        brandAccent.textContent = accent;
        document.title = `Reserva tu Hora — ${BARBERIA_NOMBRE}`;
    }

    const tagline = document.getElementById('brand-tagline');
    if (tagline) {
        tagline.textContent = BARBERIA_TAGLINE;
    }

    // admin.html: aparece 2 veces (pantalla de login y dashboard). "Admin" es
    // una etiqueta fija de la pagina, no parte del nombre de marca.
    const adminBrandNames = document.querySelectorAll('.brand-name-plain');
    if (adminBrandNames.length) {
        adminBrandNames.forEach(el => { el.textContent = BARBERIA_NOMBRE; });
        document.title = `Panel de Administración — ${BARBERIA_NOMBRE}`;
    }
}

applyBranding();

// Inicializar al cargar script (solo aplica en modo LOCAL)
if (DATA_MODE === 'LOCAL') {
    initLocalStorageDB();
}
