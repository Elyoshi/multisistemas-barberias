// ============================================================================
// api.js — CAPA DE DATOS (Data Access Layer)
// ============================================================================
// IMPORTANTE: Este es el ÚNICO archivo que va a cambiar cuando conectemos
// el backend de Django (Paso 2/3 del roadmap). Todas las funciones de abajo
// (getBarbers, getServices, getReservations, createReservation,
// updateReservationStatus) van a mantener EXACTAMENTE la misma firma —
// solo cambia su implementación interna de "leer localStorage" a
// "hacer fetch() a la API". booking.js y admin.js no se van a tocar.
//
// MODO ACTUAL: LOCAL (localStorage) — datos de prueba (MOCK), confirmado
// por el equipo que estos NO son los barberos/servicios reales.
// Cuando pasemos a Django, esta constante cambia a 'API'.
// ============================================================================

const DATA_MODE = 'LOCAL'; // 'LOCAL' | 'API' (Paso 3 lo cambia a 'API')
const API_BASE_URL = ''; // Paso 3: acá va la URL de Railway, ej: 'https://tu-backend.up.railway.app/api'

// ----------------------------------------------------------------------------
// DATOS DE PRUEBA (MOCK) — reemplazar por los reales al conectar Django
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
        desc: "Lavado, corte con tijera o máquina y peinado con cera premium.",
        category: "corte"
    },
    {
        id: "s_2",
        name: "Perfilado de Barba Real",
        price: 8000,
        duration: "25 min",
        desc: "Diseño de barba, afeitado a navaja con toalla caliente y aceites hidratantes.",
        category: "barba"
    },
    {
        id: "s_3",
        name: "Combo Legendario (Corte + Barba)",
        price: 18000,
        duration: "55 min",
        desc: "Servicio completo estrella: Corte a elección, perfilado de barba y toalla caliente aromática.",
        category: "premium"
    },
    {
        id: "s_4",
        name: "Corte de Cabello + Diseño Urbano",
        price: 15000,
        duration: "45 min",
        desc: "Corte clásico o degradado sumado a líneas o diseño artístico (Hair Tattoo).",
        category: "corte"
    },
    {
        id: "s_5",
        name: "Tratamiento Facial e Hidratación",
        price: 10000,
        duration: "20 min",
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
// INICIALIZACIÓN LOCAL
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

// ----------------------------------------------------------------------------
// FUNCIONES PÚBLICAS — firma estable, usadas por booking.js y admin.js
// ----------------------------------------------------------------------------

function getBarbers() {
    // Paso 3 (modo API): return fetch(`${API_BASE_URL}/barberos/`).then(r => r.json());
    initLocalStorageDB();
    return JSON.parse(localStorage.getItem('bb_barbers'));
}

function getServices() {
    // Paso 3 (modo API): return fetch(`${API_BASE_URL}/servicios/`).then(r => r.json());
    initLocalStorageDB();
    return JSON.parse(localStorage.getItem('bb_services'));
}

function getReservations() {
    // Paso 3 (modo API): return fetch(`${API_BASE_URL}/reservas/`).then(r => r.json());
    initLocalStorageDB();
    return JSON.parse(localStorage.getItem('bb_reservations'));
}

function saveReservations(resList) {
    localStorage.setItem('bb_reservations', JSON.stringify(resList));
}

function createReservation(clientName, clientPhone, barberId, serviceId, date, time) {
    // Paso 3 (modo API): esto pasa a ser un POST a /reservas/ — la validación
    // de horario ocupado (anti doble-reserva) se hace en el backend con un
    // constraint de base de datos, no solo en el navegador como ahora.
    const list = getReservations();
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
    return newRes;
}

function updateReservationStatus(resId, newStatus) {
    // Paso 3 (modo API): esto pasa a ser un PATCH a /reservas/{id}/
    const list = getReservations();
    const index = list.findIndex(r => r.id === resId);
    if (index !== -1) {
        list[index].status = newStatus;
        saveReservations(list);
        return true;
    }
    return false;
}

// Inicializar al cargar script (solo aplica en modo LOCAL)
if (DATA_MODE === 'LOCAL') {
    initLocalStorageDB();
}
