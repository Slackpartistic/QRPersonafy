// QRPersonafy desktop app. Talks to Python through window.pywebview.api (see gui/api.py);
// Python reports progress by calling window.onAppEvent.
"use strict";

const $ = (id) => document.getElementById(id);
const api = () => window.pywebview.api;

let mode = null; // "send" | "receive" | "file" while a flow is running
let timer = null;

function show(name) {
  for (const view of document.querySelectorAll(".view")) view.hidden = view.id !== `view-${name}`;
}

function toast(text) {
  const el = $("toast");
  el.textContent = text;
  el.hidden = false;
  clearTimeout(toast.hide);
  toast.hide = setTimeout(() => (el.hidden = true), 3500);
}

async function goHome() {
  stopTimer();
  mode = null;
  const info = await api().info();
  $("pc-name").textContent = info.pc_name;
  $("undo-link").hidden = !info.has_backup;
  show("home");
}

// Setting lists. Everything from a profile is shown with textContent, never as HTML:
// a profile can come from a phone or a file.

function renderItems(container, summary, selectable) {
  container.replaceChildren();
  for (const item of summary.items) {
    const row = document.createElement(selectable ? "label" : "div");
    row.className = "item";
    if (selectable) {
      const box = document.createElement("input");
      box.type = "checkbox";
      box.checked = true;
      box.value = item.name;
      row.append(box);
    }
    if (item.image) {
      const img = document.createElement("img");
      img.className = "thumb";
      img.alt = "";
      img.src = item.image;
      row.append(img);
    } else if (item.color) {
      const swatch = document.createElement("span");
      swatch.className = "swatch";
      swatch.style.background = /^#[0-9A-F]{6}$/i.test(item.color) ? item.color : "transparent";
      row.append(swatch);
    } else if (item.name === "theme" && "dark" in item) {
      const chip = document.createElement("span");
      chip.className = item.dark ? "mode dark" : "mode";
      row.append(chip);
    }
    const body = document.createElement("span");
    body.className = "item-body";
    const label = document.createElement("div");
    label.className = "item-label";
    label.textContent = item.label;
    const details = document.createElement("div");
    details.className = "item-details";
    details.textContent = item.details;
    if (item.list && item.list.length) details.title = item.list.join(", ");
    body.append(label, details);
    row.append(body);
    container.append(row);
  }
}

function chosenSettings() {
  return [...$("review-items").querySelectorAll("input:checked")].map((box) => box.value);
}

// QR screens

function startTimer(seconds) {
  stopTimer();
  const end = Date.now() + seconds * 1000;
  const tick = () => {
    const left = Math.max(0, Math.round((end - Date.now()) / 1000));
    $("timer").textContent = `Code expires in ${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
  };
  tick();
  timer = setInterval(tick, 1000);
}

function stopTimer() {
  clearInterval(timer);
  timer = null;
}

async function startPairing(kind) {
  mode = kind;
  $("pair-title").textContent = kind === "send" ? "Save this PC to your phone" : "Restore from your phone";
  $("pair-status").textContent = "Getting ready…";
  $("qr").replaceChildren();
  $("sending").hidden = true;
  show("pair");
  try {
    const result = kind === "send" ? await api().start_send() : await api().start_receive();
    $("qr").innerHTML = result.qr; // SVG made by this app from its own pairing address
    $("pair-status").textContent = "Waiting for your phone…";
    startTimer(result.seconds);
    if (result.summary) {
      renderItems($("send-items"), result.summary, false);
      $("sending").hidden = false;
    }
  } catch (error) {
    failed("Couldn't start", String(error.message || error));
  }
}

// Results

function finished(title, text, warnings, canUndo) {
  stopTimer();
  mode = null;
  $("done-badge").className = "badge";
  $("done-title").textContent = title;
  $("done-text").textContent = text;
  const list = $("done-warnings");
  list.replaceChildren(...(warnings || []).map((w) => Object.assign(document.createElement("li"), { textContent: w })));
  list.hidden = !warnings || !warnings.length;
  $("done-undo").hidden = !canUndo;
  show("done");
}

function showBusy(title, step) {
  $("busy-title").textContent = title;
  $("busy-fill").style.width = "4%";
  $("busy-step").textContent = step;
  show("busy");
}

function failed(title, text) {
  finished(title, text, [], false);
  $("done-badge").className = "badge bad";
}

function appliedText(applied) {
  return applied.length ? `Applied: ${applied.join(", ")}.` : "Nothing needed changing.";
}

// Events from Python

window.onAppEvent = (event) => {
  switch (event.type) {
    case "received":
      stopTimer();
      $("review-from").textContent = "Your phone sent these settings. Untick anything you want to keep as it is.";
      renderItems($("review-items"), event.summary, true);
      show("review");
      break;
    case "applied":
      finished("All done", appliedText(event.applied), event.warnings, true);
      break;
    case "finished":
      if (event.kind === "send" && event.ok) {
        finished("Saved to your phone", "You can now restore this look on any PC with QRPersonafy.", [], false);
      } else if (!event.ok && mode === event.kind) {
        failed("The code expired", "Nothing was sent. Start again when your phone is ready.");
      }
      break;
    case "progress":
      $("busy-fill").style.width = `${Math.max(4, Math.round((100 * event.done) / event.total))}%`;
      $("busy-step").textContent = event.done < event.total ? `${event.label}…` : "Done";
      break;
    case "error":
      failed("Something went wrong", event.message);
      break;
  }
};

// Buttons

document.addEventListener("click", async (e) => {
  const go = e.target.closest("[data-go]");
  if (go) {
    const where = go.dataset.go;
    if (where === "send" || where === "receive") return startPairing(where);
    if (where === "home") return goHome();
    return show(where);
  }
  if (e.target.closest("[data-cancel]")) {
    await api().cancel();
    goHome();
  }
});

$("review-apply").addEventListener("click", async () => {
  const names = chosenSettings();
  if (!names.length) return toast("Tick at least one setting, or press Cancel.");
  showBusy("Applying…", "Backing up your current settings…");
  if (mode === "file") {
    const result = await api().apply_file(names);
    finished("All done", appliedText(result.applied), result.warnings, true);
  } else {
    api().decide(true, names); // the "applied" event follows
  }
});

$("review-cancel").addEventListener("click", async () => {
  if (mode === "receive") await api().decide(false, []);
  goHome();
});

async function undo() {
  showBusy("Putting your previous settings back…", "Getting started…");
  const result = await api().undo_last();
  finished("Undone", appliedText(result.applied), result.warnings, false);
}
$("undo-link").addEventListener("click", undo);
$("done-undo").addEventListener("click", undo);

$("file-save").addEventListener("click", async () => {
  const result = await api().export_file();
  if (result.saved) toast("Saved");
});

$("file-open").addEventListener("click", async () => {
  const result = await api().open_file();
  if (result.error) return toast(result.error);
  if (!result.summary) return;
  mode = "file";
  $("review-from").textContent = "This file contains these settings. Untick anything you want to keep as it is.";
  renderItems($("review-items"), result.summary, true);
  show("review");
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && mode && mode !== "file") document.querySelector("[data-cancel]").click();
});

window.addEventListener("pywebviewready", goHome);
