(() => {
  const tabs = [...document.querySelectorAll("[data-year-tab]")];
  const panels = [...document.querySelectorAll("[data-year-panel]")];

  if (tabs.length && panels.length) {
    function activate(tab, moveFocus = false) {
      const selectedYear = tab.dataset.yearTab;
      tabs.forEach((item) => {
        const selected = item === tab;
        item.setAttribute("aria-selected", String(selected));
        item.tabIndex = selected ? 0 : -1;
        item.classList.toggle("active", selected);
      });
      panels.forEach((panel) => {
        panel.hidden = panel.dataset.yearPanel !== selectedYear;
        panel.classList.toggle("active", !panel.hidden);
      });
      if (moveFocus) tab.focus();
    }

    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => activate(tab));
      tab.addEventListener("keydown", (event) => {
        let nextIndex;
        if (event.key === "ArrowRight") nextIndex = (index + 1) % tabs.length;
        else if (event.key === "ArrowLeft") nextIndex = (index - 1 + tabs.length) % tabs.length;
        else if (event.key === "Home") nextIndex = 0;
        else if (event.key === "End") nextIndex = tabs.length - 1;
        else return;
        event.preventDefault();
        activate(tabs[nextIndex], true);
      });
    });
  }

  const treeDialog = document.querySelector("#tree-dialog");
  const openTreeButton = document.querySelector("#tree-open");
  const closeTreeButton = document.querySelector("#tree-close");
  if (!treeDialog || !openTreeButton || !closeTreeButton) return;

  openTreeButton.addEventListener("click", () => {
    treeDialog.showModal();
    closeTreeButton.focus();
  });
  closeTreeButton.addEventListener("click", () => treeDialog.close());
  treeDialog.addEventListener("click", (event) => {
    if (event.target === treeDialog) treeDialog.close();
  });
  treeDialog.addEventListener("close", () => openTreeButton.focus());
})();
