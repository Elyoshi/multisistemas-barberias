// ============================================================================
// booking.js — Lógica del wizard de reserva (portal cliente, SIN login)
// Extraído del <script> inline de client.html. Depende de api.js
// (getBarbers, getServices, getHorariosOcupados, getDisponibilidadBarbero,
// createReservationMultiple), todas
// asíncronas (devuelven Promise) sin importar el DATA_MODE de api.js.
// Todas estas son públicas a propósito: el cliente reserva sin autenticarse.
// ============================================================================

// ESTADO LOCAL DEL WIZARD
let currentStep = 1;
let selectedBarberId = null;
let selectedServiceIds = []; // hasta 2 servicios, mismo barbero/fecha/bloque consecutivo
let selectedDateStr = null; // YYYY-MM-DD
let selectedTimeSlot = null; // HH:MM

let calendarDate = new Date(); // Mes en visualizador

// Elementos DOM
let panels, stepNodes, btnPrev, btnNext, progressLine;

// INICIALIZACIÓN
document.addEventListener('DOMContentLoaded', async () => {
    panels = [
        null,
        document.getElementById('panel-step-1'),
        document.getElementById('panel-step-2'),
        document.getElementById('panel-step-3'),
        document.getElementById('panel-step-4')
    ];
    stepNodes = [
        null,
        document.getElementById('step-node-1'),
        document.getElementById('step-node-2'),
        document.getElementById('step-node-3'),
        document.getElementById('step-node-4')
    ];
    btnPrev = document.getElementById('btn-prev-step');
    btnNext = document.getElementById('btn-next-step');
    progressLine = document.getElementById('progress-line');

    await renderBarbersStep();
    await renderServicesStep();

    // Navegación
    btnPrev.addEventListener('click', () => goToStep(currentStep - 1));
    btnNext.addEventListener('click', () => goToStep(currentStep + 1));

    // Calendario
    document.getElementById('btn-prev-month').addEventListener('click', () => {
        calendarDate.setMonth(calendarDate.getMonth() - 1);
        renderCalendarWidget();
    });
    document.getElementById('btn-next-month').addEventListener('click', () => {
        calendarDate.setMonth(calendarDate.getMonth() + 1);
        renderCalendarWidget();
    });

    // Envío de Formulario
    document.getElementById('barber-booking-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('client-name').value.trim();
        const phone = document.getElementById('client-phone').value.trim();
        const submitBtn = e.target.querySelector('button[type="submit"]');

        clearBookingError();
        submitBtn.disabled = true;

        try {
            const services = await getServices();
            const selectedServices = selectedServiceIds
                .map(id => services.find(s => s.id === id))
                .filter(Boolean);

            let cursor = timeToMinutes(selectedTimeSlot);
            const serviciosConHora = selectedServices.map(s => {
                const time = minutesToTime(cursor);
                cursor += s.durationMinutes;
                return { serviceId: s.id, time };
            });

            const result = await createReservationMultiple(name, phone, selectedBarberId, selectedDateStr, serviciosConHora);

            if (result && result.error === 'HORARIO_OCUPADO') {
                showBookingError(result.message);
                selectedTimeSlot = null;
                await renderTimeSlots();
                validateStepButton();
                return;
            }

            showSuccessScreen();
        } catch (err) {
            // Cualquier falla que no sea el 409 manejado arriba: 500 del backend,
            // corte de red, etc. Al cliente solo le mostramos un mensaje genérico
            // (esto es una barbería, no un panel de debugging); el error real
            // queda en la consola para diagnosticar en desarrollo.
            console.error('Error al crear la reserva:', err);
            showBookingError('No pudimos procesar tu reserva, por favor intenta de nuevo en unos segundos.');
        } finally {
            submitBtn.disabled = false;
        }
    });

    // Reiniciar flujo éxito
    document.getElementById('btn-success-restart').addEventListener('click', async () => {
        currentStep = 1;
        selectedBarberId = null;
        selectedServiceIds = [];
        selectedDateStr = null;
        selectedTimeSlot = null;
        document.getElementById('barber-booking-form').reset();
        clearBookingError();

        document.getElementById('panel-success').classList.remove('active');
        document.getElementById('wizard-navigation-buttons').style.display = 'flex';

        await renderBarbersStep();
        await renderServicesStep();
        goToStep(1);
    });
});

