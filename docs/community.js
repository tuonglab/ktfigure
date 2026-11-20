const gallery = document.getElementById("community-entries");
const status = document.getElementById("gallery-status");

function makeCard(entry) {
  const card = document.createElement("article");
  card.className = "community-card";
  const content = document.createElement("div");
  content.className = "community-card-content";
  const heading = document.createElement("h3");
  heading.textContent = entry.platform === "x" ? "Post on X" : "Post on LinkedIn";
  content.append(heading);
  if (entry.description) {
    const description = document.createElement("p");
    description.textContent = entry.description;
    content.append(description);
  }
  const link = document.createElement("a");
  link.href = entry.url;
  link.textContent = "View the original post ↗";
  link.rel = "noopener noreferrer";
  link.className = "community-link";
  content.append(link);
  if (entry.platform === "x") {
    const quote = document.createElement("blockquote");
    quote.className = "twitter-tweet";
    const fallback = document.createElement("a");
    fallback.href = entry.url;
    fallback.textContent = "View this post on X";
    quote.append(fallback);
    content.append(quote);
  } else {
    const frame = document.createElement("iframe");
    frame.src = `https://www.linkedin.com/embed/feed/update/urn:li:${entry.id}`;
    frame.title = "LinkedIn post";
    frame.loading = "lazy";
    frame.className = "community-embed";
    content.append(frame);
  }
  card.append(content);
  return card;
}

function validEntry(entry) {
  if (!entry || typeof entry.url !== "string" || typeof entry.description !== "string") return false;
  try {
    const url = new URL(entry.url);
    if (url.protocol !== "https:" || url.username || url.password || url.port) return false;
    if (entry.platform === "x") {
      const match = /^\/[a-zA-Z0-9_]{1,15}\/status\/([0-9]{1,25})$/.exec(url.pathname);
      return url.hostname === "x.com" && match && match[1] === entry.id;
    }
    return entry.platform === "linkedin" && url.hostname === "www.linkedin.com" &&
      /^(activity|share|ugcPost):[0-9]{1,25}$/.test(entry.id);
  } catch {
    return false;
  }
}

async function loadGallery() {
  try {
    const response = await fetch("community/entries.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const entries = await response.json();
    if (!Array.isArray(entries) || !entries.every(validEntry)) throw new Error("Invalid gallery index");
    gallery.replaceChildren(...entries.map(makeCard));
    status.textContent = entries.length ? `${entries.length} community post${entries.length === 1 ? "" : "s"}.` : "No community posts yet. Be the first to share!";
    if (entries.some((entry) => entry.platform === "x")) {
      const script = document.createElement("script");
      script.src = "https://platform.twitter.com/widgets.js";
      script.async = true;
      script.onerror = () => console.error("Could not load X embeds; original post links remain available.");
      document.head.append(script);
    }
  } catch (error) {
    status.textContent = "The gallery could not be loaded. Please try again later.";
    console.error("Could not load community gallery:", error);
  }
}

loadGallery();
