/** Light/dark theme persistence (localStorage key: vg-theme).
 *  The default is dark - index.html applies it before first paint. */
export type Theme = "light" | "dark";

const KEY = "vg-theme";

export function currentTheme(): Theme {
  try {
    return localStorage.getItem(KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

export function setTheme(theme: Theme): void {
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    /* private mode - the attribute below still flips this session */
  }
  document.documentElement.setAttribute("data-theme", theme);
  // keep the browser chrome (address bar / PWA window) in step
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", theme === "light" ? "#f1f5f9" : "#020617");
}
