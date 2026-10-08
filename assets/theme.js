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

document.addEventListener("click", async event => {
    const target = event.target instanceof Element ? event.target : null;
    const modeButton = target?.closest("[data-theme-mode='toggle']");
    if (modeButton) {
        const nextMode = ui("mode") === "dark" ? "light" : "dark";
        ui("mode", nextMode);
        localStorage.setItem("theme-mode", nextMode);
        await updateBrandTheme();
        return;
    }
    const colorButton = target?.closest("[data-theme-color]");
    if (colorButton) await setThemeColor(colorButton.dataset.themeColor);
});

const savedMode = localStorage.getItem("theme-mode") || "light";
const savedColor = localStorage.getItem("theme-color") || "#009688";

ui("mode", savedMode);
await ui("theme", savedColor);
await updateBrandTheme();