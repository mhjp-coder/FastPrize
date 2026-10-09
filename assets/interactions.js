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

function initializeHistoryTimezone() {
    const select = document.getElementById("history-timezone");
    if (!select) return;

    const localTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
    const supportedTimezones =
        typeof Intl.supportedValuesOf === "function"
            ? Intl.supportedValuesOf("timeZone")
            : [
                "America/Los_Angeles",
                "America/Denver",
                "America/Chicago",
                "America/New_York",
                "Europe/London",
                "Europe/Paris",
                "Asia/Kolkata",
                "Asia/Tokyo",
                "Australia/Sydney",
            ];
    const timezones = [...new Set(["UTC", localTimezone, ...supportedTimezones])];
    timezones.sort((left, right) => {
        if (left === "UTC") return -1;
        if (right === "UTC") return 1;
        return left.localeCompare(right);
    });
    select.replaceChildren(
        ...timezones.map(timezone => {
            const option = new Option(timezone.replaceAll("_", " "), timezone);
            option.classList.add("small-text");
            return option;
        })
    );

    const savedTimezone = localStorage.getItem("history-timezone");
    select.value = timezones.includes(savedTimezone) ? savedTimezone : localTimezone;

    function updateHistoryTimes() {
        const formatter = new Intl.DateTimeFormat("en-CA", {
            timeZone: select.value,
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
            time.textContent = `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}`;
        }
    }

    select.addEventListener("change", () => {
        localStorage.setItem("history-timezone", select.value);
        updateHistoryTimes();
    });
    updateHistoryTimes();
}

openAutoOpenDialogs();
initializeAddExpansions();
updateEditControls();
initializeHistoryTimezone();
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