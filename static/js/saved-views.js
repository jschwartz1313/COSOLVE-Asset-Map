for (const button of document.querySelectorAll("[data-copy-link]")) {
  button.addEventListener("click", async () => {
    const input = button.previousElementSibling;
    try {
      await navigator.clipboard.writeText(input.value);
      button.textContent = "Copied";
      window.setTimeout(() => {
        button.textContent = "Copy link";
      }, 1800);
    } catch {
      input.select();
    }
  });
}
