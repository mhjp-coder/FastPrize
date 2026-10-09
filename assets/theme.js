let faviconSourcePromise;

async function updateBrandTheme() {
    const favicon = document.querySelector('link[rel="icon"]');
    if (!favicon) return;
    faviconSourcePromise ||= fetch("/assets/fastprize-favicon.svg").then(
        response => response.ok ? response.text() : ""
    );
    const source = await faviconSourcePromise;
    if (!source) return;
    const styles = getComputedStyle(document.body);
    const primary = styles.getPropertyValue("--primary").trim();
    const onPrimary = styles.getPropertyValue("--on-primary").trim();
    const themedIcon = source
        .replace("#245f83", primary)
        .replace("#ffffff", onPrimary);
    favicon.href = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(themedIcon)}`;
}

async function setThemeColor(color) {
    await ui("theme", color);
    localStorage.setItem("theme-color", color);
    await updateBrandTheme();
}

function setThemeMode(mode) {
    ui("mode", mode);
    const nextMode = mode === "dark" ? "light" : "dark";
    const iconName = nextMode === "dark" ? "dark_mode" : "light_mode";
    const label = `Switch to ${nextMode} mode`;
    for (const button of document.querySelectorAll("[data-theme-mode='toggle']")) {
        const icon = button.querySelector("[data-theme-mode-icon='true']");
        if (!icon) continue;
        icon.textContent = iconName;
        button.title = label;
        button.setAttribute("aria-label", label);
    }
    if (document.body.classList.contains("screen")) {
        document.body.dataset.liveTheme = mode;
    }
}

document.addEventListener("click", async event => {
    const target = event.target instanceof Element ? event.target : null;
    const modeButton = target?.closest("[data-theme-mode='toggle']");
    if (modeButton) {
        const nextMode = ui("mode") === "dark" ? "light" : "dark";
        setThemeMode(nextMode);
        localStorage.setItem("theme-mode", nextMode);
        await updateBrandTheme();
        return;
    }
    const paletteButton = target?.closest("[data-theme-picker-open='true']");
    if (paletteButton) {
        const dialog = document.getElementById("theme-color-picker");
        if (dialog && !dialog.open) dialog.showModal();
        return;
    }
    const colorButton = target?.closest("[data-theme-color]");
    if (colorButton) {
        await setThemeColor(colorButton.dataset.themeColor);
        document.getElementById("theme-color-picker")?.close();
    }
});

const savedMode = localStorage.getItem("theme-mode") || "light";
const savedColor = localStorage.getItem("theme-color") || "#009688";

setThemeMode(savedMode);
await ui("theme", savedColor);
await updateBrandTheme();

window.addEventListener("storage", async event => {
    if (event.key !== "theme-mode") return;
    setThemeMode(event.newValue || "light");
    await updateBrandTheme();
});