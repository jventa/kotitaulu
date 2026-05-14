const SOURCE_LABELS = {
  google_calendar: "Kalenteri",
  gmail: "Sähköposti",
  home_assistant: "Koti",
  weather: "Sää",
  rss: "Uutiset",
  stocks: "Osakkeet",
  web_scraper: "Verkkosivut",
  kauhavan_seurakunta: "Seurakunta",
};

const SOURCE_ICONS = {
  google_calendar: "📅",
  gmail: "✉️",
  home_assistant: "🏠",
  weather: "🌤️",
  rss: "📰",
  stocks: "📈",
  web_scraper: "🌐",
  kauhavan_seurakunta: "⛪",
};

function formatTime(isoString) {
  if (!isoString) return null;
  const d = new Date(isoString);
  if (isNaN(d)) return isoString;
  const today = new Date();
  const diffDays = Math.round((new Date(d.getFullYear(), d.getMonth(), d.getDate()) -
    new Date(today.getFullYear(), today.getMonth(), today.getDate())) / 86400000);
  const timeStr = d.toLocaleTimeString("fi-FI", { hour: "2-digit", minute: "2-digit" });
  if (diffDays === 0) return timeStr;
  if (diffDays === 1) return `huom. ${timeStr}`;
  return d.toLocaleDateString("fi-FI", { weekday: "short", day: "numeric", month: "numeric" });
}

function buildCard(source, items) {
  const label = SOURCE_LABELS[source] || source;
  const icon = SOURCE_ICONS[source] || "•";

  const section = document.createElement("section");
  section.className = "source-card";
  section.dataset.source = source;

  const header = document.createElement("h2");
  header.innerHTML = `<span class="icon">${icon}</span>${label}`;
  section.appendChild(header);

  if (!items || items.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "Ei kohteita";
    section.appendChild(empty);
    return section;
  }

  const list = document.createElement("ul");
  for (const item of items) {
    const li = document.createElement("li");
    li.className = `item priority-${item.priority || "normal"}`;

    const time = formatTime(item.time);
    const titleEl = document.createElement("span");
    titleEl.className = "item-title";

    if (item.url) {
      const a = document.createElement("a");
      a.href = item.url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = item.title;
      titleEl.appendChild(a);
    } else {
      titleEl.textContent = item.title;
    }

    if (time) {
      const timeEl = document.createElement("span");
      timeEl.className = "item-time";
      timeEl.textContent = time;
      li.appendChild(timeEl);
    }

    li.appendChild(titleEl);

    if (item.detail) {
      const detail = document.createElement("span");
      detail.className = "item-detail";
      detail.textContent = item.detail;
      li.appendChild(detail);
    }

    list.appendChild(li);
  }
  section.appendChild(list);
  return section;
}

async function loadItems() {
  try {
    const resp = await fetch("/api/items");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    const board = document.getElementById("board");
    board.innerHTML = "";

    const order = [
      "weather", "google_calendar", "kauhavan_seurakunta",
      "home_assistant", "rss", "stocks", "gmail", "web_scraper",
    ];
    const sources = data.sources || {};

    for (const src of order) {
      board.appendChild(buildCard(src, sources[src] || []));
    }

    document.getElementById("last-updated").textContent =
      "Päivitetty: " + new Date().toLocaleTimeString("fi-FI");
  } catch (err) {
    console.error(err);
  }
}

async function triggerRefresh() {
  const btn = document.getElementById("refresh-btn");
  btn.disabled = true;
  try {
    await fetch("/api/refresh", { method: "POST" });
    await loadItems();
  } finally {
    btn.disabled = false;
  }
}

function updateClock() {
  document.getElementById("clock").textContent = new Date().toLocaleString("fi-FI", {
    weekday: "long",
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  });
}

document.getElementById("refresh-btn").addEventListener("click", triggerRefresh);

loadItems();
updateClock();
setInterval(loadItems, 60_000);
setInterval(updateClock, 1_000);
