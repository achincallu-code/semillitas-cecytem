(() => {
  const scrollKey = "semillitas-post-scroll";
  const savedPosition = sessionStorage.getItem(scrollKey);
  if (savedPosition) {
    sessionStorage.removeItem(scrollKey);
    try {
      const position = JSON.parse(savedPosition);
      if (position.path === window.location.pathname && Number.isFinite(position.y)) {
        requestAnimationFrame(() => {
          document.documentElement.style.scrollBehavior = "auto";
          window.scrollTo(0, position.y);
          requestAnimationFrame(() => document.documentElement.style.removeProperty("scroll-behavior"));
        });
      }
    } catch (error) {
      console.error("No se pudo restaurar la posición de desplazamiento.", error);
    }
  }

  document.querySelectorAll("form[data-preserve-scroll]").forEach((form) => {
    form.addEventListener("submit", () => {
      sessionStorage.setItem(scrollKey, JSON.stringify({
        path: window.location.pathname,
        y: window.scrollY,
      }));
    });
  });
})();

(() => {
  document.querySelectorAll("[data-password-toggle]").forEach((button) => {
    const field = button.closest(".password-field");
    const input = field?.querySelector("input");
    if (!input) return;
    const hiddenLabel = button.getAttribute("aria-label") || "Mostrar contraseña";

    button.addEventListener("click", () => {
      const visible = input.type === "password";
      input.type = visible ? "text" : "password";
      button.setAttribute("aria-pressed", String(visible));
      button.setAttribute(
        "aria-label",
        visible ? "Ocultar contraseña" : hiddenLabel,
      );
      field.querySelector("[data-eye-open]").hidden = visible;
      field.querySelector("[data-eye-closed]").hidden = !visible;
    });
  });
})();

(() => {
  const button = document.querySelector("#sound-toggle");
  const music = document.querySelector("#background-music");
  if (!button || !music) return;
  music.volume = 0.2;
  const musicPreference = "semillitas-music-enabled";

  function setMusicButton(playing) {
    button.textContent = playing ? "🔊 Música" : "🔈 Música";
    button.setAttribute("aria-pressed", String(playing));
  }

  if (localStorage.getItem(musicPreference) === "true") {
    music.play().then(() => setMusicButton(true)).catch(() => {
      localStorage.removeItem(musicPreference);
      setMusicButton(false);
    });
  }

  button.addEventListener("click", async () => {
    if (music.paused) {
      try {
        await music.play();
        localStorage.setItem(musicPreference, "true");
        setMusicButton(true);
      } catch {
        setMusicButton(false);
        button.title = "Tu navegador no pudo reproducir la música.";
      }
    } else {
      music.pause();
      localStorage.setItem(musicPreference, "false");
      setMusicButton(false);
    }
  });
})();

(() => {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || !("IntersectionObserver" in window)) return;

  const sections = document.querySelectorAll(".hero-banner, .stats-grid, .tree-card, .section-block, .auth-layout, .form-card, .game-shell");
  if (!sections.length) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("is-visible");
      observer.unobserve(entry.target);
    });
  }, { threshold: 0.08 });

  sections.forEach((section) => {
    section.classList.add("reveal-on-scroll");
    observer.observe(section);
  });
})();
