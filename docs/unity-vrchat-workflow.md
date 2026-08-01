# Unity and VRChat validation workflow

The original Blender material is the opaque/source candidate. The generated
`<source>__AMS_ALPHA` material is the alpha candidate. Their Blender node graphs
remain identical; Unity shader modes are configured manually.

For users whose Unity materials are already configured, the intended workflow
is deliberately small: analyze and review in Blender, assign the additional
slot, export, then bind the existing opaque and transparent Unity materials to
the corresponding imported sections. The extension does not rewrite Blender
shaders merely to imitate a Unity setup.

## Required ordinary Unity validation

1. Import the processed FBX into the documented Unity project/render pipeline.
2. Confirm both material sections/submeshes exist and are used.
3. Configure the source material as opaque.
4. Configure the alpha variant using a stock/project cutout or transparent mode.
5. Reassign existing Unity materials instead when an established project
   already has the intended opaque and alpha shader configurations.
6. Verify opaque and alpha faces, material counts, and the added draw-call cost.
7. Record Unity version, render pipeline, platform, and result.

This generic material/submesh test is required for release.

## VRChat reference test

The user will separately validate one documented VRChat SDK and shader package.
Record exact Unity, SDK, platform, and shader versions, settings, animation,
blendshape, and visual results. The result applies only to that tested stack and
must not be presented as universal shader compatibility.

Raw Blender alpha and a texel margin cannot reproduce Unity filtering, mipmaps,
compression, alpha cutoff, anisotropy, or shader-specific behavior exactly.
Reducing transparent overdraw may cost an additional material section/draw call.
