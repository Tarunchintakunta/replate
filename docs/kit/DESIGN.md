# Design — Replate

Replate should feel like a proofing desk, not a model marketplace.

## Tone

Quiet, exact, short labels. The picture is the loudest thing on the screen. Say what the control does. Do not say “unleash”, “magic”, or “powered by AI” in the product UI. One line under the name is enough: “Change the words. Keep the picture.”

Best-effort is honest. Near the generate button: “Font and background matching is best-effort.”

## Type and color

- Display and wordmark: Newsreader.
- UI: IBM Plex Sans.
- Mono for credit counts only: IBM Plex Mono.
- Paper `#f3efe6`
- Ink `#1c1915`
- Green `#0e6b52` for the primary button and the focus ring
- Green wash `#e5f2ec` for a selected line
- Rule `#d9d2c5`
- Danger `#8f2d2d`
- Disabled ink at 40% opacity

No gradients. No blur. No drop shadows larger than `0 1px 0` on a pressed sheet. Corners 6px on controls, 2px on the image frame. The image sits on a 1px ink rule, like a print on a desk.

## Logo

Wordmark “Replate” in Newsreader italic. No sparkle icon. No cloned mark.

## Layout

Desktop, two columns, full height under a 56px bar.

- Bar: wordmark, credit balance, provider pill (`Local preview` for mock, `Gemini` or `WaveSpeed` when live), account.
- Left, about 60%: the image. Selected boxes are 2px green. Hovered boxes are 1px ink. A draw tool in the corner.
- Right, about 40%: “Lines” list. Each row is the detected text, a field for the new text, and a checkbox. Empty field means remove. Bottom of the column is the generate button, the cost “10 credits”, and the download link after success.

Narrow window, under 800px: image, then the list, then the button. The button stays visible.

## States

- Empty: a drop area with “Drop a PNG, JPG, or WebP.” No illustration pack.
- Working: the button label becomes “Replacing…” and is disabled. The image stays visible.
- Error: one sentence in danger color above the button. The image does not clear.
- No credits: button disabled, text “No credits left.”
- Success: the new image replaces the preview. “Download PNG” is a text button, not a modal.

## Motion

Selection and button state change in under 150ms. No page transitions. No confetti.

## Accessibility

- Every control has a visible focus ring in the green.
- Boxes are buttons with the detected text as the name.
- Color is not the only selected state. A selected row has a check.
- Contrast of ink on paper stays above 7:1 for body text.

## Do not ship

A pricing countdown, a locale switcher, comparison tables, or a marketing homepage that delays the workspace. The `/` route is the workspace. A one-screen `/pricing` can exist when Stripe arrives. It lists the pack in plain numbers. No crossed-out fantasy price.
