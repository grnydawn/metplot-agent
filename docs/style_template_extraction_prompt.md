# Style Template Extraction Prompt

This document defines the prompt template a vision-capable agent (Claude
Code, Claude Desktop, etc.) uses to extract a `style_template` JSON from
a user-provided reference plot image. The cycle-2 `plot-renderer` MCP
applies the resulting JSON deterministically.

## Schema (cycle-2 contract)

```json
{
  "colormap_kind": "sequential | diverging | categorical | null",
  "colormap_name": "<matplotlib name> | null",
  "vcenter": "<number> | null",
  "clip_pct": "[low, high] | null",

  "projection_family": "plate_carree | robinson | polar_stereo_north | polar_stereo_south | lambert_conformal | mercator | null",
  "extent_hint": "global | hemispheric | regional | null",

  "colorbar_position": "right | bottom | top | left | none | null",
  "legend_placement":  "best | outside_right | outside_bottom | none | null",
  "gridlines":         "none | light | heavy | null",
  "aspect":            "<number> | auto | null",
  "font_scale":        "<number 0.7..1.5> | null",

  "title_placement":   "top | none | null",
  "label_density":     "minimal | normal | verbose | null",

  "source": {
    "image_path": "<path or URL> | null",
    "extracted_by": "<model name> | null",
    "extracted_at": "<ISO timestamp> | null",
    "confidence":   "<float 0..1> | null"
  }
}
```

All fields are optional. If a field cannot be inferred with reasonable
confidence, set it to `null` and lower the overall `confidence` value.

## Extraction guidance

**colormap_kind**: Look at the colorbar (if present) and the data range.
- Smoothly varying single-hue or perceptually uniform → `sequential` (e.g. viridis, inferno)
- Symmetric around a midpoint, two-hue diverging palette → `diverging` (e.g. RdBu_r)
- Discrete blocks of unrelated colors → `categorical` (e.g. tab10)

**colormap_name**: Set only if the palette is unambiguously a known
matplotlib colormap. Otherwise leave `null` and let `colormap_kind`
drive the default selection. Common identifiable cmaps: `viridis`,
`inferno`, `plasma`, `magma`, `RdBu_r`, `RdYlBu_r`, `BrBG`, `coolwarm`,
`tab10`, `tab20`.

**vcenter**: For diverging cmaps, the value at which the central
neutral hue sits. Most commonly `0.0` (anomalies). Read the colorbar
tick labels.

**clip_pct**: If the colorbar visibly clips outliers (e.g. sharp
saturation at one or both ends), guess `[2, 98]`; if not visible, leave
`null`.

**projection_family**: Coastline shape inference.
- Straight horizontal/vertical gridlines, rectangle frame → `plate_carree`
- Curved gridlines, oval frame → `robinson`
- Polar circular frame, north hemisphere visible → `polar_stereo_north`
- Polar circular frame, south hemisphere visible → `polar_stereo_south`
- Conic, mid-latitude regional view → `lambert_conformal`
- Cylindrical with characteristic Mercator north-south stretch → `mercator`

**extent_hint**:
- `global` — full earth visible
- `hemispheric` — single hemisphere or large quadrant
- `regional` — single basin, country, continent

**colorbar_position**: Read from layout. Common: `right` for vertical
maps, `bottom` for landscape figures.

**legend_placement**: Time series / profile plots usually have legends.
- Inside the axes, lower-right or upper-right → `best`
- Outside the right edge → `outside_right`
- Outside the bottom → `outside_bottom`
- Absent → `none`

**gridlines**:
- No grid → `none`
- Faint grid → `light`
- Bold/heavy grid → `heavy`

**aspect**: For maps and rectangular plots, estimate width-to-height
ratio. For "natural" aspect (cartopy-default for the projection),
use `auto`.

**font_scale**: 1.0 is matplotlib default. Larger labels/titles → 1.2.
Tighter, smaller labels → 0.8.

**title_placement**: Almost always `top` if a title is visible.

**label_density**:
- Minimal axis labels and ticks → `minimal`
- Standard → `normal`
- Heavy annotation, multiple legends, callouts → `verbose`

## Confidence calibration

Set `source.confidence` based on how certain the extraction is:

- 0.9–1.0: All major fields inferable; reference image is clear, high-resolution, well-labeled.
- 0.7–0.9: Most fields confident; one or two ambiguous (e.g., colormap kind clear but exact name uncertain).
- 0.5–0.7: Some fields confident, others uncertain; reference image is small or low-contrast.
- < 0.5: Extraction is mostly guessing; consider returning very few fields and letting the renderer fall back to defaults.

## Example

**Reference image**: a global SST anomaly map with a horizontal
RdBu_r colorbar at the bottom, light gridlines, Robinson projection.

**Expected JSON**:

```json
{
  "colormap_kind": "diverging",
  "colormap_name": "RdBu_r",
  "vcenter": 0.0,
  "projection_family": "robinson",
  "extent_hint": "global",
  "colorbar_position": "bottom",
  "gridlines": "light",
  "aspect": "auto",
  "font_scale": 1.0,
  "title_placement": "top",
  "label_density": "normal",
  "source": {
    "image_path": "/data/refs/sst_anomaly_2024.png",
    "extracted_by": "claude-opus-4-7",
    "extracted_at": "2026-05-07T14:30:00Z",
    "confidence": 0.92
  }
}
```

## Renderer behavior

The cycle-2 `plot-renderer` MCP applies this JSON deterministically:
- Explicit fields in the user's render spec **override** template fields
  ("explicit > template > library_default").
- Unknown fields are recorded in `oracle.style_template_applied.fields_ignored`
  but never error.
- The `source` block flows through untouched into the oracle, so cycle-3
  skill-refiner can audit which plots came from which references.

See `docs/specs/2026-05-07-cycle-2-plot-renderer.md` §8 for the full
mapping table from template fields to renderer spec fields.
