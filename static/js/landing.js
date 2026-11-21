(() => {
  const startLink = document.querySelector("[data-start-login]");
  if (!startLink || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  startLink.addEventListener("click", (event) => {
    if (document.body.classList.contains("landing-exit")) {
      event.preventDefault();
      return;
    }
    event.preventDefault();
    document.body.classList.add("landing-exit");
    window.setTimeout(() => window.location.assign(startLink.href), 520);
  });
})();
