# Deck screenshots

Drop image files here with these exact names, then re-run `python make_deck.py`.
Anything missing is drawn as a dashed placeholder box instead, so the deck always
builds.

| Filename | Slide | What it should show |
| --- | --- | --- |
| `streamlit-main.png` | 5 | The Streamlit interface, ideally mid-annotation with terms visible |

Aspect ratio is preserved and the image is centred in its box, so no need to crop to
a particular size. The slot on slide 5 is roughly 7.45 × 4.05 inches — a 16:10-ish
landscape screenshot fills it best. PNG is preferred over JPG for UI screenshots.

Two things worth having in the frame: at least one **non-English input** and the
**HPO IDs** next to the terms. Those are what make the screenshot evidence rather
than decoration.

These files are committed — they are deck content, not working data.
