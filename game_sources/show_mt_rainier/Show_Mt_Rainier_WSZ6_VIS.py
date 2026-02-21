"""
Show_Mt_Rainier_WSZ6_VIS.py

WSZ6 visualization module for the Mt. Rainier Views game.
Companion to Show_Mt_Rainier_SZ6.py.

Demonstrates M2 image-resource feature: images are stored in the game
directory and served via the /play/game-asset/<slug>/<filename> endpoint.

render_state(state) -> str
    Returns an HTML card showing the current image, its title, caption,
    and a progress indicator.
"""

_IMG_SUBDIR  = 'Show_Mt_Rainier_images'   # images subdirectory inside the game dir

# Pulled from the PFF at import time so the vis stays in sync with any
# future changes to the image list.  No circular import: we use
# importlib-style lazy access via the module attribute set on the formulation.
# Actually, we just re-declare the minimal info the vis needs (filename only).
# The PFF owns the full metadata; the vis needs the filename to build a URL.
#
# Rather than import from the PFF (which would create a circular dependency
# since the PFF imports us), we rely on state attributes.  The state carries
# current_idx and the IMAGES list is referenced through the PFF's module-level
# constant — but to avoid the circular import we simply re-read it from the
# state's module.  The cleanest approach: the state object exposes a helper.


def render_state(state, base_url='') -> str:
    """Return an HTML string displaying the current Mt. Rainier image.

    ``base_url`` is injected by the game runner as ``/play/game-asset/<slug>/``.
    Image URLs are constructed as ``base_url + _IMG_SUBDIR + '/' + filename``.
    """
    # The state object has current_idx and viewed_indices.
    # The IMAGES list lives in the PFF module; we access it through the
    # state's class module to avoid a circular import.
    images = _get_images(state)
    if not images:
        return '<p style="color:red">Could not load image list from state.</p>'

    idx     = getattr(state, 'current_idx', 0)
    viewed  = getattr(state, 'viewed_indices', set())
    total   = len(images)
    seen    = len(viewed)
    at_goal = (seen == total)

    filename, title, caption = images[idx]
    img_url = f'{base_url}{_IMG_SUBDIR}/{filename}'

    # Progress dots: filled circle for viewed, empty for unseen.
    dot_html = _progress_dots(viewed, total)

    # Goal banner (shown only when all images viewed).
    goal_html = ''
    if at_goal:
        goal_html = (
            '<div style="margin:0 0 .8rem 0; padding:.5rem 1rem;'
            ' background:#e8f5e9; border-radius:6px; color:#1b5e20;'
            ' font-weight:600; font-size:.95rem;">'
            '&#10003; All views explored!'
            '</div>'
        )

    return f'''
<div style="
    font-family: Georgia, 'Times New Roman', serif;
    max-width: 700px;
    margin: 0 auto;
    color: #212121;
">
  {goal_html}

  <!-- Image -->
  <div style="
      border-radius: 8px;
      overflow: hidden;
      box-shadow: 0 4px 18px rgba(0,0,0,.22);
      margin-bottom: .9rem;
      background: #e0e0e0;
  ">
    <img src="{_esc_attr(img_url)}"
         alt="{_esc_attr(title)}"
         style="width:100%; display:block; height:auto;"
         loading="eager">
  </div>

  <!-- Title -->
  <h2 style="
      margin: 0 0 .4rem 0;
      font-size: 1.3rem;
      font-weight: 700;
      color: #1a3a5c;
  ">{_esc(title)}</h2>

  <!-- Caption -->
  <p style="
      margin: 0 0 .9rem 0;
      font-size: .93rem;
      line-height: 1.65;
      color: #444;
  ">{_esc(caption)}</p>

  <!-- Progress -->
  <div style="
      display: flex;
      align-items: center;
      gap: .5rem;
      font-size: .82rem;
      color: #666;
  ">
    <span>Scenes viewed:</span>
    {dot_html}
    <span style="margin-left:.2rem;">({seen}&thinsp;/&thinsp;{total})</span>
  </div>
</div>
'''.strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_images(state):
    """Return the IMAGES list by reading it from the state's class module."""
    try:
        import sys
        # The state class is defined in the PFF module.  That module has an
        # IMAGES attribute at module level.
        module = sys.modules.get(type(state).__module__)
        if module and hasattr(module, 'IMAGES'):
            return module.IMAGES
    except Exception:
        pass
    return []


def _progress_dots(viewed_indices, total):
    """Return HTML for a row of progress dots (filled = viewed)."""
    dots = []
    for i in range(total):
        if i in viewed_indices:
            dots.append(
                '<span title="Viewed" style="'
                'display:inline-block; width:12px; height:12px;'
                ' border-radius:50%; background:#1565c0;'
                ' border:2px solid #1565c0;"></span>'
            )
        else:
            dots.append(
                '<span title="Not yet viewed" style="'
                'display:inline-block; width:12px; height:12px;'
                ' border-radius:50%; background:transparent;'
                ' border:2px solid #90a4ae;"></span>'
            )
    return ' '.join(dots)


def _esc(text):
    """Escape HTML special characters for text content."""
    return (str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;'))


def _esc_attr(text):
    """Escape for use inside an HTML attribute value."""
    return (str(text)
            .replace('&', '&amp;')
            .replace('"', '&quot;')
            .replace('<', '&lt;')
            .replace('>', '&gt;'))
