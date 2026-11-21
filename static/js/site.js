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
