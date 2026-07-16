// ============================================================================
// admin.js — Lógica del panel de administración
// Extraído del <script> inline de admin.html. Depende de api.js
// (getReservations, getBarbers, getServices, updateReservationStatus).
//
// NOTA DE SEGURIDAD: este panel todavía NO tiene autenticación. Antes de
// desplegarlo (Paso 3), esta vista va a requerir login contra Django.
// No lo dejamos accesible públicamente sin contraseña.
// ============================================================================

let currentFilter = 'todas';

document.addEventListener('DOMContentLoaded', () => {
    renderAdminDashboard();

    document.querySelectorAll('.admin-filter-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            document.querySelectorAll('.admin-filter-chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            currentFilter = chip.getAttribute('data-status');
            renderAdminDashboard();
        });
    });

    // Sincronizar en tiempo real cuando se actualiza el localStorage en otra pestaña (client.html)
    // Paso 3: esto se reemplaza por polling o WebSocket contra la API de Django.
    window.addEventListener('storage', (e) => {
        if (e.key === 'bb_reservations') {
            renderAdminDashboard();
        }
    });
});

function renderAdminDashboard() {
    const reservations = getReservations();
    const barbers = getBarbers();
    const services = getServices();

    const tbody = document.getElementById('admin-table-body');
    tbody.innerHTML = '';

    let totalRevenue = 0;
    let activeCount = 0;
    let completedCount = 0;

    reservations.forEach(res => {
        const service = services.find(s => s.id === res.serviceId);
        const price = service ? service.price : 0;

        if (res.status === 'confirmada' || res.status === 'completada') {
            totalRevenue += price;
        }
        if (res.status === 'pendiente' || res.status === 'confirmada') {
            activeCount++;
        }
        if (res.status === 'completada') {
            completedCount++;
        }
    });

    document.getElementById('metric-revenue').textContent = `$${totalRevenue.toLocaleString('es-CL')}`;
    document.getElementById('metric-active-count').textContent = activeCount;
    document.getElementById('metric-completed-count').textContent = completedCount;

    let filteredReservations = reservations;
    if (currentFilter !== 'todas') {
        filteredReservations = reservations.filter(res => res.status === currentFilter);
    }

    filteredReservations.sort((a, b) => new Date(`${b.date}T${b.time}`) - new Date(`${a.date}T${a.time}`));

    if (filteredReservations.length === 0) {
        document.getElementById('admin-table-empty').style.display = 'block';
        return;
    } else {
        document.getElementById('admin-table-empty').style.display = 'none';
    }

    filteredReservations.forEach(res => {
        const barber = barbers.find(b => b.id === res.barberId);
        const service = services.find(s => s.id === res.serviceId);
        const servicePrice = service ? service.price : 0;

        const tr = document.createElement('tr');

        const dateParts = res.date.split('-');
        const dateObj = new Date(dateParts[0], dateParts[1] - 1, dateParts[2]);
        const formattedDate = dateObj.toLocaleDateString('es-CL', { day: 'numeric', month: 'short' });

        const isPremium = servicePrice >= 15000;
        const priorityBadge = isPremium
            ? `<span class="priority-flag high"><i class="fa-solid fa-star"></i> Premium</span>`
            : `<span class="priority-flag standard">Estándar</span>`;

        tr.innerHTML = `
            <td style="font-weight: 700; color: #FFF;">${res.clientName}</td>
            <td>
                <a href="tel:${res.clientPhone}" style="color: var(--color-gold); font-weight: 600;">
                    <i class="fa-solid fa-phone" style="font-size: 0.75rem;"></i> ${res.clientPhone}
                </a>
            </td>
            <td>${barber ? barber.name.split(' ')[0] : 'Barbero'}</td>
            <td>
                <div style="font-weight: 600;">${service ? service.name : 'Servicio'}</div>
                <div style="font-size: 0.75rem; color: var(--color-text-muted);">$${servicePrice.toLocaleString('es-CL')}</div>
            </td>
            <td>${priorityBadge}</td>
            <td>
                <div style="font-weight: 600;">${formattedDate}</div>
                <div style="font-size: 0.75rem; color: var(--color-gold);">${res.time} Hrs</div>
            </td>
            <td>
                <span class="status-badge ${res.status}">${res.status}</span>
            </td>
            <td style="text-align: right;">
                <div class="table-actions-row" style="justify-content: flex-end;">
                    ${renderActionsByStatus(res)}
                </div>
            </td>
        `;

        tbody.appendChild(tr);
    });
}

function renderActionsByStatus(res) {
    if (res.status === 'pendiente') {
        return `
            <button class="btn action-btn-small confirm" onclick="changeStatus('${res.id}', 'confirmada')" title="Confirmar turno">Confirmar</button>
            <button class="btn action-btn-small cancel" onclick="changeStatus('${res.id}', 'cancelada')" title="Cancelar turno">Cancelar</button>
        `;
    } else if (res.status === 'confirmada') {
        return `
            <button class="btn action-btn-small complete" onclick="changeStatus('${res.id}', 'completada')" title="Marcar servicio como finalizado">Completar</button>
            <button class="btn action-btn-small cancel" onclick="changeStatus('${res.id}', 'cancelada')" title="Cancelar turno">Cancelar</button>
        `;
    }
    return `<span style="font-size: 0.75rem; color: var(--color-text-light);"><i class="fa-solid fa-lock"></i> Finalizado</span>`;
}

function changeStatus(id, newStatus) {
    const success = updateReservationStatus(id, newStatus);
    if (success) {
        renderAdminDashboard();
    }
}
