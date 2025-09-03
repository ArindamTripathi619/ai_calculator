document.addEventListener("DOMContentLoaded", function () {
  const canvas = document.getElementById("drawingCanvas");
  const ctx = canvas.getContext("2d");
  const colorTools = document.querySelectorAll(".color-tool");
  const clearButton = document.getElementById("clearCanvas");
  const calculateButton = document.getElementById("calculateButton");
  const resultContainer = document.getElementById("resultContainer");
  const resultBox = document.getElementById("resultBox");
  const closeResult = document.getElementById("closeResult");
  const undoButton = document.getElementById("undoButton");
  const redoButton = document.getElementById("redoButton");
  const onboardingModal = document.getElementById("onboardingModal");
  const startButton = document.getElementById("startButton");
  const onboardingTitle = document.getElementById("onboardingTitle");
  const onboardingDescription = document.getElementById("onboardingDescription");
  const prevButton = document.getElementById("prevButton");
  const nextButton = document.getElementById("nextButton");
  const skipButton = document.getElementById("skipButton");

  let currentStep = 0;

  function highlightElement(selector) {
    const element = document.querySelector(selector);
    if (element) {
      element.style.boxShadow = "0 0 10px 3px #ffcc00";
      element.style.zIndex = "1000";
    }
  }

  function removeHighlight(selector) {
    const element = document.querySelector(selector);
    if (element) {
      element.style.boxShadow = "";
      element.style.zIndex = "";
    }
  }

  const steps = [
    {
      title: "Welcome to AI Calculator",
      description: "This app helps you solve mathematical equations using AI.",
      highlight: null,
    },
    {
      title: "Step 1: Draw Your Equation",
      description: "Use the canvas to draw your equation.",
      highlight: "#drawingCanvas",
    },
    {
      title: "Step 2: Calculate",
      description: "Click the 'Calculate' button to get the solution.",
      highlight: "#calculateButton",
    },
    {
      title: "Step 3: Toolbar Features",
      description: "Use Undo, Redo, and Clear buttons for better control.",
      highlight: ".toolbar",
    },
  ];

  function updateOnboarding(step) {
    onboardingTitle.textContent = steps[step].title;
    onboardingDescription.textContent = steps[step].description;

    // Remove highlight from the previous step
    if (steps[step - 1]?.highlight) {
      removeHighlight(steps[step - 1].highlight);
    }

    // Highlight the current step
    if (steps[step]?.highlight) {
      highlightElement(steps[step].highlight);
    }

    prevButton.disabled = step === 0;
    nextButton.textContent = step === steps.length - 1 ? "Finish" : "Next";
  }

  function updateProgressIndicators(step) {
    const dots = document.querySelectorAll(".dot");
    dots.forEach((dot, index) => {
      dot.classList.toggle("active", index === step);
    });
  }

  prevButton.addEventListener("click", function () {
    if (currentStep > 0) {
      currentStep--;
      updateOnboarding(currentStep);
      updateProgressIndicators(currentStep);
    }
  });

  function showConfetti() {
    // Create and append the confetti canvas
    const confettiCanvas = document.createElement("canvas");
    confettiCanvas.id = "confettiCanvas";
    document.body.appendChild(confettiCanvas);

    // Initialize the confetti animation
    const confetti = new ConfettiGenerator({ target: "confettiCanvas" });
    confetti.render();

    // Play confetti music
    const confettiAudio = new Audio("/static/audio/confetti.mp3"); // Path to your audio file
    confettiAudio.play();

    // Stop the confetti animation and remove the canvas after 5 seconds
    setTimeout(() => {
      confetti.clear();
      document.body.removeChild(confettiCanvas);
      confettiAudio.pause(); // Stop the audio
      confettiAudio.currentTime = 0; // Reset the audio to the beginning
    }, 2200);
  }

  nextButton.addEventListener("click", function () {
    if (currentStep < steps.length - 1) {
      currentStep++;
      updateOnboarding(currentStep);
      updateProgressIndicators(currentStep);
    } else {
      onboardingModal.style.display = "none";
      localStorage.setItem("onboardingSeen", "true");
      showConfetti(); // Trigger confetti on completion
      resizeCanvas(); // Ensure canvas is resized and interactive after onboarding
    }
  });

  skipButton.addEventListener("click", function () {
    onboardingModal.style.display = "none";
    localStorage.setItem("onboardingSeen", "true");
    resizeCanvas(); // Ensure canvas is resized and interactive after onboarding
  });

  // Show onboarding only if not seen before
  if (!localStorage.getItem("onboardingSeen")) {
    onboardingModal.style.display = "flex";
    updateOnboarding(currentStep);
  }

  // History states for undo/redo
  let undoStack = [];
  let redoStack = [];
  const MAX_HISTORY_SIZE = 50; // Limit the history size to prevent memory issues

  // Set canvas size
  function resizeCanvas() {
    const canvasContainer = document.querySelector(".canvas-container");
    canvas.width = canvasContainer.offsetWidth;
    canvas.height = canvasContainer.offsetHeight;

    // Restore current state if it exists
    if (undoStack.length > 0) {
      const currentState = undoStack[undoStack.length - 1];
      ctx.putImageData(currentState, 0, 0);
    } else {
      // Set background to black
      ctx.fillStyle = "black";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Save initial state
      saveState();
    }
  }

  window.addEventListener("resize", resizeCanvas);

  // Drawing variables
  let isDrawing = false;
  let lastX = 0;
  let lastY = 0;
  let currentColor = "white";
  let lineWidth = 2;
  let hasDrawnSinceLastSave = false;

  // Color selection
  colorTools.forEach((tool) => {
    tool.addEventListener("click", function () {
      // Remove active class from all tools
      colorTools.forEach((t) => t.classList.remove("active"));
      // Add active class to selected tool
      this.classList.add("active");

      // Set current color or eraser
      if (this.dataset.color === "eraser") {
        currentColor = "black";
        lineWidth = 20; // Larger width for eraser
      } else {
        currentColor = this.dataset.color;
        lineWidth = 2; // Default width for drawing
      }
    });
  });

  // Save the current state to the undo stack
  function saveState() {
    // Limit the stack size
    if (undoStack.length >= MAX_HISTORY_SIZE) {
      undoStack.shift(); // Remove the oldest state
    }

    const currentState = ctx.getImageData(0, 0, canvas.width, canvas.height);
    undoStack.push(currentState);

    // Clear the redo stack when new changes are made
    redoStack = [];

    // Update button states
    updateButtons();

    hasDrawnSinceLastSave = false;
  }

  // Update the enabled/disabled state of undo/redo buttons
  function updateButtons() {
    setToolbarButtonState({
      undo: undoStack.length > 1,
      redo: redoStack.length > 0
    });
  }

  // Drawing functions
  function startDrawing(e) {
    isDrawing = true;
    [lastX, lastY] = getMousePos(canvas, e);
    hasDrawnSinceLastSave = false; // Reset the flag when starting a new stroke
  }

  function draw(e) {
    if (!isDrawing) return;

    const [x, y] = getMousePos(canvas, e);

    ctx.beginPath();
    ctx.moveTo(lastX, lastY);
    ctx.lineTo(x, y);
    ctx.strokeStyle = currentColor;
    ctx.lineWidth = lineWidth;
    ctx.lineCap = "round";
    ctx.stroke();

    [lastX, lastY] = [x, y];

    hasDrawnSinceLastSave = true;
  }

  function stopDrawing() {
    if (isDrawing && hasDrawnSinceLastSave) {
      saveState();
    }
    isDrawing = false;
  }

  // Get mouse position relative to canvas
  function getMousePos(canvas, evt) {
    const rect = canvas.getBoundingClientRect();
    return [
      ((evt.clientX - rect.left) / (rect.right - rect.left)) * canvas.width,
      ((evt.clientY - rect.top) / (rect.bottom - rect.top)) * canvas.height,
    ];
  }

  // Touch support
  function getTouchPos(canvas, evt) {
    const rect = canvas.getBoundingClientRect();
    return [
      ((evt.touches[0].clientX - rect.left) / (rect.right - rect.left)) *
        canvas.width,
      ((evt.touches[0].clientY - rect.top) / (rect.bottom - rect.top)) *
        canvas.height,
    ];
  }

  function handleStart(e) {
    e.preventDefault();
    isDrawing = true;
    [lastX, lastY] = getTouchPos(canvas, e);
    hasDrawnSinceLastSave = false;
  }

  function handleMove(e) {
    e.preventDefault();
    if (!isDrawing) return;

    const [x, y] = getTouchPos(canvas, e);

    ctx.beginPath();
    ctx.moveTo(lastX, lastY);
    ctx.lineTo(x, y);
    ctx.strokeStyle = currentColor;
    ctx.lineWidth = lineWidth;
    ctx.lineCap = "round";
    ctx.stroke();

    [lastX, lastY] = [x, y];

    hasDrawnSinceLastSave = true;
  }

  // Undo function
  function undo() {
    if (undoStack.length > 1) {
      // Keep at least the initial state
      // Save current state to redo stack
      const currentState = undoStack.pop();
      redoStack.push(currentState);

      // Restore the previous state
      const previousState = undoStack[undoStack.length - 1];
      ctx.putImageData(previousState, 0, 0);

      // Update button states
      updateButtons();
    }
  }

  // Redo function
  function redo() {
    if (redoStack.length > 0) {
      // Get the state to redo
      const redoState = redoStack.pop();

      // Add it to the undo stack
      undoStack.push(redoState);

      // Restore the state
      ctx.putImageData(redoState, 0, 0);

      // Update button states
      updateButtons();
    }
  }

  // Clear canvas function
  function clearCanvas() {
    // Save current state before clearing
    saveState();

    // Clear the canvas
    ctx.fillStyle = "black";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Save the cleared state
    saveState();
  }

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

  function setupToolbarEvents({ onUndo, onRedo, onClear, onCalculate }) {
    const btns = getToolbarButtons();
    btns.undo.forEach(btn => btn && btn.addEventListener('click', onUndo));
    btns.redo.forEach(btn => btn && btn.addEventListener('click', onRedo));
    btns.clear.forEach(btn => btn && btn.addEventListener('click', onClear));
    btns.calculate.forEach(btn => btn && btn.addEventListener('click', onCalculate));
  }

  function setToolbarButtonState({ undo, redo }) {
    const btns = getToolbarButtons();
    btns.undo.forEach(btn => btn && (btn.disabled = !undo));
    btns.redo.forEach(btn => btn && (btn.disabled = !redo));
  }

  // Replace single button references with toolbar-utils
  const btns = getToolbarButtons();

  // Attach event listeners to all toolbar buttons
  setupToolbarEvents({
    onUndo: undo,
    onRedo: redo,
    onClear: clearCanvas,
    onCalculate: function () {
      // Get canvas data
      const imageData = canvas.toDataURL("image/png");
      resultBox.innerHTML = "<p>Processing your equation...</p>";
      resultContainer.style.display = "flex";
      fetch("/calculate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: imageData }),
      })
        .then((response) => {
          if (!response.ok) throw new Error(`Server responded with status: ${response.status}`);
          return response.text();
        })
        .then((text) => {
          let data;
          try { data = JSON.parse(text); } catch (e) { throw new Error("Failed to parse server response as JSON."); }
          return data;
        })
        .then((data) => {
          if (data.success) {
            resultBox.innerHTML = data.solution || "Solution processed successfully but was empty.";
            if (window.MathJax) { try { MathJax.typeset(); } catch (err) { console.error("MathJax error:", err); } }
          } else {
            resultBox.innerHTML = `<p>Error: ${data.error || "Unknown error occurred"}</p>`;
          }
        })
        .catch((error) => {
          resultBox.innerHTML = `<p>Error: ${error.message}</p><p>Please try again or try with a simpler equation.</p>`;
        });
    }
  });

  // Initialize the canvas
  resizeCanvas();

  // Add drawing event listeners
  // Mouse events
  canvas.addEventListener("mousedown", startDrawing);
  canvas.addEventListener("mousemove", draw);
  canvas.addEventListener("mouseup", stopDrawing);
  canvas.addEventListener("mouseleave", stopDrawing);

  // Touch events
  canvas.addEventListener("touchstart", handleStart, { passive: false });
  canvas.addEventListener("touchmove", handleMove, { passive: false });
  canvas.addEventListener("touchend", stopDrawing);
  canvas.addEventListener("touchcancel", stopDrawing);

  // Add event listener to close the result overlay
  closeResult.addEventListener("click", function () {
    resultContainer.style.display = "none";
  });
});
