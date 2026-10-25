import { useState } from "react";
import { Moon, Sun } from "lucide-react";
import { currentTheme, setTheme, type Theme } from "../theme";

/** Sun/moon pill that flips the whole app between the dark and light themes. */
export default function ThemeToggle({
  className = "btn-ghost w-full !py-1.5 text-xs",
}: {
  className?: string;
}) {
  const [theme, setLocal] = useState<Theme>(() => currentTheme());

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setLocal(next);
    setTheme(next);
  }

  return (
    <button
      type="button"
      className={className}
      onClick={toggle}
      aria-label="Toggle color theme"
      title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
    >
      {theme === "dark" ? (
        <Sun className="h-3.5 w-3.5 text-amber-400" />
      ) : (
        <Moon className="h-3.5 w-3.5 text-indigo-500" />
      )}
      {theme === "dark" ? "Light theme" : "Dark theme"}
    </button>
  );
}
