import { ComponentRender, LogProvider } from "./gd5/engine/index.js";
import { HomePage } from "./HomePage.js";

const app = new ComponentRender({
  logProvider: new LogProvider({
    level: "info",
    sink: "console",
    context: { machId: "pyouter", userId: "local" },
  }),
});

app.init(
  { loading: "home", home: "home" },
  {
    home: HomePage,
  }
);

const boot = () => app.render();
if (document.readyState === "loading") {
  window.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}
