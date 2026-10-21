const disclosures = [...document.querySelectorAll(".detail-page details")];
let printState;

window.addEventListener("beforeprint", () => {
  if (printState) return;
  printState = disclosures.map((details) => details.open);
  for (const details of disclosures) details.open = true;
});

window.addEventListener("afterprint", () => {
  if (!printState) return;
  disclosures.forEach((details, index) => { details.open = printState[index]; });
  printState = undefined;
});