// WIZARD NAVIGATION
async function goToStep(stepNum) {
    if (stepNum < 1 || stepNum > 4) return;

    panels.forEach((p, idx) => {
        if (idx > 0) p.classList.remove('active');
    });
    stepNodes.forEach((s, idx) => {
        if (idx > 0) {
            s.classList.remove('active');
            s.classList.remove('completed');
        }
    });

    currentStep = stepNum;
    panels[currentStep].classList.add('active');

    for (let i = 1; i <= 4; i++) {
        if (i < currentStep) {
            stepNodes[i].classList.add('completed');
        } else if (i === currentStep) {
            stepNodes[i].classList.add('active');
        }
    }

    const percentage = ((currentStep - 1) / 3) * 100;
    progressLine.style.width = `${percentage}%`;

    btnPrev.disabled = currentStep === 1;
    validateStepButton();

    if (currentStep === 3) {
        renderCalendarWidget();
    } else if (currentStep === 4) {
        await prepareSummary();
    }
}

// VALIDAR CONTINUACIÓN DE PASOS
function validateStepButton() {
    let isValid = false;

    if (currentStep === 1) {
        isValid = selectedBarberId !== null;
    } else if (currentStep === 2) {
        isValid = selectedServiceIds.length > 0;
    } else if (currentStep === 3) {
        isValid = selectedDateStr !== null && selectedTimeSlot !== null;
    } else if (currentStep === 4) {
        isValid = true;
    }

    btnNext.disabled = !isValid;
    btnNext.style.display = currentStep === 4 ? 'none' : 'inline-flex';
}

// PASO 1: RENDER BARBEROS
async function renderBarbersStep() {
    const barbers = await getBarbers();
    const container = document.getElementById('barbers-container');
    container.innerHTML = '';

    barbers.forEach(barber => {
        const card = document.createElement('div');
        card.className = `barber-selection-card ${selectedBarberId === barber.id ? 'selected' : ''}`;

        card.innerHTML = `
            <div class="barber-card-avatar">${barber.name.charAt(0).toUpperCase()}</div>
            <h3 class="barber-card-name">${barber.name}</h3>
            <div class="barber-card-role">${barber.role}</div>
            <p class="barber-card-desc">${barber.specialty}</p>
        `;

        card.addEventListener('click', () => {
            selectedBarberId = barber.id;
            document.querySelectorAll('.barber-selection-card').forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
            validateStepButton();
            setTimeout(() => goToStep(2), 250);
        });

        container.appendChild(card);
    });
}

// PASO 2: RENDER SERVICIOS
// Selección múltiple (hasta 2 servicios de la misma visita, mismo barbero
// y bloque de horario consecutivo). Se re-renderiza toda la lista en cada
// click para reflejar el estado seleccionado/deshabilitado (al llegar a 2
// se deshabilitan las tarjetas restantes hasta que el cliente deseleccione
// alguna). El avance al paso 3 ya no es automático -- requiere el botón
// "Siguiente", porque el primer click ya no implica "terminé de elegir".
//
// Regla de exclusividad de combos (serv.isCombo): un combo NUNCA se suma a
// otra seleccion, siempre la reemplaza por completo. Mientras un combo esta
// seleccionado, todo lo demas se ve atenuado ("locked") EXCEPTO el combo
// mismo -- pero sigue siendo clickeable: un click en un no-combo con un
// combo activo reemplaza la seleccion (no lo suma). El bloqueo real (sin
// click, "disabled") solo aplica al limite de "hasta 2" entre no-combo.
async function renderServicesStep() {
    const services = await getServices();
    const container = document.getElementById('services-container');
    container.innerHTML = '';

    const selectedCombo = services.find(s => s.isCombo && selectedServiceIds.includes(s.id));

    services.forEach(serv => {
        const isSelected = selectedServiceIds.includes(serv.id);
        // Combo activo y esta no es su tarjeta: atenuada pero clickeable
        // (permite reemplazar la seleccion, ver regla arriba).
        const isLocked = Boolean(selectedCombo) && serv.id !== selectedCombo.id;
        // Limite de 2 alcanzado sin combo de por medio: genuinamente bloqueada.
        const isBlocked = !selectedCombo && !isSelected && !serv.isCombo && selectedServiceIds.length >= 2;

        const card = document.createElement('div');
        card.className = `service-item-card ${isSelected ? 'selected' : ''} ${isLocked ? 'locked' : ''} ${isBlocked ? 'disabled' : ''}`;

        card.innerHTML = `
            <div class="service-checkbox"><i class="fa-solid fa-check"></i></div>
            <div class="service-info">
                <div class="service-name-row">
                    <span class="service-name">${serv.name}</span>
                    <span class="service-category-badge">${serv.category}</span>
                </div>
                <p class="service-desc">${serv.desc}</p>
                <span class="service-duration"><i class="fa-regular fa-clock"></i> ${serv.duration}</span>
            </div>
            <div class="service-price-block">
                <span class="service-price">$${serv.price.toLocaleString('es-CL')}</span>
            </div>
        `;

        if (!isBlocked) {
            card.addEventListener('click', () => {
                if (serv.isCombo) {
                    // Un combo siempre reemplaza todo -- o se deselecciona
                    // por completo si ya era el unico elegido.
                    selectedServiceIds = isSelected ? [] : [serv.id];
                } else if (selectedCombo) {
                    // Habia un combo activo: un no-combo reemplaza, no se
                    // suma al combo.
                    selectedServiceIds = [serv.id];
                } else {
                    const idx = selectedServiceIds.indexOf(serv.id);
                    if (idx !== -1) {
                        selectedServiceIds.splice(idx, 1);
                    } else if (selectedServiceIds.length < 2) {
                        selectedServiceIds.push(serv.id);
                    }
                }
                validateStepButton();
                renderServicesStep();
            });
        }

        container.appendChild(card);
    });
}

