// TaskControl Vanilla JS (Principio de Restricciones Técnicas - sin framework SPA)
document.addEventListener("DOMContentLoaded", () => {
    // 1. Auto-desvanecer mensajes flash después de 5 segundos
    const alerts = document.querySelectorAll(".alert");
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = "opacity 0.5s ease";
            alert.style.opacity = "0";
            setTimeout(() => alert.remove(), 500);
        }, 5000);
    });

    // 2. Validación preventiva en el cliente para el formulario de registro
    const registerForm = document.querySelector("form[action*='register']");
    if (registerForm) {
        registerForm.addEventListener("submit", (e) => {
            const passwordInput = registerForm.querySelector("input[name='password']");
            if (passwordInput && passwordInput.value.length < 8) {
                e.preventDefault();
                alert("La contraseña debe tener al menos 8 caracteres.");
                passwordInput.focus();
            }
        });
    }

    // 3. Validación preventiva en el cliente para tareas
    const taskForms = document.querySelectorAll("form[action*='tasks']");
    taskForms.forEach(form => {
        form.addEventListener("submit", (e) => {
            const titleInput = form.querySelector("input[name='title']");
            if (titleInput && titleInput.value.trim() === "") {
                e.preventDefault();
                alert("El título de la tarea no puede estar vacío.");
                titleInput.focus();
            }
        });
    });

    // 4. Completar sin recarga (HU-15, Inc.5): fetch contra el contrato
    // existente POST /tasks/<id>/status con actualización optimista y
    // reversión garantizada ante fallo (FR-003/FR-004). Sin fetch disponible
    // se conserva el flujo base con recarga (degradación, FR-015).
    (function initCompleteWithoutReload() {
        const list = document.querySelector("[data-task-list]");
        const flash = document.getElementById("js-flash");
        if (!list || !window.fetch) return;

        function showMessage(text) {
            if (!flash) return;
            flash.innerHTML = "";
            const box = document.createElement("div");
            box.className = "alert alert-error";
            box.setAttribute("role", "alert");
            box.textContent = text;
            flash.appendChild(box);
            setTimeout(() => box.remove(), 8000);
        }

        function currentFilterStatus() {
            const params = new URLSearchParams(window.location.search);
            return params.get("status");
        }

        function wireCard(card) {
            card.querySelectorAll(".js-complete-btn").forEach((btn) => {
                if (btn.dataset.wired) return;
                btn.dataset.wired = "1";
                btn.addEventListener("click", (e) => {
                    e.preventDefault();
                    completeTask(btn, card);
                });
            });
        }

        async function completeTask(button, card) {
            const taskId = button.dataset.taskId;
            card.querySelectorAll("button").forEach((b) => { b.disabled = true; });
            // Instantánea previa para reversión (estado confirmado anterior).
            const snapshot = {
                status: card.dataset.status,
                cardHTML: card.innerHTML,
            };
            // Estado provisional: marcar como completada de inmediato.
            card.dataset.status = "completed";
            const badge = card.querySelector(".badge-pending, .badge-in_progress");
            if (badge) {
                badge.className = "badge badge-completed";
                badge.textContent = "Completada";
            }

            let confirmed = false;
            try {
                const response = await fetch(`/tasks/${taskId}/status`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    body: JSON.stringify({ status: "completed" }),
                });
                let body = null;
                try { body = await response.json(); } catch (e) { body = null; }
                if (response.ok && body && body.status === "success") {
                    confirmed = true;
                } else if (response.status === 401) {
                    throw new Error("Tu sesión expiró. Vuelve a iniciar sesión.");
                } else if (body && body.message) {
                    throw new Error(body.message);
                } else {
                    throw new Error("No se pudo completar la tarea. Inténtalo de nuevo.");
                }
            } catch (err) {
                // Reversión obligatoria: restaurar el estado anterior confirmado.
                card.dataset.status = snapshot.status;
                card.innerHTML = snapshot.cardHTML;
                showMessage(err && err.message
                    ? err.message
                    : "No se pudo completar la tarea. Inténtalo de nuevo.");
                wireCard(card);
                return;
            }

            if (confirmed) {
                // Estado definitivo confirmado por el backend.
                const filter = currentFilterStatus();
                if (filter === "pending" || filter === "in_progress") {
                    card.remove();
                } else {
                    const actions = card.querySelectorAll("div[style*='flex']")[0];
                    if (actions) {
                        actions.innerHTML =
                            `<form action="/tasks/${taskId}/reopen" method="POST" class="inline-form">` +
                            `<button type="submit" class="btn btn-primary btn-sm">Reabrir</button></form>`;
                    }
                }
            }
        }

        list.querySelectorAll("[data-task-id]").forEach(wireCard);
    })();

    // 5. Reordenamiento manual (HU-16, Inc.5): Drag-and-Drop nativo +
    // botones subir/bajar por teclado, con persistencia inmediata por vista
    // vía POST /tasks/reorder y reversión ante fallo (FR-010). Sin fetch
    // disponible el listado conserva el flujo base (FR-015).
    (function initManualReorder() {
        const list = document.querySelector("[data-task-list]");
        const flash = document.getElementById("js-flash");
        if (!list || !window.fetch) return;

        let draggedId = null;
        let dragPrevious = null;
        let chain = Promise.resolve();

        function showMessage(text) {
            if (!flash) return;
            flash.innerHTML = "";
            const box = document.createElement("div");
            box.className = "alert alert-error";
            box.setAttribute("role", "alert");
            box.textContent = text;
            flash.appendChild(box);
            setTimeout(() => box.remove(), 8000);
        }

        function cards() {
            return Array.from(list.querySelectorAll("[data-task-id]"));
        }

        function currentIds() {
            return cards().map((c) => parseInt(c.dataset.taskId, 10));
        }

        function currentView() {
            const params = new URLSearchParams(window.location.search);
            return params.get("status") || "all";
        }

        function refreshSortAttrs() {
            cards().forEach((c, i) => { c.dataset.sortOrder = String(i); });
        }

        function restoreOrder(previousOrder) {
            const byId = {};
            cards().forEach((c) => { byId[c.dataset.taskId] = c; });
            previousOrder.forEach((id) => {
                const card = byId[String(id)];
                if (card) list.appendChild(card);
            });
            refreshSortAttrs();
        }

        async function persist(previousOrder) {
            try {
                const response = await fetch("/tasks/reorder", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    body: JSON.stringify({
                        ordered_ids: currentIds(),
                        view: currentView(),
                    }),
                });
                let body = null;
                try { body = await response.json(); } catch (e) { body = null; }
                if (response.ok && body && body.status === "success") {
                    refreshSortAttrs();
                    return;
                }
                if (response.status === 401) {
                    throw new Error("Tu sesión expiró. Vuelve a iniciar sesión.");
                }
                throw new Error(body && body.message
                    ? body.message
                    : "No se pudo guardar el nuevo orden. Inténtalo de nuevo.");
            } catch (err) {
                // Reversión al orden anterior confirmado + mensaje.
                restoreOrder(previousOrder);
                showMessage(err && err.message
                    ? err.message
                    : "No se pudo guardar el nuevo orden. Inténtalo de nuevo.");
            }
        }

        function schedulePersist(previousOrder) {
            chain = chain.then(() => persist(previousOrder));
            return chain;
        }

        // --- Arrastrar y soltar (puntero) ---
        list.addEventListener("dragstart", (e) => {
            const card = e.target.closest("[data-task-id]");
            if (!card) return;
            draggedId = card.dataset.taskId;
            dragPrevious = currentIds();
            e.dataTransfer.effectAllowed = "move";
            try { e.dataTransfer.setData("text/plain", draggedId); } catch (err) { /* noop */ }
        });

        list.addEventListener("dragover", (e) => {
            if (!draggedId) return;
            const over = e.target.closest("[data-task-id]");
            if (!over || over.dataset.taskId === draggedId) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = "move";
            const rect = over.getBoundingClientRect();
            const before = (e.clientY - rect.top) < rect.height / 2;
            const dragged = list.querySelector(`[data-task-id="${draggedId}"]`);
            if (dragged) {
                if (before) list.insertBefore(dragged, over);
                else list.insertBefore(dragged, over.nextSibling);
            }
        });

        list.addEventListener("drop", (e) => {
            if (!draggedId) return;
            e.preventDefault();
            const previousOrder = dragPrevious || currentIds();
            const changed = previousOrder.join() !== currentIds().join();
            draggedId = null;
            dragPrevious = null;
            // Soltar sin cambio observable: sin persistencia ni errores.
            if (changed) schedulePersist(previousOrder);
        });

        list.addEventListener("dragend", () => { draggedId = null; });

        // --- Botones subir/bajar (teclado y lector de pantalla) ---
        list.addEventListener("click", (e) => {
            const btn = e.target.closest(".js-move-btn");
            if (!btn) return;
            const card = btn.closest("[data-task-id]");
            if (!card) return;
            const previousOrder = currentIds();
            const sibling = btn.dataset.direction === "up"
                ? card.previousElementSibling
                : card.nextElementSibling;
            if (!sibling || !sibling.hasAttribute("data-task-id")) return;
            if (btn.dataset.direction === "up") list.insertBefore(card, sibling);
            else list.insertBefore(sibling, card);
            refreshSortAttrs();
            schedulePersist(previousOrder);
            btn.focus();
        });
    })();
});
