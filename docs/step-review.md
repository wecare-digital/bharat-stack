# Workflow terminal — step colours, five ways

> ## DECIDED: **A**
>
> Owner picked **A** after seeing the five panels rendered. Shipped: hue lives on the dot and
> the chip, every step name holds `#fff` at 21:1, and the tick keeps its step's `--ink`.
>
> The deciding argument was only visible once the options were pictures. **On a sentence, a hue
> stops reading as an identifier and starts reading as a severity** — B put step 7, *"A provider
> failed, nobody noticed"*, in amber, which reads as a warning badge when the whole point of the
> line is that the failure was absorbed. This is the same reasoning already recorded in the
> component for excluding red from the dot palette.
>
> I had recommended **B** from the contrast figures alone, and the figures could not show this.
> The mock changed the answer — which is the argument for rendering options rather than
> describing them.
>
> This document is kept rather than deleted: it is the record of what was compared and why the
> recommendation was reversed.

The per-service dot hues shipped, and the report back was **"the dot colour changed, but the text colour is still lime green"**. That report was accurate. The reason was not visible in the diff.

`.wt-name.is-complete` is gated on `step.complete`, which is `true` for **exactly one of the eight steps**. So the rule recoloured a single line — lime `#d1f470` to green `#3da35a`, two greens, 16.89:1 down to 6.58:1 — while all eight `.wt-svc` pills stayed lime. The lime in the report was the pills.

Probed against the production export, `tools/browser/replaycheck.js`:

| # | service | dot | pill text | name text |
|---|---|---|---|---|
| 1 | `gateway` | blue `#2563eb` | lime `#d1f470` | white `#ffffff` |
| 2 | `auth` | purple `#9849e8` | lime `#d1f470` | white `#ffffff` |
| 3 | `contacts` | amber `#f0a818` | lime `#d1f470` | white `#ffffff` |
| 4 | `messaging` | lime `#d1f470` | lime `#d1f470` | white `#ffffff` |
| 5 | `commerce` | green `#3da35a` | lime `#d1f470` | white `#ffffff` |
| 6 | `billing` | blue `#2563eb` | lime `#d1f470` | white `#ffffff` |
| 7 | `queue` | amber `#f0a818` | lime `#d1f470` | white `#ffffff` |
| 8 | `platform` | green `#3da35a` | lime `#d1f470` | green `#3da35a` |

---

## The five panels

### TODAY — what ships now

Pill lime on all eight. Names white on seven, green on step 8 — the only row whose data says complete. This is the one-line change that was reported as "not showing".

![today](step-mock/today.png)

### PILL ONLY — pill takes its service hue, names untouched

The change you asked for three times, shown on its own. The pill holds the service name, which is exactly what the dot hue encodes, so lime there had stopped meaning anything.

![pill-only](step-mock/pill-only.png)

### A — pill hued, ALL names white

Hue stays decorative and lives only on the dot and the chip. Every name reads at 21:1, the highest on the panel. The tick alone carries "complete", and step 8 stops being the one dim row.

![a](step-mock/a.png)

### B — pill hued, ALL names take their own hue (AA, ≥4.5:1)

Eight coloured names instead of one, so the change is finally visible. Blue and purple lift 11% and 7% toward white to clear the floor; amber, lime and green are untouched.

![b](step-mock/b.png)

### C — pill hued, ALL names at AAA (≥7:1)

Same as B with a bigger lift on blue, purple and green. Rendered side by side it is very nearly indistinguishable from B, so the extra contrast margin buys almost nothing visible — and it inherits B's problem below.

![c](step-mock/c.png)


---

## Measured

Pill text sits on its own hue at 14% over black. Name text sits on the panel body, `#000`. Pill type is 11.5px and name type is 15px/600 — both count as normal text for WCAG, so the floor is **4.5:1** for AA and **7:1** for AAA.

