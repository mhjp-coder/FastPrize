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

openAutoOpenDialogs();
document.body.addEventListener("htmx:afterSwap", event => {
    if (event.target instanceof Element) openAutoOpenDialogs(event.target);
});

document.addEventListener("click", event => {
    for (const dialog of document.querySelectorAll(
        'dialog[data-close-on-backdrop="true"].active'
    )) {
        const bounds = dialog.getBoundingClientRect();
        const clickedOutside =
            event.clientX < bounds.left ||
            event.clientX > bounds.right ||
            event.clientY < bounds.top ||
            event.clientY > bounds.bottom;
        if (clickedOutside) ui(`#${dialog.id}`);
    }
});

document.addEventListener("change", event => {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || input.type !== "file") return;
    const label = document.getElementById(input.dataset.filenameTarget);
    const fileName = input.files?.[0]?.name;
    if (label && fileName) label.textContent = fileName;
});