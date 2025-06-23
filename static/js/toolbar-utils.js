// Utility to get all toolbar buttons (desktop and mobile)
function getToolbarButtons() {
  return {
    undo: [
      document.getElementById('undoButton'),
      document.getElementById('undoButtonDesktop')
    ].filter(Boolean),
    redo: [
      document.getElementById('redoButton'),
      document.getElementById('redoButtonDesktop')
    ].filter(Boolean),
    clear: [
      document.getElementById('clearCanvas'),
      document.getElementById('clearCanvasDesktop')
    ].filter(Boolean),
    calculate: [
      document.getElementById('calculateButton'),
      document.getElementById('calculateButtonDesktop')
    ].filter(Boolean)
  };
}

// Example: attach event listeners to all toolbar buttons
function setupToolbarEvents({ onUndo, onRedo, onClear, onCalculate }) {
  const btns = getToolbarButtons();
  btns.undo.forEach(btn => btn && btn.addEventListener('click', onUndo));
  btns.redo.forEach(btn => btn && btn.addEventListener('click', onRedo));
  btns.clear.forEach(btn => btn && btn.addEventListener('click', onClear));
  btns.calculate.forEach(btn => btn && btn.addEventListener('click', onCalculate));
}

// Example: update enabled/disabled state for all toolbar buttons
function setToolbarButtonState({ undo, redo }) {
  const btns = getToolbarButtons();
  btns.undo.forEach(btn => btn && (btn.disabled = !undo));
  btns.redo.forEach(btn => btn && (btn.disabled = !redo));
}

// Usage: In your main script.js, call setupToolbarEvents and setToolbarButtonState
// setupToolbarEvents({
//   onUndo: ...,
//   onRedo: ...,
//   onClear: ...,
//   onCalculate: ...
// });
// setToolbarButtonState({ undo: true/false, redo: true/false });