| # | service | dot hue | pill ink on its chip | name at AA (B) | name at AAA (C) |
|---|---|---|---|---|---|
| 1 | `gateway` | blue `#2563eb` | `#3d74ed` on `#050e21` = **4.51:1** | `#3d74ed` = **4.92:1** | `#6993f1` = **7.04:1** |
| 2 | `auth` | purple `#9849e8` | `#9f56ea` on `#150a20` = **4.56:1** | `#9f56ea` = **4.99:1** | `#b57cee` = **7.08:1** |
| 3 | `contacts` | amber `#f0a818` | `#f0a818` on `#221803` = **8.60:1** | `#f0a818` = **10.32:1** | `#f0a818` = **10.32:1** |
| 4 | `messaging` | lime `#d1f470` | `#d1f470` on `#1d2210` = **13.10:1** | `#d1f470` = **16.89:1** | `#d1f470` = **16.89:1** |
| 5 | `commerce` | green `#3da35a` | `#3da35a` on `#09170d` = **5.78:1** | `#3da35a` = **6.58:1** | `#47a862` = **7.05:1** |
| 6 | `billing` | blue `#2563eb` | `#3d74ed` on `#050e21` = **4.51:1** | `#3d74ed` = **4.92:1** | `#6993f1` = **7.04:1** |
| 7 | `queue` | amber `#f0a818` | `#f0a818` on `#221803` = **8.60:1** | `#f0a818` = **10.32:1** | `#f0a818` = **10.32:1** |
| 8 | `platform` | green `#3da35a` | `#3da35a` on `#09170d` = **5.78:1** | `#3da35a` = **6.58:1** | `#47a862` = **7.05:1** |

### Why blue and purple need lifting at all

| hue | raw | on `#000` | verdict as text |
|---|---|---|---|
| lime | `#d1f470` | 16.89:1 | passes AAA |
| amber | `#f0a818` | 10.32:1 | passes AAA |
| green | `#3da35a` | 6.58:1 | passes AA, misses AAA |
| purple | `#9849e8` | 4.45:1 | **fails AA** |
| blue | `#2563eb` | 4.06:1 | **fails AA** |

This is also a **latent bug in what currently ships**, not only a question about the mock. The committed comment beside `.wt-name.is-complete` claims the lowest of the five is "blue at 4.06:1. Well clear of 4.5:1 for 15px/600 text". 4.06 is not clear of 4.5 — it is below it. Nothing is visibly broken today only because step 8, the single complete step, happens to be green. Mark step 1 or 6 complete and the panel ships failing text.

### The hues stay distinguishable

Closest pair after lifting is blue against purple at **131** RGB distance of a possible 765. Every other pair is 194 or more. And each lifted ink stays close enough to its own dot to read as the same colour — blue moves **43**.

---

## What each option costs

**A** — one hue per row, carried by the dot and the chip. Names all white at 21:1, the most readable text on the panel. "Complete" is carried by the tick and by the footer's *running* / *complete* wording, so nothing is lost that colour was uniquely saying. Step 8 stops being the only dim row.

**B** — colours eight names instead of one, so the change is unmistakable. Costs the panel's primary text: a name drops from 21:1 to as low as 4.51:1.

**C** — B with a bigger lift. Rendered at size it is very nearly indistinguishable from B, so it pays a palette cost for a margin nobody can see.

---

## I am revising my own recommendation, and the mock is the reason

I recommended **B** before rendering it, on the argument that it was the only option that made the change visible. Looking at it, B has a problem the numbers could not show:

**On a sentence, a hue stops reading as an identifier and starts reading as a severity.**

- Row 7, *"A provider failed, nobody noticed"*, renders in **amber**. Amber on a sentence about a failure reads as a warning badge. The whole point of that line is that the failure was absorbed and nothing needed attention.
- Row 6, *"Usage metered"*, renders in **blue**, which reads as an info notice.

This is precisely the reasoning already recorded in this component for **excluding red** from the dot palette — red on "A provider failed" would read as an alarm about the thing being described. That argument applies with more force to a full sentence than to a 12px dot, and B puts the hue on the sentence.

The pill does not have this problem, and the difference is worth being precise about: a chip containing the single word `queue` is self-evidently an identifier, so colouring it reinforces identity. A chip cannot be mistaken for a severity because it is not a claim about anything. The sentence beside it can.

**So: A.** It resolves the original report completely — there is no lime text left anywhere in the panel, every row's hue is visible on its dot *and* its chip, and the change lands on all eight rows instead of one. It keeps the panel's primary text at 21:1, and it removes the current defect where step 8 is the only dim row. Colour ends up carrying exactly one meaning, *which service*, in the two places that are unambiguously labels.

None of the five panels changes what colour *means*: hue says **which service**, while motion, the tick and the footer wording say **whether it ran**. WCAG 1.4.1 stays unengaged throughout. A is the only one where hue never lands on a sentence.

---

Regenerate: `node tools/browser/stepreview.js`
