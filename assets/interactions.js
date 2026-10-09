function openAutoOpenDialogs(root = document) {
    const selector = 'dialog[data-auto-open="true"]';
    const dialogs = [
        ...(root instanceof Element && root.matches(selector) ? [root] : []),
        ...root.querySelectorAll(selector),
    ];
    for (const dialog of dialogs) {
        if (!dialog.open) dialog.showModal();
    }
}

function updateAddExpansion(details) {
    const icon = details.querySelector("[data-add-expansion-chevron]");
    const summary = details.querySelector("summary");
    if (!icon || !summary) return;
    icon.textContent = details.open ? "expand_less" : "expand_more";
    summary.setAttribute("aria-expanded", String(details.open));
}

function initializeAddExpansions(root = document) {
    const selector = 'details[data-add-expansion="true"]';
    const expansions = [
        ...(root instanceof Element && root.matches(selector) ? [root] : []),
        ...root.querySelectorAll(selector),
    ];
    for (const details of expansions) {
        if (details.dataset.expansionInitialized) continue;
        details.addEventListener("toggle", () => updateAddExpansion(details));
        details.dataset.expansionInitialized = "true";
        updateAddExpansion(details);
    }
}

function updateEditControls() {
    for (const button of document.querySelectorAll("button[data-edit-target]")) {
        const target = document.getElementById(button.dataset.editTarget);
        button.disabled = Boolean(target?.hasAttribute("data-inline-edit"));
    }
    for (const element of document.querySelectorAll("[data-hide-while-editing]")) {
        const target = document.getElementById(element.dataset.hideWhileEditing);
        element.hidden = Boolean(target?.hasAttribute("data-inline-edit"));
    }
}

function updateHistoryTimes() {
    const formatter = new Intl.DateTimeFormat("en-CA", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hourCycle: "h23",
    });
    for (const time of document.querySelectorAll("time[data-history-time]")) {
        const parts = Object.fromEntries(
            formatter
                .formatToParts(new Date(time.dateTime))
                .map(({ type, value }) => [type, value])
        );
        time.querySelector("[data-history-date]").textContent =
            `${parts.year}-${parts.month}-${parts.day}`;
        time.querySelector("[data-history-clock]").textContent =
            `${parts.hour}:${parts.minute}`;
    }
}

openAutoOpenDialogs();
initializeAddExpansions();
updateEditControls();
updateHistoryTimes();
document.body.addEventListener("htmx:configRequest", event => {
    const token = document.querySelector('meta[name="csrf-token"]')?.content;
    if (token) event.detail.headers["X-CSRF-Token"] = token;
});
document.body.addEventListener("htmx:afterSwap", event => {
    if (event.target instanceof Element) {
        openAutoOpenDialogs(event.target);
        initializeAddExpansions(event.target);
        updateEditControls();
    }
});

document.addEventListener("click", event => {
    const target = event.target instanceof Element ? event.target : null;
    const liveThemeControls = document.querySelector(
        "#live-display-theme-controls"
    );
    if (
        liveThemeControls?.open &&
        !liveThemeControls.querySelector("summary")?.contains(target)
    ) {
        liveThemeControls.open = false;
        updateAddExpansion(liveThemeControls);
    }
    for (const dialog of document.querySelectorAll(
        'dialog[data-close-on-backdrop="true"][open]'
    )) {
        if (target?.closest(`[aria-controls="${dialog.id}"]`)) continue;
        const bounds = dialog.getBoundingClientRect();
        const clickedOutside =
            event.clientX < bounds.left ||
            event.clientX > bounds.right ||
            event.clientY < bounds.top ||
            event.clientY > bounds.bottom;
        if (clickedOutside) {
            if (dialog.classList.contains("active")) ui(`#${dialog.id}`);
            else dialog.close();
        }
    }
});

document.addEventListener("change", event => {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || input.type !== "file") return;
    const label = document.getElementById(input.dataset.filenameTarget);
    const fileName = input.files?.[0]?.name;
    if (label && fileName) label.textContent = fileName;
});