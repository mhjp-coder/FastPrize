let faviconSourcePromise;
let logoSourcePromise;

async function updateBrandTheme() {
    const styles = getComputedStyle(document.body);
    const primary = styles.getPropertyValue("--primary").trim();
    const onPrimary = styles.getPropertyValue("--on-primary").trim();

    const logos = document.querySelectorAll(
        'img[src="/assets/fastprize-logo.svg"], img[data-brand-logo="true"]'
    );
    if (logos.length) {
        logoSourcePromise ||= fetch("/assets/fastprize-logo.svg").then(
            response => response.ok ? response.text() : ""
        );
        const logoSource = await logoSourcePromise;
        if (logoSource) {
            const themedLogo = logoSource.replace("#245f83", primary);
            const logoUrl = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(themedLogo)}`;
            for (const logo of logos) {
                logo.dataset.brandLogo = "true";
                logo.src = logoUrl;
            }
        }
    }

    const favicon = document.querySelector('link[rel="icon"]');
    if (!favicon) return;
    faviconSourcePromise ||= fetch("/assets/fastprize-favicon.svg").then(
        response => response.ok ? response.text() : ""
    );
    const faviconSource = await faviconSourcePromise;
    if (!faviconSource) return;
    const themedIcon = faviconSource
        .replace("#245f83", primary)
        .replace("#ffffff", onPrimary);
    favicon.href = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(themedIcon)}`;
}

function getThemePalette(name = localStorage.getItem("theme-palette")) {
    return Array.from(document.querySelectorAll("[data-theme-palette]")).find(
        button => button.dataset.themePalette === name
    );
}

async function setThemeMode(mode) {
    ui("mode", mode);
    let palette = getThemePalette();
    const savedPalette = localStorage.getItem("theme-palette");
    const savedColor = localStorage.getItem("theme-color");
    if (!palette && (savedPalette || !savedColor)) {
        palette = getThemePalette("sapphire") ||
            document.querySelector("[data-theme-palette]");
        if (palette) {
            localStorage.setItem("theme-palette", palette.dataset.themePalette);
        } else {
            localStorage.removeItem("theme-palette");
        }
    }
    if (palette) {
        const color = palette.dataset[
            mode === "dark" ? "themeColorDark" : "themeColorLight"
        ];
        await ui("theme", color);
        localStorage.setItem("theme-color", color);
    } else {
        await ui("theme", savedColor);
    }
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
        await setThemeMode(nextMode);
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
    const selectedPaletteButton = target?.closest("[data-theme-palette]");
    if (selectedPaletteButton) {
        const mode = ui("mode");
        const color = selectedPaletteButton.dataset[
            mode === "dark" ? "themeColorDark" : "themeColorLight"
        ];
        await ui("theme", color);
        localStorage.setItem("theme-color", color);
        localStorage.setItem(
            "theme-palette",
            selectedPaletteButton.dataset.themePalette
        );
        await updateBrandTheme();
        document.getElementById("theme-color-picker")?.close();
    }
});

const savedMode = localStorage.getItem("theme-mode") || "light";
const fixedMode = document.body.dataset.themeFixed;

if (fixedMode) {
    ui("mode", fixedMode);
    await ui("theme", "#82B1FF");
} else {
    await setThemeMode(savedMode);
}
await updateBrandTheme();

window.addEventListener("storage", async event => {
    if (fixedMode) return;
    if (event.key === "theme-mode") {
        await setThemeMode(event.newValue || "light");
    } else if (event.key === "theme-palette") {
        const mode = ui("mode");
        const palette = getThemePalette(event.newValue);
        const color = palette?.dataset[
            mode === "dark" ? "themeColorDark" : "themeColorLight"
        ] || localStorage.getItem("theme-color") || "#009688";
        await ui("theme", color);
    } else {
        return;
    }
    await updateBrandTheme();
});