// PASO 3: CALENDARIO Y HORAS
function renderCalendarWidget() {
    const grid = document.getElementById('calendar-days-grid');
    grid.innerHTML = '';

    const year = calendarDate.getFullYear();
    const month = calendarDate.getMonth();

    const monthNames = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ];
    document.getElementById('calendar-title').textContent = `${monthNames[month]} ${year}`;

    const firstDayIndex = new Date(year, month, 1).getDay();
    const adjustedFirstDay = firstDayIndex === 0 ? 6 : firstDayIndex - 1;
    const totalDays = new Date(year, month + 1, 0).getDate();
    const today = new Date();

    for (let i = 0; i < adjustedFirstDay; i++) {
        grid.appendChild(document.createElement('div'));
    }

    for (let day = 1; day <= totalDays; day++) {
        const btn = document.createElement('button');
        btn.className = 'cal-day-btn';
        btn.textContent = day;

        const loopDate = new Date(year, month, day);
        const formatMonth = (month + 1).toString().padStart(2, '0');
        const formatDay = day.toString().padStart(2, '0');
        const loopDateStr = `${year}-${formatMonth}-${formatDay}`;

        const compareToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());

        if (loopDate < compareToday) {
            btn.disabled = true;
        } else {
            if (loopDate.toDateString() === today.toDateString()) {
                btn.classList.add('today');
            }
            if (selectedDateStr === loopDateStr) {
                btn.classList.add('selected');
            }

            btn.addEventListener('click', async () => {
                document.querySelectorAll('.cal-day-btn').forEach(b => b.classList.remove('selected'));
                btn.classList.add('selected');

                selectedDateStr = loopDateStr;
                selectedTimeSlot = null;

                const formattedLabel = loopDate.toLocaleDateString('es-CL', { weekday: 'long', day: 'numeric', month: 'long' });
                document.getElementById('selected-day-label').innerHTML = `Fecha: <strong style="color: var(--color-gold);">${formattedLabel}</strong>`;

                await renderTimeSlots();
                validateStepButton();
            });
        }

        grid.appendChild(btn);
    }
}

// "HH:MM" <-> minutos desde medianoche, para sumar duraciones y comparar
// bloques de horario (un servicio de 2 items ocupa mas que un slot fijo).
function timeToMinutes(t) {
    const [h, m] = t.split(':').map(Number);
    return h * 60 + m;
}

function minutesToTime(mins) {
    const h = Math.floor(mins / 60).toString().padStart(2, '0');
    const m = (mins % 60).toString().padStart(2, '0');
    return `${h}:${m}`;
}

// Genera horas candidatas cada 30 min dentro de cada ventana de
// disponibilidad, pero solo hasta donde el bloque completo (duracionMinutos)
// quepa antes de que termine la ventana -- asi un candidato nunca se pasa
// del horario en el que el barbero esta disponible ese dia.
function generarHorasDesdeVentanas(ventanas, duracionMinutos, pasoMinutos = 30) {
    const horas = [];
    ventanas.forEach(v => {
        let inicio = timeToMinutes(v.horaInicio);
        const fin = timeToMinutes(v.horaFin);
        while (inicio + duracionMinutos <= fin) {
            horas.push(minutesToTime(inicio));
            inicio += pasoMinutos;
        }
    });
    return horas;
}

