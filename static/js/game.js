(() => {
  const data = JSON.parse(document.querySelector("#game-data").textContent);
  const stage = document.querySelector("#game-stage");
  const status = document.querySelector("#game-status");
  const progress = document.querySelector("#progress-bar");
  const result = document.querySelector("#game-result");
  const activityRoot = document.querySelector("#activity-root");
  let questionNumber = 1;
  let busy = false;
  const repeatInstruction = document.querySelector("#repeat-instruction");

  const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
  const mediaHref = (filename) => `${data.mediaUrl}${String(filename).split("/").map(encodeURIComponent).join("/")}`;
  const playSound = (filename) => {
    const sound = new Audio(mediaHref(filename));
    sound.volume = 0.65;
    sound.play().catch(() => {});
  };

  async function postJson(url, payload) {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": data.csrf
      },
      body: JSON.stringify(payload)
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.message || "No se pudo guardar tu avance.");
    return body;
  }

  function drawClock(hour) {
    const angle = (Number(hour) % 12) * 30 - 90;
    const radians = angle * Math.PI / 180;
    const x = 90 + Math.cos(radians) * 37;
    const y = 90 + Math.sin(radians) * 37;
    const numbers = Array.from({ length: 12 }, (_, i) => {
      const n = i + 1;
      const a = n * 30 * Math.PI / 180 - Math.PI / 2;
      const nx = 90 + Math.cos(a) * 67;
      const ny = 90 + Math.sin(a) * 67 + 5;
      return `<text x="${nx}" y="${ny}" text-anchor="middle" font-size="12" font-weight="800" fill="#26352c">${n}</text>`;
    }).join("");
    return `<svg width="180" height="180" viewBox="0 0 180 180" role="img" aria-label="Reloj analógico"><circle cx="90" cy="90" r="79" fill="#fff" stroke="#718078" stroke-width="4"/>${numbers}<line x1="90" y1="90" x2="${x}" y2="${y}" stroke="#e05b4f" stroke-width="6" stroke-linecap="round"/><circle cx="90" cy="90" r="5" fill="#26352c"/></svg>`;
  }

  function showQuestion(question) {
    if (!question) return;
    const visual = document.querySelector("#question-visual");
    const prompt = document.querySelector("#question-prompt");
    const options = document.querySelector("#answer-options");
    const feedback = document.querySelector("#answer-feedback");
    const soundButton = document.querySelector("#repeat-sound");
    feedback.textContent = "";
    feedback.className = "answer-feedback";
    visual.className = `question-visual${question.visual_type === "color" ? " color" : question.visual_type === "clock" ? " clock" : question.visual_type === "shadow" ? " shadow" : ""}`;
    if (question.visual_type === "stars") visual.setAttribute("aria-label", "stars");
    else visual.removeAttribute("aria-label");
    if (question.visual_type === "color") visual.style.background = question.visual;
    else if (question.visual_type === "clock") visual.innerHTML = drawClock(question.visual);
    else visual.textContent = question.visual || "";
    prompt.textContent = question.prompt;
    repeatInstruction.onclick = () => speak(question.prompt);
    speak(question.prompt);
    options.replaceChildren();
    (question.options || []).forEach((option) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "answer-option";
      button.textContent = option;
      button.addEventListener("click", () => submitAnswer(option, button));
      options.append(button);
    });
    if (question.sound) {
      soundButton.hidden = false;
      soundButton.onclick = () => new Audio(mediaHref(question.sound)).play().catch(() => {});
      soundButton.click();
    } else {
      soundButton.hidden = true;
    }
    status.textContent = `Pregunta ${questionNumber} de 5`;
    progress.style.width = `${Math.max(20, (questionNumber / 5) * 100)}%`;
  }

  function speak(text) {
    if (!("speechSynthesis" in window)) {
      status.textContent = "La lectura de voz no está disponible en este navegador.";
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "es-MX";
    utterance.rate = 0.88;
    window.speechSynthesis.speak(utterance);
  }

  async function submitAnswer(answer, button) {
    if (busy) return;
    busy = true;
    const buttons = [...document.querySelectorAll(".answer-option")];
    buttons.forEach((item) => { item.disabled = true; });
    const feedback = document.querySelector("#answer-feedback");
    try {
      const response = await postJson("/api/responder", { round_id: data.roundId, answer });
      if (response.correct) {
        playSound("correcto.mp3");
        feedback.textContent = "¡Muy bien! 🌟";
        feedback.className = "answer-feedback good";
      } else if (response.resolved && response.reveal) {
        playSound("error.mp3");
        feedback.textContent = `La respuesta era ${response.reveal}. ¡Sigue intentando!`;
        feedback.className = "answer-feedback bad";
      } else {
        playSound("error.mp3");
        feedback.textContent = "Casi… prueba otra vez. 💪";
        feedback.className = "answer-feedback bad";
        buttons.forEach((item) => { item.disabled = false; });
        busy = false;
        return;
      }
      if (response.completed) {
        questionNumber = 5;
        progress.style.width = "100%";
        status.textContent = "Ronda terminada";
        window.setTimeout(() => showResult(response), 700);
      } else {
        questionNumber = response.question_number;
        window.setTimeout(() => showQuestion(response.question), response.correct ? 550 : 1100);
      }
    } catch (error) {
      feedback.textContent = error.message;
      feedback.className = "answer-feedback bad";
      buttons.forEach((item) => { item.disabled = false; });
    } finally {
      busy = false;
    }
  }

  function showResult(response) {
    if (response.medal) playSound("muy_bien.mp3");
    stage.hidden = true;
    const medal = response.medal ? ({ oro: "🥇 ¡Medalla de oro!", plata: "🥈 ¡Medalla de plata!", bronce: "🥉 ¡Medalla de bronce!" })[response.medal] : "¡Sigue practicando!";
    result.hidden = false;
    result.innerHTML = `<h2>¡Terminaste la ronda!</h2><p class="activity-emoji">${medal}</p><p>Acertaste <strong>${response.score} de 5</strong> y ganaste ${response.score} ⭐.</p><a class="button primary" href="${data.dashboardUrl}">Volver a mi aventura</a> <a class="button secondary" href="/juego/${encodeURIComponent(data.id)}">Jugar otra vez</a>`;
  }

  async function completeActivity(message = "¡Muy bien! Actividad completada.") {
    const buttons = [...activityRoot.querySelectorAll("button")];
    buttons.forEach((button) => { button.disabled = true; });
    try {
      const response = await postJson("/api/completar-actividad", { round_id: data.roundId });
      playSound("muy_bien.mp3");
      stage.hidden = true;
      result.hidden = false;
      result.innerHTML = `<h2>${escapeHtml(response.message || message)}</h2><p>Ganaste <strong>${response.points} ⭐</strong>${response.medal ? " · 🥇 ¡Medalla de oro!" : ""}</p><a class="button primary" href="${data.dashboardUrl}">Volver a mi aventura</a> <a class="button secondary" href="/juego/${encodeURIComponent(data.id)}">Jugar otra vez</a>`;
    } catch (error) {
      status.textContent = error.message;
      buttons.forEach((button) => { button.disabled = false; });
    }
  }

  function renderLesson() {
    const steps = data.activity.steps;
    let index = 0;
    activityRoot.innerHTML = `<h2 class="activity-title">${data.title === "Lavarse las manos" ? "Manos limpias y saludables" : "Cuida tu sonrisa"}</h2><p class="activity-description">Sigue los pasos de la aventura.</p><div class="lesson-visual"><span id="lesson-emoji" class="lesson-emoji"></span></div><h3 id="lesson-title"></h3><p id="lesson-description"></p><p id="lesson-count"></p><div class="activity-controls"><button class="button secondary" id="lesson-prev">← Anterior</button><button class="button primary" id="lesson-next">Siguiente →</button><button class="button light" id="lesson-done">Ya aprendí ✓</button></div>`;
    const draw = () => {
      const step = steps[index];
      document.querySelector("#lesson-emoji").textContent = step[1];
      document.querySelector("#lesson-title").textContent = `${index + 1}. ${step[0]}`;
      document.querySelector("#lesson-description").textContent = step[2];
      document.querySelector("#lesson-count").textContent = `Paso ${index + 1} de ${steps.length}`;
      status.textContent = `Paso ${index + 1} de ${steps.length}`;
      progress.style.width = `${((index + 1) / steps.length) * 100}%`;
      document.querySelector("#lesson-prev").disabled = index === 0;
      document.querySelector("#lesson-next").textContent = index === steps.length - 1 ? "Terminar lección ✓" : "Siguiente →";
      repeatInstruction.onclick = () => speak(`${step[0]}. ${step[2]}`);
    };
    document.querySelector("#lesson-prev").onclick = () => { index = Math.max(0, index - 1); draw(); };
    document.querySelector("#lesson-next").onclick = () => {
      if (index === steps.length - 1) completeActivity();
      else { index += 1; draw(); }
    };
    document.querySelector("#lesson-done").onclick = () => completeActivity();
    draw();
  }

  function setupCanvas(canvas, background = "#fff") {
    const context = canvas.getContext("2d");
    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const ratio = window.devicePixelRatio || 1;
      const saved = canvas.toDataURL();
      canvas.width = Math.max(1, rect.width * ratio);
      canvas.height = Math.max(1, rect.height * ratio);
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.fillStyle = background;
      context.fillRect(0, 0, rect.width, rect.height);
      if (saved && saved !== "data:,") {
        const image = new Image();
        image.onload = () => context.drawImage(image, 0, 0, rect.width, rect.height);
        image.src = saved;
      }
    };
    resize();
    return { context, resize };
  }

  function renderDraw() {
    const vowels = data.activity.vowels || ["A", "E", "I", "O", "U"];
    let index = 0;
    let points = 0;
    const palette = ["#e53935", "#fb8c00", "#fdd835", "#43a047", "#1e88e5", "#8e24aa", "#ec407a"];
    activityRoot.innerHTML = `<h2 class="activity-title">✏️ Dibuja la vocal <span id="vowel-target"></span></h2><p class="activity-description">Sigue la guía con tu dedo o el ratón. ¡No importa si no queda perfecta!</p><div class="vowel-board"><img id="vowel-reference" alt="Guía para trazar la vocal"><canvas id="draw-pad" class="draw-canvas" height="320"></canvas></div><div class="palette" id="draw-palette"></div><div class="activity-controls"><button class="button secondary" id="draw-clear">Limpiar</button><button class="button primary" id="draw-next">Verificar y continuar</button></div>`;
    const canvas = document.querySelector("#draw-pad");
    const { context } = setupCanvas(canvas);
    const reference = document.querySelector("#vowel-reference");
    let color = palette[0];
    let drawing = false;
    palette.forEach((tone) => {
      const button = document.createElement("button");
      button.type = "button";
      button.style.background = tone;
      button.setAttribute("aria-label", `Color ${tone}`);
      button.onclick = () => { color = tone; };
      document.querySelector("#draw-palette").append(button);
    });
    const position = (event) => {
      const rect = canvas.getBoundingClientRect();
      return { x: event.clientX - rect.left, y: event.clientY - rect.top };
    };
    canvas.onpointerdown = (event) => { drawing = true; canvas.setPointerCapture(event.pointerId); const p = position(event); context.beginPath(); context.moveTo(p.x, p.y); context.lineWidth = 9; context.lineCap = "round"; context.strokeStyle = color; points++; };
    canvas.onpointermove = (event) => { if (!drawing) return; const p = position(event); context.lineTo(p.x, p.y); context.stroke(); points++; };
    canvas.onpointerup = () => { drawing = false; };
    const setTarget = () => {
      document.querySelector("#vowel-target").textContent = vowels[index];
      reference.src = mediaHref(`vocal_${vowels[index].toLowerCase()}.png`);
      reference.alt = `Guía para trazar la vocal ${vowels[index]}`;
      status.textContent = `Vocal ${index + 1} de ${vowels.length}`;
      progress.style.width = `${(index / vowels.length) * 100}%`;
    };
    document.querySelector("#draw-clear").onclick = () => { context.clearRect(0, 0, canvas.width, canvas.height); points = 0; };
    document.querySelector("#draw-next").onclick = async () => {
      if (points < 12) { status.textContent = "¡Haz unos trazos en el lienzo antes de continuar!"; return; }
      index++;
      points = 0;
      if (index >= vowels.length) {
        try { await completeActivity(); } catch (error) { status.textContent = error.message; }
      } else {
        context.clearRect(0, 0, canvas.width, canvas.height);
        setTarget();
      }
    };
    setTarget();
  }

  function renderMemory() {
    const deck = data.activity.deck || [];
    activityRoot.innerHTML = `<h2 class="activity-title">🧠 Encuentra las parejas</h2><p class="activity-description">Voltea dos tarjetas y busca los animales iguales.</p><div id="memory-grid" class="memory-grid"></div><p id="memory-status"></p>`;
    const grid = document.querySelector("#memory-grid");
    let opened = [];
    let matched = new Set();
    let locked = false;
    let pairs = 0;
    const buttons = deck.map((animal, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "memory-card";
      button.textContent = "❓";
      button.setAttribute("aria-label", `Tarjeta ${index + 1}`);
      button.onclick = () => {
        if (locked || matched.has(index) || opened.includes(index)) return;
        button.textContent = animal;
        opened.push(index);
        if (opened.length === 2) {
          locked = true;
          const [first, second] = opened;
          if (deck[first] === deck[second]) {
              playSound("magia.mp3");
            matched.add(first); matched.add(second); pairs++;
            buttons[first].classList.add("matched"); buttons[second].classList.add("matched");
            opened = []; locked = false;
            document.querySelector("#memory-status").textContent = `¡Parejas: ${pairs} de 6!`;
            progress.style.width = `${(pairs / 6) * 100}%`;
            if (pairs === 6) completeActivity().catch((error) => { document.querySelector("#memory-status").textContent = error.message; });
          } else {
            window.setTimeout(() => { buttons[first].textContent = "❓"; buttons[second].textContent = "❓"; opened = []; locked = false; }, 750);
          }
        }
      };
      grid.append(button);
      return button;
    });
  }

  function renderPaint() {
    activityRoot.innerHTML = `<h2 class="activity-title">🎨 Pintura libre</h2><p class="activity-description">Elige un color y pinta con el ratón o con tu dedo.</p><canvas id="paint-pad" class="paint-canvas" height="320"></canvas><div id="paint-palette" class="palette"></div><div class="activity-controls"><button class="button secondary" id="paint-clear">Limpiar</button><button class="button primary" id="paint-done">Terminar mi obra</button></div>`;
    const canvas = document.querySelector("#paint-pad");
    const { context } = setupCanvas(canvas);
    let color = "#e53935";
    let drawing = false;
    ["#e53935", "#fb8c00", "#fdd835", "#43a047", "#1e88e5", "#8e24aa", "#ec407a", "#222222"].forEach((tone) => {
      const button = document.createElement("button");
      button.type = "button"; button.style.background = tone; button.setAttribute("aria-label", `Color ${tone}`);
      button.onclick = () => { color = tone; };
      document.querySelector("#paint-palette").append(button);
    });
    const position = (event) => { const rect = canvas.getBoundingClientRect(); return { x: event.clientX - rect.left, y: event.clientY - rect.top }; };
    canvas.onpointerdown = (event) => { drawing = true; canvas.setPointerCapture(event.pointerId); const p = position(event); context.beginPath(); context.moveTo(p.x, p.y); context.lineWidth = 10; context.lineCap = "round"; context.strokeStyle = color; };
    canvas.onpointermove = (event) => { if (!drawing) return; const p = position(event); context.lineTo(p.x, p.y); context.stroke(); };
    canvas.onpointerup = () => { drawing = false; };
    document.querySelector("#paint-clear").onclick = () => context.clearRect(0, 0, canvas.width, canvas.height);
    document.querySelector("#paint-done").onclick = () => completeActivity();
  }

  function renderFind() {
    activityRoot.innerHTML = `<h2 class="activity-title">🐆 Encuentra al jaguar</h2><p class="activity-description">Tienes pistas: busca con cuidado en la cuadrícula.</p><div id="find-grid" class="activity-grid"></div><p id="find-status" aria-live="polite"></p>`;
    const target = Math.floor(Math.random() * 9);
    const grid = document.querySelector("#find-grid");
    let misses = 0;
    Array.from({ length: 9 }, (_, index) => {
      const button = document.createElement("button");
      button.type = "button"; button.className = "activity-cell"; button.textContent = ["🐶", "🐱", "🐰", "🐻", "🐸", "🐵", "🦊", "🐼", "🐨"][index];
      button.onclick = () => {
        if (index === target) {
          button.textContent = "🐆";
          document.querySelector("#find-status").textContent = "¡Lo encontraste!";
          [...grid.children].forEach((cell) => { cell.disabled = true; });
          completeActivity();
        } else {
          misses++; button.disabled = true; button.textContent = "🌿";
          document.querySelector("#find-status").textContent = misses >= 2 ? `Pista: el jaguar está más ${index < target ? "adelante" : "atrás"}.` : "Aquí no está… ¡sigue buscando!";
        }
      };
      grid.append(button);
    });
  }

  function renderTimedGame(kind) {
    const isWhack = kind === "whack";
    const seconds = isWhack ? 15 : 10;
    const targetEmoji = isWhack ? "🐹" : kind === "catch" ? "🍎" : "🎈";
    activityRoot.innerHTML = `<h2 class="activity-title">${isWhack ? "🔨 ¡Atrapa al topo!" : kind === "catch" ? "🍎 ¡Atrapa las frutas!" : "🎈 ¡Explota los globos!"}</h2><p class="activity-description">Toca los objetos que aparecen antes de que termine el tiempo.</p><p><strong id="timed-score">0</strong> puntos · <span id="timed-clock">${seconds}</span> segundos</p><div class="activity-grid" id="timed-grid"></div><div class="activity-controls"><button class="button primary" id="timed-start">Empezar</button></div>`;
    const grid = document.querySelector("#timed-grid");
    let score = 0;
    let active = false;
    let timer;
    const cells = Array.from({ length: 9 }, () => {
      const button = document.createElement("button");
      button.type = "button"; button.className = "activity-cell";
      button.onclick = () => {
        if (active && button.textContent) { score++; button.textContent = ""; document.querySelector("#timed-score").textContent = score; }
      };
      grid.append(button);
      return button;
    });
    const spawn = () => {
      if (!active) return;
      cells.forEach((button) => { button.textContent = ""; });
      cells[Math.floor(Math.random() * cells.length)].textContent = targetEmoji;
      timer = window.setTimeout(spawn, 650);
    };
    document.querySelector("#timed-start").onclick = () => {
      if (active) return;
      active = true;
      let remaining = seconds;
      spawn();
      const interval = window.setInterval(() => {
        remaining--; document.querySelector("#timed-clock").textContent = remaining;
        if (remaining <= 0) {
          window.clearInterval(interval); window.clearTimeout(timer); active = false;
          cells.forEach((button) => { button.textContent = ""; button.disabled = true; });
          completeActivity();
        }
      }, 1000);
    };
  }

  function renderSimon() {
    const colors = ["#e53935", "#43a047", "#1e88e5", "#fdd835"];
    activityRoot.innerHTML = `<h2 class="activity-title">🎵 Simón dice</h2><p id="simon-status" class="activity-description">Observa la secuencia y repítela.</p><div id="simon-grid" class="simon-grid"></div><div class="activity-controls"><button id="simon-start" class="button primary">Empezar</button></div>`;
    const grid = document.querySelector("#simon-grid");
    const sequence = [];
    let input = [];
    let accepting = false;
    const buttons = colors.map((color, index) => {
      const button = document.createElement("button");
      button.type = "button"; button.className = "simon-button"; button.style.background = color; button.setAttribute("aria-label", `Color ${index + 1}`);
      button.onclick = () => {
        if (!accepting) return;
        input.push(index);
        const step = input.length - 1;
        if (input[step] !== sequence[step]) {
          accepting = false;
          document.querySelector("#simon-status").textContent = "¡Casi! Intenta una nueva secuencia.";
          return;
        }
        if (input.length === sequence.length) {
          accepting = false;
          if (sequence.length >= 5) completeActivity();
          else window.setTimeout(nextRound, 600);
        }
      };
      grid.append(button);
      return button;
    });
    const showSequence = () => {
      accepting = false;
      document.querySelector("#simon-status").textContent = `Nivel ${sequence.length}: observa…`;
      sequence.forEach((value, i) => window.setTimeout(() => {
        buttons[value].classList.add("lit");
        window.setTimeout(() => buttons[value].classList.remove("lit"), 280);
      }, i * 550));
      window.setTimeout(() => { input = []; accepting = true; document.querySelector("#simon-status").textContent = "¡Ahora repite la secuencia!"; }, sequence.length * 550 + 350);
    };
    const nextRound = () => { sequence.push(Math.floor(Math.random() * 4)); showSequence(); };
    document.querySelector("#simon-start").onclick = () => { sequence.length = 0; nextRound(); };
  }

  function renderPuzzle() {
    const puzzles = data.activity.puzzles || [];
    const puzzle = puzzles[Math.floor(Math.random() * puzzles.length)];
    activityRoot.innerHTML = `<h2 class="activity-title">🧩 Rompecabezas</h2><p class="activity-description">Arrastra las piezas para ordenar la imagen.</p><img src="${mediaHref(puzzle.image)}" alt="${escapeHtml(puzzle.name)}" style="display:block;width:130px;height:90px;object-fit:cover;margin:8px auto;border-radius:12px"><div class="puzzle-board" id="puzzle-board"></div><div class="activity-controls"><button id="puzzle-check" class="button primary">Revisar imagen</button></div>`;
    const board = document.querySelector("#puzzle-board");
    const order = Array.from({ length: 9 }, (_, i) => i).sort(() => Math.random() - .5);
    let dragIndex = null;
    order.forEach((piece, index) => {
      const tile = document.createElement("button");
      tile.type = "button"; tile.className = "puzzle-piece"; tile.draggable = true; tile.dataset.piece = piece;
      tile.style.backgroundImage = `url("${mediaHref(puzzle.image)}")`;
      tile.style.backgroundPosition = `${(piece % 3) * -95}px ${Math.floor(piece / 3) * -95}px`;
      tile.ondragstart = () => { dragIndex = index; };
      tile.ondragover = (event) => event.preventDefault();
      tile.ondrop = (event) => {
        event.preventDefault();
        const other = board.children[dragIndex];
        const temp = tile.dataset.piece;
        tile.dataset.piece = other.dataset.piece; other.dataset.piece = temp;
        const update = (node) => { const value = Number(node.dataset.piece); node.style.backgroundPosition = `${(value % 3) * -95}px ${Math.floor(value / 3) * -95}px`; };
        update(tile); update(other);
      };
      board.append(tile);
    });
    document.querySelector("#puzzle-check").onclick = () => {
      const solved = [...board.children].every((piece, index) => Number(piece.dataset.piece) === index);
      if (solved) completeActivity();
      else status.textContent = "¡Sigue intentando! Cambia las piezas de lugar.";
    };
  }

  function renderActivity() {
    repeatInstruction.onclick = () => speak(`${data.title}. ${stage.textContent.replace(/\s+/g, " ").trim()}`);
    if (data.mode === "lesson") renderLesson();
    else if (data.mode === "draw") renderDraw();
    else if (data.mode === "memory") renderMemory();
    else if (data.mode === "paint") renderPaint();
    else if (data.mode === "find") renderFind();
    else if (data.mode === "balloons" || data.mode === "whack" || data.mode === "catch") renderTimedGame(data.mode);
    else if (data.mode === "simon") renderSimon();
    else if (data.mode === "puzzle") renderPuzzle();
  }

  if (data.mode === "quiz") showQuestion(data.question);
  else renderActivity();
})();
