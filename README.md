# Blender Alpha Material Separator

Blender Alpha Material Separator is a standalone Blender 5.2 LTS extension for
finding mesh faces whose UV-covered image texels need alpha rendering. Its
production operation assigns those faces to a distinct material slot without
cutting or separating geometry.

Version 0.1 is in development. The repository is currently at the material
support characterization checkpoint; alpha analysis and assignment are not yet
implemented.

## Why this exists

Avatar materials commonly use transparent rendering for an entire mesh even
when most of its faces only cover fully opaque texture regions. In Unity this
can cause avoidable transparent overdraw and sorting costs. The extension is
designed to keep proven-opaque faces on the original material while routing
faces that need alpha to a derived material.

The tradeoff is an additional material section, which commonly means another
draw call. The extension reports the estimated slot/section increase so the
user can decide whether the overdraw reduction is worthwhile.

## Planned workflow

1. Select one or more original/base mesh objects in Blender.
2. Resolve each polygon's material, image, and UV map.
3. Rasterize every texel cell with positive-area intersection with each UV
   triangle; centroid, vertex-only, and sparse sampling are not used.
4. Review the report and preview affected faces.
5. Assign reviewed alpha-affected and mixed faces to `<source>__AMS_ALPHA`.
6. Export the model and configure the two materials manually in Unity.

## Classification terms

- **Opaque**: no covered texel is below the configured alpha threshold.
- **Alpha-affected**: significant alpha evidence exists across the entire face.
- **Mixed**: the same original polygon covers both opaque and alpha-affected
  texels. It cannot become fully opaque without cutting geometry.
- **Suppressed**: alpha evidence exists but user-configured significance filters
  rejected it. Suppressed evidence is never reported as proven opacity and
  blocks assignment by default.
- **Unsupported**: the extension cannot make a trustworthy determination.

## Material support boundary

Guaranteed version 0.1 inputs are:

- An Image Texture Alpha output directly connected to the active Principled
  BSDF Alpha input.
- Explicit image and UV-map overrides.
- Repeat, Extend, Clip, and Mirror image addressing.

Additional automatic graph patterns remain unsupported until the bounded,
anonymized characterization matrix in
[`docs/material-support.md`](docs/material-support.md) is approved. Ambiguous
materials are reported rather than guessed.

## Unity and VRChat

The original Blender material remains the source/opaque candidate. The derived
`__AMS_ALPHA` material represents alpha-affected and mixed faces. Blender
material duplication does **not** configure Unity or VRChat shaders.

After FBX import:

1. Confirm that the source and alpha material sections both exist and are used.
2. Configure the source material as opaque.
3. Configure the alpha variant as cutout/alpha-clip or transparent in the
   chosen shader.
4. Reapply the same color, normal, and mask textures as needed.
5. Validate filtering, mipmaps, compression, cutoff, animation, and blendshapes
   in the target project.

Raw Blender image alpha and an optional texel margin cannot exactly reproduce
Unity texture filtering, mipmaps, compression, alpha clipping, or
shader-specific behavior. Ordinary Unity submesh/material validation is a
release requirement. VRChat SDK and shader validation is a documented reference
test for the exact versions tested, not a universal compatibility claim.

## Version 0.1 exclusions

- Topology cutting, subdivision, or physical object separation.
- Shader rewriting or Unity editor automation.
- Automatic CATS integration or a CATS dependency.
- Evaluated-modifier topology analysis.
- Arbitrary or ambiguous shader evaluation.
- Automatic make-local or single-user conversion.
- Runtime dependency installation, updating, telemetry, or network access.

## Development

The extension package lives directly under `addon/`; tests, scripts, and
documentation remain outside the packaged directory.

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'

python -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
& $Blender52 --factory-startup --command extension build --source-dir addon --output-dir .packaged-releases
```

Private references belong only in `.local-references/`. Built ZIPs belong only
in `.packaged-releases/`. Both locations are ignored by Git.

## License

Blender Alpha Material Separator is licensed under
`GPL-3.0-or-later`. The canonical GNU GPL version 3 text is preserved in
[`LICENSE`](LICENSE).
