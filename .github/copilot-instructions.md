
## Tech Stack
- The project is designed to be a small web application with a focus on simplicity and speed. 
- It is built using FastHTML, which is a lightweight framework that allows for rapid development of web applications. 
- The application uses Fastlite's Database and Table APIs for database access, which provides a simple and efficient way to interact with the SQLite database. 
- The project also uses BeerCSS for styling, which is a lightweight CSS framework that provides a clean and modern look to the application.
- This project is managed with uv. 

## Coding Standards and Best Practices
- Always follow the project's coding standards and best practices to ensure consistency and maintainability across the codebase. 
- When contributing to the project, make sure to write clear and concise code, provide meaningful commit messages, and include appropriate documentation for any new features or changes.
- Ensure that all code is properly tested and that any new functionality is covered by automated tests to maintain the project's reliability and stability.
- Regularly review and refactor the code to improve its quality, readability, and performance, while keeping the project's architecture and design principles in mind.
- Keep dependencies up to date and ensure that any third-party libraries used in the project are secure and compatible with the project's requirements.
- Follow security best practices to protect the application and its data from potential vulnerabilities and threats.
- Adhere to the principles of clean code, ensuring that the codebase remains easy to understand, maintain, and extend over time.
- Use ruff to enforce consistent code style and catch potential issues early in the development process.

## Design Principles
- Use BeerCSS to maintain a consistent and modern design throughout the application.
- Do Not override BeerCSS classes with custom styles unless necessary.
- Use BeerCSS classes consistently to ensure a cohesive and visually appealing design throughout the application.
- Use BeerCSS Compact layout.
- Use BeerCSS Grid system for layout consistency and responsiveness.
- Utilize BeerCSS utility classes to streamline styling and maintain a consistent design language.
- Ensure that all custom styles complement BeerCSS and do not conflict with its classes.
- Keep the user interface simple and intuitive, ensuring that users can easily navigate and interact with the application.
- Follow responsive design principles to provide a seamless experience across different devices and screen sizes.
- Use semantic HTML elements to improve the structure, accessibility, and SEO of the application.
- Ensure that the application follows a consistent design language and visual hierarchy to enhance user experience.
- Maintain a balance between aesthetics and performance to provide a visually appealing yet fast and responsive application.

# FastHTML + BeerCSS Coding Instructions & UI Archetype

You are an expert Python assistant generating FastHTML application layouts styled exclusively with the BeerCSS framework. Replace all PicoCSS defaults with clean semantic BeerCSS components using Python definitions. Follow these whitespace rules, responsive standards, and theme/localStorage persistence configurations.

## 1. UI Archetype: High-Whitespace & Large Elements
*   **Element Sizing:** Default to larger interactive footprints. Apply framework modifier classes like `"large"` or `"extra"` directly inside FastHTML components: `Button("Click Me", cls="large primary")`, `Article(cls="large medium-padding round")`.
*   **Whitespace & Layout Spacing:** Prevent crowded layouts. Use padding and margin helpers liberally (`p`, `m`, `padding`, `margin`). Prioritize heavy, intentional breathing room via utility steps: `"large-padding"`, `"extra-padding"`, `"large-margin"`, and `"large-space"`.
*   **Typography:** Set bold hierarchies using `"max"` or `"large-text"` classes on headers (`H1`, `H2`, `H3`), ensuring plenty of spatial padding above and below.

## 2. Responsive Layout & Sidebar Navigation Architecture
Construct adaptive multi-device structures using BeerCSS structural standards rather than relying on generic custom wrapper layers.
*   **Structure Sequence:** The Navigation layout (`Nav()`) must be placed structurally *before* the main content area (`Main()`).
*   **Desktop & Mobile Sidebar Structure:** 
    *   For standard desktop sidebars, utilize `Nav(cls="left drawer large-padding")`.
    *   To build an interface responsive to all screen widths, apply adaptive visibility layout tokens (`"m"`, `"l"`, or hidden helpers). Ensure navigation items wrap internal anchor blocks cleanly:
    ```python
    Nav(
        A(I("home"), Div("Home"), href="/"),
        A(I("settings"), Div("Settings"), href="/settings"),
        cls="left drawer large-padding max"
    )
    ```
*   **Main content block:** Always pair the sidebar layout with exactly one main content element configured for responsiveness and spacing: `Main(cls="responsive large-padding")`.
*   **Grid System Breakpoints:** Distribute sub-elements using a fluid 12-column template: `Div(..., cls="grid")` with columns explicitly declaring breakpoint spans: `Div("Content", cls="s12 m4 l4")`.

## 3. Dark Mode, Dynamic Themes, & LocalStorage Persistence
Implement full interface adjustments leveraging BeerCSS runtime JavaScript helper tools, persisting selections seamlessly via standard `localStorage` keys (`'theme-mode'` and `'theme-color'`).

*   **Initialization Header Script:** Ensure the global base layout emits a brief inline `<script>` tag in its header immediately after loading BeerCSS. This prevents layout shift by resolving theme settings *before* rendering the full body:
    ```python
    Script("""
        document.addEventListener('DOMContentLoaded', () => {
            const savedMode = localStorage.getItem('theme-mode') || 'light';
            const savedColor = localStorage.getItem('theme-color') || '#009688';
            ui('mode', savedMode);
            ui('theme', savedColor);
        });
    """)
    ```
*   **Light/Dark Toggle Execution:** Use an interactive macro that evaluates the current system state, applies the flip via `ui()`, and updates `localStorage`:
    ```python
    Button(
        I("dark_mode"), 
        onclick="""
            const nextMode = ui('mode') === 'dark' ? 'light' : 'dark';
            ui('mode', nextMode);
            localStorage.setItem('theme-mode', nextMode);
        """, 
        cls="circle flat large"
    )
    ```
*   **Dynamic Theme Picker Design:** Pass runtime color changes to a dedicated utility function that syncs your theme cache keys:
    ```python
    # Dynamic Palette Selection Controls
    Div(
        Button("Teal", onclick="ui('theme', '#009688'); localStorage.setItem('theme-color', '#009688');", cls="chip"),
        Button("Amber", onclick="ui('theme', '#ffc107'); localStorage.setItem('theme-color', '#ffc107');", cls="chip"),
        cls="row large-space"
    )
    ```

## 4. Core Framework Rules (Do's and Don'ts)
*   **DO NOT** nest complex framework style identifiers on single structures (`cls="element element helper"`). Rely on flat, cascading Material Design 3 utility attributes.
*   **DO NOT** generate custom component wrapper boilerplate like `cls="card-header"` or `cls="card-body"`. BeerCSS maps styles directly down to nested semantic HTML children inside an `Article()` block.
*   **DO** explicitly declare state semantics with utility bindings like `"primary"`, `"secondary"`, `"error"`, or contrasting textual labels such as `"secondary-text"`.
