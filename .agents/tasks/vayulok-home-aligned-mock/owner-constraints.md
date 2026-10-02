# Owner constraints — vayulok home-aligned mock

Standing constraints for every later step in this run. The owner's words win over
any paraphrase.

## 1. Section order (exactly 11, in this order)

1. Header — brand + search
2. Top section — place, Now summary
3. FULL-WIDTH MAP (live)
4. Fact rail
5. Health advisory
6. Signal strip
7. Next 24 hours
8. Air / Weather tabs — pollutants, insights, history
9. Subscribe
10. Contribute
11. Footer

## 2. Label correction — "Contribute", not "Contribution"

Owner was explicit: *"Contribute not CONTRIBUTION"*.

- The visible section heading reads **Contribute**.
- Do NOT uppercase it via CSS (`text-transform: uppercase`) — the owner objected
  to the all-caps form. Use the same sentence casing the home page uses for its
  headings.
- Internal identifiers do NOT need renaming: CSS class names, element ids, and
  the source component filename `BlogContribution.tsx` stay as they are. This is
  about viewer-facing label text only.
- The Subscribe section keeps its label as **Subscribe**.

## 3. Design alignment

- Must match the existing home page design: CSS, UI, UX and colour scheme.
- **NO RED anywhere** in the palette.

## 4. Live map

- Map is live and keyed at runtime. **No API key is ever committed** to the repo.
- Google attribution must be preserved.

## 5. Footer

- Left as a clearly labelled placeholder pending the owner's own copy.
