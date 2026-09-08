# Noto Sans KR (Korean subset)

Burned into every rendered short by libass. Kept in the repo rather than
installed system-wide so a clone renders identically on any machine, with no
admin rights and no font step during setup.

- Source: [`@fontsource/noto-sans-kr`](https://www.npmjs.com/package/@fontsource/noto-sans-kr) v5, Korean subset
- Converted woff2 → TTF with `fontTools`; libass reads TTF/OTF, not woff2
- Licence: **SIL Open Font License 1.1** — redistribution is permitted
  <https://openfontlicense.org>

`scripts/setup_render_env.sh` regenerates these only if they are missing.
Point `FONT_DIR` elsewhere to use a different face.
