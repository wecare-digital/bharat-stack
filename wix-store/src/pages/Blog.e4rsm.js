/**************************************************************
 * pages/blog.js
 * Blog index / categories / tags
 * SECTION A: Blog Search Component
 * SECTION B: SEO / Hygiene
 **************************************************************/

// ---------- IMPORTS (ALL IMPORTS MUST BE AT THE TOP) ----------
import wixData from 'wix-data';
import wixLocation from 'wix-location';
import wixWindow from 'wix-window';

import { autoSEO } from 'public/global-apply';
import { installSeoBridge } from 'public/seo-bridge';
import { initHygiene } from 'public/site-hygiene';
import { runOpsLite } from 'public/ops-lite';

// ---------- SEARCH CONSTANTS ----------
const BLOG_POSTS_COLLECTION = "Blog/Posts";
// Slightly faster debounce for "as you type"
const DEBOUNCE_DELAY_MS = 150;
const MAX_RESULTS_DESKTOP = 10;
const MAX_RESULTS_MOBILE = 6;

let debounceTimer = null;
let lastQuery = "";
let isMobile = false;
let currentResults = [];   // holds the latest search results

// ======================================================
//  SECTION A: BLOG SEARCH (server query + debounce)
// ======================================================

// This onReady is ONLY for search
$w.onReady(() => {
  isMobile = wixWindow.formFactor === "Mobile";
  initBlogSearch();
});

// Reusable Blog Search Component
// - Mobile-friendly
// - Helvetica Light, 16px, black clickable titles
// - Auto-fill input from suggestions
// - Enter key opens first result (fast)
// - Shows #noResultsText when no posts found
//
// Required elements on the page:
// #searchInput, #resultsBox, #resultsRepeater, #rowBox, #resultTitle, #noResultsText

function initBlogSearch() {
  if (!(
    $w('#searchInput') &&
    $w('#resultsBox') &&
    $w('#resultsRepeater') &&
    $w('#noResultsText')
  )) {
    console.warn('Blog search: one or more required elements are missing on this page.');
    return;
  }

  const input = $w('#searchInput');
  const resultsBox = $w('#resultsBox');
  const repeater = $w('#resultsRepeater');
  const noResultsText = $w('#noResultsText');

  // Initial state
  resultsBox.collapse();
  repeater.data = [];
  currentResults = [];
  noResultsText.hide();

  // How each row looks/behaves
  repeater.onItemReady(($item, itemData) => {
    const title = itemData.title || "";
    const titleEl = $item('#resultTitle');

    // Try HTML styling (Rich Text) → fallback to plain text if needed
    try {
      titleEl.html = asLinkHtml(title);
    } catch (e) {
      titleEl.text = title;
    }

    if (isMobile) {
      try {
        const rowBox = $item('#rowBox');
        rowBox.height = Math.max(rowBox.height, 48);
      } catch (e) { /* ignore */ }
    }

    const goToPost = () => {
      const url = itemData.postPageUrl || itemData.postPageURL;
      if (url) {
        // Auto-fill the input immediately
        input.value = title;
        wixLocation.to(url);
      } else {
        console.warn('Blog search: post URL not found on itemData.', itemData);
      }
    };

    titleEl.onClick(goToPost);
    $item('#rowBox').onClick(goToPost);
  });

  // Typing → debounced search (starts as you type)
  input.onInput(() => {
    const query = input.value.trim();

    if (!query) {
      lastQuery = "";
      currentResults = [];
      repeater.data = [];
      noResultsText.hide();
      resultsBox.collapse();
      return;
    }

    if (debounceTimer) {
      clearTimeout(debounceTimer);
    }

    debounceTimer = setTimeout(() => {
      runSearch(query, repeater, resultsBox, noResultsText, false);
    }, DEBOUNCE_DELAY_MS);
  });

  // FAST Enter behavior:
  // - If we already have results → open first immediately.
  // - If not yet searched for this text → run an immediate search and
  //   navigate to first result as soon as it comes back.
  input.onKeyPress((event) => {
    if (event.key === "Enter") {
      const query = input.value.trim();
      if (!query) {
        return;
      }

      // If currentResults already matches this query and has items → go now
      if (currentResults.length > 0 && query === lastQuery) {
        const first = currentResults[0];
        const url = first.postPageUrl || first.postPageURL;
        if (url) {
          input.value = first.title || input.value;
          wixLocation.to(url);
        }
      } else {
        // No fresh results yet → run immediate search & auto-navigate on first result
        runSearch(query, repeater, resultsBox, noResultsText, true);
      }
    }
  });
}

// ---------------- SEARCH LOGIC ----------------

function runSearch(query, repeater, resultsBox, noResultsText, navigateFirst) {
  lastQuery = query;
  const limit = isMobile ? MAX_RESULTS_MOBILE : MAX_RESULTS_DESKTOP;

  wixData.query(BLOG_POSTS_COLLECTION)
    .contains("title", query)
    .ascending("title")
    .limit(limit)
    .find()
    .then((result) => {
      // Ignore stale results
      if (query !== lastQuery) {
        return;
      }

      const items = result.items || [];
      currentResults = items;

      if (items.length > 0) {
        repeater.data = items;
        noResultsText.hide();

        if (resultsBox.collapsed) {
          resultsBox.expand();
          if (isMobile) {
            resultsBox.scrollTo().catch(() => {});
          }
        }

        // If Enter triggered this search & we want to go to the first result fast
        if (navigateFirst) {
          const first = items[0];
          const url = first.postPageUrl || first.postPageURL;
          if (url) {
            const input = $w('#searchInput');
            input.value = first.title || input.value;
            wixLocation.to(url);
          }
        }
      } else {
        repeater.data = [];
        if (query) {
          noResultsText.show();
          resultsBox.expand();
        } else {
          noResultsText.hide();
          resultsBox.collapse();
        }
      }
    })
    .catch((error) => {
      console.error('Blog search query failed:', error);
      currentResults = [];
      repeater.data = [];
      noResultsText.hide();
      resultsBox.collapse();
    });
}

// ---------------- HELPERS ----------------

// Link HTML: Helvetica Light, size 16, black, underlined, clickable
function asLinkHtml(label) {
  const safe = escapeHtml(label);
  return `
    <p style="margin:0;">
      <span style="
        font-family:'Helvetica Light', Helvetica, Arial, sans-serif;
        font-size:16px;
        color:#000000;
        text-decoration:underline;
        cursor:pointer;
      ">
        ${safe}
      </span>
    </p>
  `;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&lt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ======================================================
//  SECTION B: SEO / HYGIENE (your original block)
// ======================================================

// This onReady is ONLY for SEO & hygiene
$w.onReady(async () => {
  initHygiene({ useCanonicalize: true });
  await autoSEO();            // for actual blog posts, the product/blog stubs kick in
  installSeoBridge({ relaxedDynamic: true });
  runOpsLite().catch(() => {});
});
