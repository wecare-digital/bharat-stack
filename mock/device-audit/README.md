# Header / footer / widget — device audit and mockups

Nothing in `src/` is changed on this branch. These are measurements and mockups only, for a decision.

Every image is the **real rendered home page** at a real device size, captured with the same Chromium the test harness uses. Nothing is drawn or illustrated. Red outlines are added only to mark the pill and the dash so the relationship is visible.

Fourteen widths measured: 280, 320, 375, 390, 393, 412, 430, 768, 820, 1024, 1280, 1440, 1920, 2560.

---

## 1 · Header — no defects

![Header across every device width](./1-header.png)

Two sizes only: **96px tall with a 54px logo** below 768px, **108px with a 60px logo** above it. Fixed at every width. It never wraps, never overlaps, the lockup stays optically centred, and the chevron chip is the only control — there is no separate hamburger to keep in step.

Two things to carry into the first-section work, neither a defect:

- At 280px the fixed header takes 96px of a 653px screen, about 15% of it, permanently.
- The hero repeats **WECARE.DIGITAL** in a lime badge roughly 190px below the header's own wordmark, so the same words appear twice in one screenful.

---

## 2 · Footer and widget — two defects

![Footer and widget across every device width](./2-footer-widget.png)

Scrolled to the very end of the page — the one scroll position where a fixed pill can sit on top of footer content.

### ① The pill covers the lime dash

The dash is bottom-**right** at every width, not just on desktop. On desktop `.ft-grid` is `justify-content: space-between`, which pushes it right. Below 768px the grid becomes a column with `align-items: flex-start` — but the dash carries `align-self: flex-end`, which overrides that and pins it to the right edge anyway. So it shares the pill's column everywhere; only vertical distance saves the small phones.

| Width | Overlap with the 56px dash |
| --- | --- |
| 1440 | **34px covered** (61% of it) |
| 768 | **entirely behind the pill** |
| 430 | clears by 8px |
| 390 | clears by 120px |

### ② The pill floats 72px up on phones, for a bar that is not there

The 72px offset exists to clear the dashboard `BottomNav`. `BottomNav` is only rendered by `Layout.tsx`, which public pages never use. Checked at all fourteen widths: **absent every time**. Desktop sits at 20px, so phones are inconsistent with desktop and the gap is above empty space.

---

## 3 · The options — pick one for each

![The four options, desktop and phone](./3-options.png)

### For the dash

| | What it does | Cost |
| --- | --- | --- |
| **A** | Dash moves under the tagline. Right side genuinely blank. | None. No new behaviour, collision gone at every width. |
| **B** | Pill fades out while the footer is in view. | Removes the support button exactly when someone has read to the end. |
| **C** | Footer keeps a 150px right gutter. | Spends 150px on an invisible reservation; dash still sits 20px from a floating object. |

**Recommended: A.** You asked for the right side of the footer to be blank, and right now the right side holds the dash. Moving it under the tagline puts the whole footer in one left column, makes the right side actually empty, and removes the collision at every width without the pill having to hide or the footer growing a gutter nobody sees.

### For the offset

**72px → 20px on public pages.** The dashboard keeps 72px, because there the bar is real. The offset becomes conditional on the app shell instead of applying everywhere.

---

## 4 · The defect I would fix first — the page scrolls past its own footer

![The scroll defect, before and after](./4-scroll-defect.png)

These are real mouse-wheel scrolls to the end of the page, not scripted jumps.

`src/styles/Layout.css:30` sets:

```css
html, body {
  height: 100%;
  overflow-y: auto;
}
```

A height **and** `overflow-y: auto` on **both** elements creates two nested scroll containers. The content scrolls inside `body`; `html` keeps its own leftover scroll range stacked on top of it — and that leftover range is pure empty space.

| Width | Document scroller | Body scroller | Blank below footer | `End` key |
| --- | --- | --- | --- | --- |
| 320 × 568 | 623px | 2012px | **623px** — footer scrolls off the top | dead |
| 390 × 844 | 196px | 1724px | **196px** | dead |
| 1440 × 900 | 0px | 1248px | 0px | dead |
| **with the fix** | 2012 / 1724 / 1248px | **0px** | **0px** | works |

On a 320px phone, reaching the end of the home page shows a **completely blank white screen** — the fixed header and the pill, nothing else. Desktop escapes it only because html's leftover range happens to compute to 0 at 900px tall.

Two side effects worth knowing:

- The **`End` key does nothing on any device**, because it scrolls the document and the document is not where the content lives.
- `window.scrollY` is permanently **0** on desktop, so any future scroll-triggered behaviour would silently never fire.

The fix is two lines and is measured green at all three widths above. But `html, body` is inherited by all 123 pages including the dashboard, and a signed-in dashboard cannot be rendered from the sandbox to prove the sidebar survives it. **It deserves its own branch and its own review, not a ride along with a footer tweak.**

---

## Decisions needed

1. Dash — **A**, **B** or **C**?
2. Phone offset 72px → 20px — **yes / no**?
3. Scroll fix — **now**, on its own branch, or **park it**?
4. Still open from the last round: delete `src/pages/contact-test/index.tsx`? It is de-listed so it is no longer public, but the file is still in the tree.
