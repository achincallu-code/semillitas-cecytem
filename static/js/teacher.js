(() => {
  const tabButtons = [...document.querySelectorAll("[data-teacher-tab]")];
  const tabPanels = [...document.querySelectorAll("[data-teacher-panel]")];

  tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const tabName = button.dataset.teacherTab;

      tabButtons.forEach((tab) => {
        const active = tab === button;
        tab.classList.toggle("is-active", active);
        tab.setAttribute("aria-selected", String(active));
      });

      tabPanels.forEach((panel) => {
        panel.hidden = panel.dataset.teacherPanel !== tabName;
      });
    });
  });

  const searchInput = document.querySelector("#teacher-student-search");
  const studentCards = [...document.querySelectorAll(".teacher-student")];
  const emptyNotice = document.querySelector("#teacher-search-empty");

  if (!searchInput || !emptyNotice) return;

  searchInput.addEventListener("input", () => {
    const query = searchInput.value.trim().toLocaleLowerCase("es");
    let visibleStudents = 0;

    studentCards.forEach((card) => {
      const matches = card.dataset.studentName.includes(query);
      card.hidden = !matches;
      if (matches) visibleStudents += 1;
    });

    emptyNotice.hidden = studentCards.length === 0 || visibleStudents > 0;
  });
})();
