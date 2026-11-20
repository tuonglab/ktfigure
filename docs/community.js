const gallery = document.getElementById("community-entries");
const status = document.getElementById("gallery-status");

function textElement(tag, text, className) {
  const element = document.createElement(tag);
  element.textContent = text;
  if (className) element.className = className;
  return element;
}

function makeCard(entry) {
  const card = document.createElement("article");
  card.className = "community-card";
  const image = document.createElement("img");
  image.src = `community/items/${entry.image}`;
  image.alt = `Figure shared by ${entry.name}`;
  image.loading = "lazy";
  card.append(image);
  const content = document.createElement("div");
  content.className = "community-card-content";
  content.append(textElement("h3", entry.name));
  if (entry.description) content.append(textElement("p", entry.description));
  if (entry.feedback) content.append(textElement("blockquote", entry.feedback, "community-feedback"));
  if (entry.citation) content.append(textElement("p", entry.citation, "caption"));
  if (entry.doi) {
    const doi = textElement("a", `DOI: ${entry.doi}`, "community-link");
    doi.href = `https://doi.org/${encodeURIComponent(entry.doi).replace(/%2F/gi, "/")}`;
    doi.rel = "noopener noreferrer";
    content.append(doi);
  }
  if (entry.link) {
    try {
      const url = new URL(entry.link);
      if (url.protocol === "https:" || url.protocol === "http:") {
        const link = textElement("a", "Paper or project ↗", "community-link");
        link.href = url.href;
        link.rel = "noopener noreferrer";
        content.append(link);
      }
    } catch {
      content.append(textElement("p", "The project link is invalid.", "caption"));
    }
  }
  const discussion = textElement("a", "View discussion & comment ↗", "community-discussion");
  discussion.href = `https://github.com/tuonglab/ktfigure/issues/${entry.issue}`;
  content.append(discussion);
  card.append(content);
  return card;
}

async function loadGallery() {
  try {
    const response = await fetch("community/entries.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const entries = await response.json();
    if (!Array.isArray(entries)) throw new Error("Invalid gallery index");
    for (const entry of entries) {
      if (
        !Number.isSafeInteger(entry.issue) || entry.issue <= 0 ||
        typeof entry.image !== "string" ||
        !new RegExp(`^${entry.issue}\\.(jpg|png)$`).test(entry.image) ||
        typeof entry.name !== "string" || typeof entry.description !== "string" ||
        typeof entry.citation !== "string" || typeof entry.link !== "string" ||
        (entry.feedback !== undefined && typeof entry.feedback !== "string") ||
        (entry.doi !== undefined && typeof entry.doi !== "string")
      ) throw new Error("Invalid gallery entry");
    }
    gallery.replaceChildren(...entries.map(makeCard));
    status.textContent = entries.length ? `${entries.length} approved figure${entries.length === 1 ? "" : "s"}.` : "No community submissions have been approved yet. Be the first to share!";
  } catch (error) {
    status.textContent = "The gallery could not be loaded. Please try again later or visit the submission form.";
    console.error("Could not load community gallery:", error);
  }
}

const examples = [
  ["A time-course overview", "plot-line"],
  ["Individual sample responses", "plot-strip"],
  ["Biomarker association", "plot-scatter"],
  ["Comparing two methods", "plot-box"],
  ["Response distributions", "plot-histogram"],
  ["Endpoint observations", "plot-strip"],
  ["Treatment over time", "plot-line"],
  ["Exploring paired measurements", "plot-scatter"],
  ["Benchmark variability", "plot-box"],
  ["Measurement distribution", "plot-histogram"],
  ["Longitudinal trends", "plot-line"],
  ["Group comparisons", "plot-strip"],
  ["Two measurements together", "plot-scatter"],
  ["Variability between groups", "plot-box"],
  ["Score distribution", "plot-histogram"],
  ["Changes across visits", "plot-line"],
  ["Showing observations", "plot-strip"],
  ["Comparing measurements", "plot-scatter"],
  ["Method runtime spread", "plot-box"],
  ["Exploring score ranges", "plot-histogram"],
];

const exampleGallery = document.getElementById("community-examples");
for (const [title, symbol] of examples) {
  const card = document.createElement("article");
  card.className = "community-card";
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 240 120");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `Schematic example: ${title}`);
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `images/step-illustrations.svg#${symbol}`);
  svg.append(use);
  card.append(svg);
  const content = document.createElement("div");
  content.className = "community-card-content";
  content.append(textElement("span", "Example plot", "card-number"));
  content.append(textElement("h3", title));
  card.append(content);
  exampleGallery.append(card);
}

loadGallery();