async function renderTimeSlots() {
    const container = document.getElementById('slots-grid-container');
    container.innerHTML = '';

    const services = await getServices();
    const totalDuration = selectedServiceIds.reduce((sum, id) => {
        const s = services.find(sv => sv.id === id);
        return sum + (s ? s.durationMinutes : 0);
    }, 0);

    // Capa de disponibilidad personalizada: si hay ventanas cargadas para
    // este barbero+fecha, reemplazan el hoursList base solo para esta
    // fecha. Sin ventanas, comportamiento identico al de siempre.
    const ventanas = await getDisponibilidadBarbero(selectedBarberId, selectedDateStr);
    const hoursList = ventanas.length
        ? generarHorasDesdeVentanas(ventanas, totalDuration)
        : ["09:30", "10:30", "11:30", "14:00", "15:00", "16:00", "17:00", "18:00", "19:00"];

    const ocupados = await getHorariosOcupados();
    const bloquesOcupados = ocupados
        .filter(r => r.barberId === selectedBarberId && r.date === selectedDateStr)
        .map(r => {
            const inicio = timeToMinutes(r.time);
            return { inicio, fin: inicio + (r.durationMinutes || 0) };
        });

    hoursList.forEach(hour => {
        const btn = document.createElement('button');
        btn.className = 'barber-slot-btn';
        btn.textContent = `${hour} Hrs`;

        // Un horario solo esta disponible si el bloque COMPLETO (inicio
        // hasta inicio + duracion total de los servicios elegidos) no se
        // superpone con ningun bloque ya ocupado de ese barbero/fecha.
        const inicioCandidato = timeToMinutes(hour);
        const finCandidato = inicioCandidato + totalDuration;
        const isBooked = bloquesOcupados.some(
            b => inicioCandidato < b.fin && finCandidato > b.inicio
        );

        if (isBooked) {
            btn.disabled = true;
            btn.textContent = `${hour} (Ocupado)`;
        } else {
            if (selectedTimeSlot === hour) {
                btn.classList.add('selected');
            }

            btn.addEventListener('click', () => {
                document.querySelectorAll('.barber-slot-btn').forEach(b => b.classList.remove('selected'));
                btn.classList.add('selected');
                selectedTimeSlot = hour;
                validateStepButton();
                setTimeout(() => goToStep(4), 250);
            });
        }

        container.appendChild(btn);
    });
}

// PASO 4: RESUMEN DE CHECKOUT
async function prepareSummary() {
    const barbers = await getBarbers();
    const barber = barbers.find(b => b.id === selectedBarberId);
    const services = await getServices();
    const selectedServices = selectedServiceIds
        .map(id => services.find(s => s.id === id))
        .filter(Boolean);

    const totalPrice = selectedServices.reduce((sum, s) => sum + s.price, 0);
    const totalDuration = selectedServices.reduce((sum, s) => sum + s.durationMinutes, 0);

    document.getElementById('summary-barber-name').textContent = barber ? barber.name : '--';
    document.getElementById('summary-service-name').textContent = selectedServices.length
        ? selectedServices.map(s => s.name).join(' + ')
        : '--';
    document.getElementById('summary-duration').textContent = selectedServices.length ? `${totalDuration} min` : '--';
    document.getElementById('summary-total-price').textContent = `$${totalPrice.toLocaleString('es-CL')}`;

    const dateParts = selectedDateStr.split('-');
    const dateObj = new Date(dateParts[0], dateParts[1] - 1, dateParts[2]);
    const formattedDate = dateObj.toLocaleDateString('es-CL', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

    document.getElementById('summary-datetime').textContent = `${formattedDate} a las ${selectedTimeSlot} Hrs`;
}

// MENSAJE DE ERROR DE RESERVA (ej. 409 horario ocupado)
// No hay un elemento dedicado en client.html para esto, así que se crea
// dinámicamente la primera vez y se reutiliza después.
function showBookingError(message) {
    let el = document.getElementById('booking-error-message');
    if (!el) {
        el = document.createElement('div');
        el.id = 'booking-error-message';
        el.style.color = 'var(--color-alert)';
        el.style.marginTop = '12px';
        el.style.fontWeight = '600';
        el.style.fontSize = '0.875rem';
        document.getElementById('barber-booking-form').appendChild(el);
    }
    el.textContent = message;
    el.style.display = 'block';
}

function clearBookingError() {
    const el = document.getElementById('booking-error-message');
    if (el) {
        el.style.display = 'none';
    }
}

// PANTALLA ÉXITO
function showSuccessScreen() {
    panels[4].classList.remove('active');
    document.getElementById('panel-success').classList.add('active');
    document.getElementById('wizard-navigation-buttons').style.display = 'none';
    progressLine.style.width = `100%`;
    stepNodes[4].classList.remove('active');
    stepNodes[4].classList.add('completed');
}
