(() => {
  const statusElement = document.querySelector("[data-run-status]");
  const eventsUrl = statusElement?.dataset.eventsUrl;
  if (!eventsUrl || statusElement.dataset.terminal === "true") return;

  const source = new EventSource(eventsUrl);
  source.addEventListener("status", (event) => {
    const state = JSON.parse(event.data);
    statusElement.textContent = state.message;
    const countElement = document.querySelector("[data-run-count]");
    if (countElement) {
      countElement.textContent = `${state.success_count + state.error_count} / ${state.total_count}`;
    }
    if (state.terminal) {
      source.close();
      window.location.reload();
    }
  });
  source.onerror = () => {
    statusElement.textContent = "Connection lost. Refresh to check progress.";
  };
})();
