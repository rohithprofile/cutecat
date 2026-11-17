import math
import os
import time
import numpy as np
import bpy

TEX_DIR = r"C:\Users\Rohith\cute-cat-3d\textures"


def ensure_tex_dir():
    os.makedirs(TEX_DIR, exist_ok=True)


def value_noise_2d(h, w, scale_y, scale_x, seed=0):
    rng = np.random.default_rng(seed)
    gh = max(2, int(scale_y) + 2)
    gw = max(2, int(scale_x) + 2)
    grid = rng.random((gh, gw), dtype=np.float32)

    ys = np.linspace(0, gh - 2, h, dtype=np.float32)
    xs = np.linspace(0, gw - 2, w, dtype=np.float32)
    yi = np.floor(ys).astype(np.int32)
    xi = np.floor(xs).astype(np.int32)
    yf = ys - yi
    xf = xs - xi
    # Smoothstep
    yf = yf * yf * (3.0 - 2.0 * yf)
    xf = xf * xf * (3.0 - 2.0 * xf)

    c00 = grid[yi[:, None], xi[None, :]]
    c10 = grid[yi[:, None], (xi + 1)[None, :]]
    c01 = grid[(yi + 1)[:, None], xi[None, :]]
    c11 = grid[(yi + 1)[:, None], (xi + 1)[None, :]]

    top = c00 * (1.0 - xf[None, :]) + c10 * xf[None, :]
    bot = c01 * (1.0 - xf[None, :]) + c11 * xf[None, :]
    return top * (1.0 - yf[:, None]) + bot * yf[:, None]


def hash_noise_3d_coords(cx, cy, cz):
    """Fast deterministic trigonometric multi-octave smooth pseudo-noise on 3D coords."""
    n1 = np.sin(cx * 1.13 + np.cos(cy * 1.37 + cz * 0.91)) * np.cos(cz * 1.29 - np.sin(cx * 0.83))
    n2 = np.sin(cx * 2.41 - cy * 1.93 + np.sin(cz * 2.17)) * 0.5
    n3 = np.cos(cy * 4.37 + cz * 3.89 + np.cos(cx * 4.11)) * 0.25
    return (n1 + n2 + n3) * 0.55


def np_smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def np_gauss(x, mu, sigma):
    d = (x - mu) / sigma
    return np.exp(-0.5 * d * d)


def bake_pos_and_normal_maps(body, size=2048):
    """Bake 3D rest-pose Position & Normal maps onto Cat_Body's UVMap via 1-sample Cycles EMIT."""
    t0 = time.time()
    scene = bpy.context.scene
    prev_engine = scene.render.engine
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 1
    scene.cycles.use_denoising = False

    # Position image (biased into [0, 1]: (pos + 0.5) * 0.5)
    pos_img = bpy.data.images.new("Bake_Pos3D", size, size, alpha=False, float_buffer=True)
    norm_img = bpy.data.images.new("Bake_Norm3D", size, size, alpha=False, float_buffer=True)

    # Temp bake material
    mat = bpy.data.materials.new("Temp_Bake_Geo")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    geo = nt.nodes.new("ShaderNodeNewGeometry")

    # (Position + (0.5, 0.5, 0.2)) * 0.5
    vadd = nt.nodes.new("ShaderNodeVectorMath")
    vadd.operation = 'ADD'
    vadd.inputs[1].default_value = (0.5, 0.5, 0.2)
    vmul = nt.nodes.new("ShaderNodeVectorMath")
    vmul.operation = 'SCALE'
    vmul.inputs['Scale'].default_value = 0.5

    tex_node = nt.nodes.new("ShaderNodeTexImage")
    tex_node.image = pos_img
    nt.nodes.active = tex_node

    nt.links.new(geo.outputs['Position'], vadd.inputs[0])
    nt.links.new(vadd.outputs['Vector'], vmul.inputs[0])
    nt.links.new(vmul.outputs['Vector'], em.inputs['Color'])
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])

    old_mats = list(body.data.materials)
    body.data.materials.clear()
    body.data.materials.append(mat)

    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    with bpy.context.temp_override(object=body, active_object=body, selected_objects=[body]):
        bpy.ops.object.bake(type='EMIT', margin=4, use_clear=True)

    pos_buf = np.empty(size * size * 4, dtype=np.float32)
    pos_img.pixels.foreach_get(pos_buf)
    pos_arr = pos_buf.reshape((size, size, 4))[:, :, :3] * 2.0 - np.array([0.5, 0.5, 0.2], dtype=np.float32)

    # Now bake Normals: (Normal + 1) * 0.5
    vadd.inputs[1].default_value = (1.0, 1.0, 1.0)
    nt.links.new(geo.outputs['Normal'], vadd.inputs[0])
    tex_node.image = norm_img
    with bpy.context.temp_override(object=body, active_object=body, selected_objects=[body]):
        bpy.ops.object.bake(type='EMIT', margin=4, use_clear=True)

    norm_buf = np.empty(size * size * 4, dtype=np.float32)
    norm_img.pixels.foreach_get(norm_buf)
    norm_arr = norm_buf.reshape((size, size, 4))[:, :, :3] * 2.0 - 1.0

    # Restore original engine & material slots
    body.data.materials.clear()
    for m in old_mats:
        body.data.materials.append(m)
    scene.render.engine = prev_engine
    bpy.data.materials.remove(mat)
    bpy.data.images.remove(pos_img)
    bpy.data.images.remove(norm_img)

    print(f"Baked 2K Pos3D & Norm3D in {time.time()-t0:.2f}s")
    return pos_arr, norm_arr


def save_np_image(name, arr_rgb_01, is_srgb=True):
    """Create & save PNG to TEX_DIR and keep packed/loaded cleanly in bpy.data.images."""
    h, w, c = arr_rgb_01.shape
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[:, :, :c] = np.clip(arr_rgb_01, 0.0, 1.0)
    if name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[name])
    img = bpy.data.images.new(name, w, h, alpha=False)
    img.colorspace_settings.name = 'sRGB' if is_srgb else 'Non-Color'
    img.pixels.foreach_set(rgba.ravel())
    path = os.path.join(TEX_DIR, f"{name}.png")
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    return img, path


def generate_cat_coat_textures(pos_arr, norm_arr):
    """
    Generate ultra-detailed 2048x2048 seamless 3D-projected Tabby Fur PBR maps:
      - Cat_Fur_Albedo.png (Ginger-Cream Mackerel Tabby, White Bib/Muzzle/Mittens, Pink Ears)
      - Cat_Fur_Normal.png (Crisp directional hair-strand tangent normals)
      - Cat_Fur_Roughness.png (Silky guard hair sheen vs soft undercoat)
      - Cat_Coat_Mask.png (R=Tabby Stripes, G=White Markings, B=Ear Pink/Skin -> for WebGL live coat switcher!)
    """
    t0 = time.time()
    h, w, _ = pos_arr.shape
    x = pos_arr[:, :, 0]
    y = pos_arr[:, :, 1]
    z = pos_arr[:, :, 2]
    ax = np.abs(x)
    nx, ny, nz = norm_arr[:, :, 0], norm_arr[:, :, 1], norm_arr[:, :, 2]

    # 1. ANATOMICAL HAIR-STRAND SYNTHESIS (Seamless 3D directional coordinates!)
    # Blend smoothly between facial radial flow (from nose) and body downward/backward flow
    face_w = np_smoothstep(0.245, 0.275, z) * np_smoothstep(-0.025, -0.065, y)
    # Radial coordinates around nose (0, -0.105, 0.272)
    ang_face = np.arctan2(z - 0.272, x)
    rad_face = np.hypot(x, z - 0.272)

    # Body longitudinal vs circumferential flow
    body_along = z + y * 0.35
    body_across = x * 1.15 - y * 0.25

    # Ultra-fine directional hair fibers (2 octaves of guard hairs + soft undercoat)
    # Face hair is shorter & finer; body hair is plush & slightly longer
    strand_face = (
        np.sin(ang_face * 190.0 + hash_noise_3d_coords(x * 80.0, y * 80.0, z * 80.0) * 3.5) * 0.5
        + np.sin(ang_face * 340.0 + rad_face * 95.0) * 0.35
        + hash_noise_3d_coords(x * 380.0, y * 380.0, z * 190.0) * 0.35
    )
    strand_body = (
        np.sin(body_across * 520.0 + hash_noise_3d_coords(x * 45.0, y * 45.0, z * 45.0) * 4.0) * 0.5
        + np.sin(x * 820.0 + y * 640.0 + body_along * 110.0) * 0.35
        + hash_noise_3d_coords(x * 260.0, y * 260.0, z * 95.0) * 0.40
    )
    # Combine with UV high-freq micro-grain so strands stay razor sharp even in closeups
    uv_grain = value_noise_2d(h, w, 460, 460, seed=42) - 0.5
    hair_strands = np.clip(
        (face_w * strand_face + (1.0 - face_w) * strand_body) * 0.48 + uv_grain * 0.55,
        -1.0, 1.0
    )
    # Positive [0..1] hair fiber value for shading & bump
    hair_01 = np.clip(hair_strands * 0.5 + 0.5, 0.0, 1.0)

    # 2. TABBY MACKEREL STRIPES & FOREHEAD "M" MARKINGS
    warp = hash_noise_3d_coords(x * 32.0, y * 32.0, z * 32.0) * 0.012
    # Dorsal dark spine stripe
    spine_stripe = np_gauss(x + warp * 0.4, 0.0, 0.015) * np_smoothstep(-0.01, 0.04, y) * np_smoothstep(0.27, 0.21, z)
    # Flank mackerel ribs arching down sides
    flank_phase = (z - 0.04) * 72.0 + ax * 22.0 + y * 28.0 + warp * 140.0
    flank_stripes = np.power(np.clip(np.cos(flank_phase), 0.0, 1.0), 3.0)
    flank_mask = np_smoothstep(0.015, 0.045, ax) * np_smoothstep(0.245, 0.195, z) * np_smoothstep(0.09, 0.02, y + 0.04)
    # Tail tabby rings (tail extends to x > 0.02, z < 0.075)
    is_tail = np_smoothstep(0.018, 0.042, x) * np_smoothstep(0.085, 0.055, z) * (1.0 - np_smoothstep(0.04, 0.07, ax) * np_smoothstep(0.06, 0.02, z) * 0.0)
    # Better tail detector: tail curves outside body haunch (x > 0.085 or (y > 0.08 and x > 0.01))
    tail_zone = np.maximum(
        np_smoothstep(0.078, 0.095, x) * np_smoothstep(0.085, 0.060, z),
        np_smoothstep(0.095, 0.112, y) * np_smoothstep(0.065, 0.045, z)
    )
    tail_phase = (y * 1.2 + x * 1.4) * 95.0 + warp * 90.0
    tail_rings = np.power(np.clip(np.sin(tail_phase), 0.0, 1.0), 2.5) * tail_zone

    # Forehead Tabby "M" & Cheek Mascara Streaks (delicate arched tabby lines above brow!)
    forehead_zone = (
        np_smoothstep(0.298, 0.324, z + (hair_01 - 0.5) * 0.014)
        * np_smoothstep(-0.005, -0.050, y)
        * np_smoothstep(0.044, 0.008, ax)
    )
    m_stripes = (
        np_gauss(ax, 0.000, 0.0024) * np_smoothstep(0.324, 0.308, z)
        + np_gauss(ax - (z - 0.306) * 0.28, 0.011, 0.0026)
        + np_gauss(ax - (z - 0.304) * 0.45, 0.022, 0.0028)
    ) * forehead_zone

    # Cute mascara cheek lines sweeping back from outer eye corner
    cheek_line1 = np_gauss(z - (0.289 - (y + 0.078) * 0.16), 0.0, 0.0042) * np_smoothstep(0.025, 0.036, ax) * np_smoothstep(-0.085, -0.068, y) * np_smoothstep(-0.020, -0.048, y)
    cheek_line2 = np_gauss(z - (0.278 - (y + 0.078) * 0.10), 0.0, 0.0042) * np_smoothstep(0.027, 0.038, ax) * np_smoothstep(-0.085, -0.068, y) * np_smoothstep(-0.020, -0.048, y)

    # Combine tabby stripe mask & feather edges with hair strands!
    raw_stripe = np.clip(
        spine_stripe * 0.90
        + flank_stripes * flank_mask * 0.85
        + tail_rings * 0.95
        + m_stripes * 1.45
        + (cheek_line1 + cheek_line2) * 1.15,
        0.0, 1.0
    )
    stripe_mask = np_smoothstep(0.14, 0.62, raw_stripe + (hair_01 - 0.5) * 0.30)

    # 3. SNOWY WHITE BIB, MUZZLE PADS, CHIN, BELLY & MITTEN PAWS!
    muzzle_white = (
        np_smoothstep(-0.086, -0.097, y)
        * np_smoothstep(0.274, 0.264, z + ax * 0.42)
        * np_smoothstep(0.028, 0.012, ax)
    )
    chin_white = np_smoothstep(0.265, 0.250, z) * np_smoothstep(-0.055, -0.078, y) * np_smoothstep(0.024, 0.009, ax)
    # Fluffy chest bib tapering neatly between forelegs so legs stay ginger down to white mittens!
    bib_width = 0.015 + 0.022 * np_smoothstep(0.15, 0.23, z)
    bib_white = (
        np_smoothstep(0.246, 0.205, z)
        * np_smoothstep(0.010, -0.032, y)
        * np_smoothstep(bib_width, bib_width * 0.32, ax)
    )
    # Cute white dipped paws ("mittens") on forepaws & front toes of hindpaws (no white thigh blotch!)
    fore_paws_white = np_smoothstep(0.030, 0.015, z) * np_smoothstep(-0.035, -0.052, y) * np_smoothstep(0.046, 0.032, ax)
    hind_paws_white = np_smoothstep(0.022, 0.010, z) * np_smoothstep(-0.024, -0.038, y) * np_smoothstep(0.038, 0.050, ax) * (1.0 - tail_zone)
    paws_white = np.maximum(fore_paws_white, hind_paws_white)
    # Tiny cream tail tip
    tail_tip_white = np_smoothstep(0.044, 0.058, z) * np_smoothstep(-0.035, -0.055, y) * np_smoothstep(0.080, 0.098, x)

    raw_white = np.clip(np.maximum.reduce([muzzle_white, chin_white, bib_white, paws_white, tail_tip_white]), 0.0, 1.0)
    white_mask = np_smoothstep(0.28, 0.72, raw_white + (hair_01 - 0.5) * 0.38)

    # 4. ROSY PINK INNER EAR SKIN & DARK EYELINER RIM!
    ear_bowl = (
        np_smoothstep(0.028, 0.040, ax)
        * np_smoothstep(0.324, 0.336, z)
        * np_smoothstep(0.362, 0.346, z)
        * np_smoothstep(-0.05, -0.35, ny)
        * np_smoothstep(-0.065, -0.038, y)
    )
    # Very subtle inner lash-margin darkening only (no dark raccoon smudge around eyes!)
    d_eye_l = np.sqrt((x - 0.028) ** 2 + (y + 0.084) ** 2 + (z - 0.298) ** 2)
    d_eye_r = np.sqrt((x + 0.028) ** 2 + (y + 0.084) ** 2 + (z - 0.298) ** 2)
    d_eye = np.minimum(d_eye_l, d_eye_r)
    eyeliner = np_smoothstep(0.0125, 0.0105, d_eye) * (1.0 - ear_bowl)

    # Subtle cute cream eyebrow puffs right above eyes
    brow_cream = (
        np_smoothstep(-0.072, -0.086, y)
        * np_gauss(z, 0.314, 0.0045)
        * np_gauss(ax, 0.027, 0.0085)
    )
    white_mask = np.clip(white_mask + brow_cream * 0.32 * (1.0 - stripe_mask), 0.0, 1.0)

    # Cute subtle rosy whisker follicle dimples on white muzzle pads
    follicle_dots = (
        np_smoothstep(-0.095, -0.100, y)
        * np_smoothstep(0.272, 0.264, z)
        * np_smoothstep(0.022, 0.010, ax)
        * np.power(np.clip(np.sin(ax * 780.0) * np.sin(z * 780.0), 0.0, 1.0), 6.0)
    )

    # 5. ASSEMBLE PHOTOREALISTIC LINEAR RGB ALBEDO (Rich Warm Marmalade-Ginger!)
    c_base_light = np.array([0.62, 0.26, 0.075], dtype=np.float32)
    c_base_dark = np.array([0.36, 0.13, 0.030], dtype=np.float32)
    col = c_base_dark[None, None, :] * (1.0 - hair_01[:, :, None]) + c_base_light[None, None, :] * hair_01[:, :, None]

    # Rich deep chestnut-cinnamon tabby stripes
    c_stripe = np.array([0.14, 0.042, 0.008], dtype=np.float32)
    c_stripe_hi = np.array([0.24, 0.078, 0.018], dtype=np.float32)
    col_st = c_stripe[None, None, :] * (1.0 - hair_01[:, :, None] * 0.7) + c_stripe_hi[None, None, :] * (hair_01[:, :, None] * 0.7)
    col = col * (1.0 - stripe_mask[:, :, None]) + col_st * stripe_mask[:, :, None]

    # Warm cream-ivory white coat (with subtle hair warmth!)
    c_white = np.array([0.92, 0.87, 0.80], dtype=np.float32)
    c_white_sh = np.array([0.76, 0.70, 0.62], dtype=np.float32)
    col_wh = c_white_sh[None, None, :] * (1.0 - hair_01[:, :, None]) + c_white[None, None, :] * hair_01[:, :, None]
    col = col * (1.0 - white_mask[:, :, None]) + col_wh * white_mask[:, :, None]

    # Blush pink inner ear
    c_ear_pink = np.array([0.74, 0.34, 0.34], dtype=np.float32)
    col = col * (1.0 - ear_bowl[:, :, None]) + c_ear_pink[None, None, :] * ear_bowl[:, :, None]

    # Eyeliner & cute subtle `:3` mouth smile cleft under nose!
    mouth_smile_z = 0.2605 - 0.0022 * np.cos(ax * 260.0)
    mouth_line = (
        np_gauss(z - mouth_smile_z, 0.0, 0.0011)
        * np_smoothstep(0.013, 0.002, ax)
        * np_smoothstep(-0.092, -0.101, y)
    )
    philtrum_line = np_gauss(ax, 0.0, 0.0009) * np_smoothstep(0.271, 0.266, z) * np_smoothstep(0.258, 0.262, z) * np_smoothstep(-0.095, -0.102, y)
    c_liner = np.array([0.04, 0.025, 0.02], dtype=np.float32)
    c_mouth = np.array([0.38, 0.18, 0.16], dtype=np.float32)
    col = col * (1.0 - eyeliner[:, :, None] * 0.90) + c_liner[None, None, :] * (eyeliner[:, :, None] * 0.90)
    m_mix = np.clip(mouth_line + philtrum_line * 0.75, 0.0, 1.0)[:, :, None] * 0.65
    col = col * (1.0 - m_mix) + c_mouth[None, None, :] * m_mix
    col = col * (1.0 - follicle_dots[:, :, None] * 0.25)

    # Soft crevice Ambient Occlusion
    ao = (
        1.0
        - 0.16 * np_smoothstep(0.022, 0.0155, d_eye)
        - 0.10 * np_gauss(z, 0.242, 0.016) * np_smoothstep(-0.04, -0.07, y)
        - 0.14 * np_smoothstep(0.014, 0.001, z)
    )
    col *= np.clip(ao, 0.72, 1.0)[:, :, None]

    col_srgb = np.power(np.clip(col, 0.0, 1.0), 1.0 / 2.2)

    # 6. TANGENT-SPACE HAIR-STRAND NORMAL MAP (Silky subtle directional bump)
    fur_height = hair_strands * (1.0 - ear_bowl * 0.80) * 0.42
    gy, gx = np.gradient(fur_height)
    bump_strength = 1.45
    tnx = -gx * bump_strength
    tny = -gy * bump_strength
    tnz = np.ones_like(tnx)
    tlen = np.sqrt(tnx * tnx + tny * tny + tnz * tnz) + 1e-6
    norm_tan = np.stack([tnx / tlen * 0.5 + 0.5, tny / tlen * 0.5 + 0.5, tnz / tlen * 0.5 + 0.5], axis=-1)

    # 7. ROUGHNESS MAP (Guard fur ~0.58-0.75, glossy ear skin ~0.48)
    rough_val = 0.62 + (1.0 - hair_01) * 0.16 - ear_bowl * 0.14 - eyeliner * 0.18
    rough_rgb = np.repeat(np.clip(rough_val, 0.35, 0.88)[:, :, None], 3, axis=2)

    # 8. COAT PATTERN MASK (R=Stripe, G=White, B=EarPink -> enables live WebGL coat color themes!)
    coat_mask = np.stack([stripe_mask, white_mask, ear_bowl], axis=-1)

    img_alb, p_alb = save_np_image("Cat_Fur_Albedo", col_srgb, is_srgb=True)
    img_nrm, p_nrm = save_np_image("Cat_Fur_Normal", norm_tan, is_srgb=False)
    img_rgh, p_rgh = save_np_image("Cat_Fur_Roughness", rough_rgb, is_srgb=False)
    img_msk, p_msk = save_np_image("Cat_Coat_Mask", coat_mask, is_srgb=False)
    print(f"Generated 2K Fur PBR maps in {time.time()-t0:.2f}s")
    return img_alb, img_nrm, img_rgh, img_msk


def generate_iris_texture(size=1024):
    """
    Generate photorealistic 1K Feline Iris texture mapped to UV Sphere where V=1.0 is front gaze pole!
    Rich amber-gold inner ring -> luminous emerald-chartreuse radial crypts -> dark limbal ring -> sclera.
    """
    ys = np.linspace(0.0, 1.0, size, dtype=np.float32)[:, None]  # V = 0 (back) .. 1 (front pupil pole)
    xs = np.linspace(0.0, 1.0, size, dtype=np.float32)[None, :]  # U = 0..1 around iris

    # Polar angle from front gaze pole (V=1.0)
    theta = (1.0 - ys) * math.pi
    phi = xs * 2.0 * math.pi
    # Iris radius covers ~64 deg from front pole so rich emerald-gold fills the eye opening!
    r = theta / math.radians(64.0)

    # Multi-frequency radial fibers & organic ciliary crypts (seamless in phi!)
    fibers = (
        np.sin(phi * 48.0 + np.sin(r * 14.0 + np.cos(phi * 12.0))) * 0.35
        + np.sin(phi * 112.0 - r * 8.0 + np.cos(phi * 29.0) * 1.5) * 0.30
        + np.cos(phi * 210.0 + r * 22.0) * 0.20
        + np.sin(phi * 17.0 + r * 6.0) * 0.15
    )
    fib_01 = np.clip(fibers * 0.5 + 0.5, 0.0, 1.0)

    # Color zones (linear space -> sRGB at end)
    c_gold = np.array([0.82, 0.56, 0.12], dtype=np.float32)       # Inner amber-gold halo
    c_emerald = np.array([0.28, 0.58, 0.18], dtype=np.float32)    # Luminous emerald-sage iris
    c_jade_dk = np.array([0.10, 0.28, 0.11], dtype=np.float32)    # Deep radial fiber shadow
    c_limbal = np.array([0.04, 0.08, 0.05], dtype=np.float32)     # Crisp dark limbal edge
    c_sclera = np.array([0.78, 0.74, 0.68], dtype=np.float32)     # Soft shadowed sclera

    gold_mix = 1.0 - np_smoothstep(0.18, 0.44 + (fib_01 - 0.5) * 0.18, r)
    stroma = c_jade_dk[None, None, :] * (1.0 - fib_01[:, :, None]) + c_emerald[None, None, :] * fib_01[:, :, None]
    iris_col = stroma * (1.0 - gold_mix[:, :, None]) + c_gold[None, None, :] * gold_mix[:, :, None]

    # Golden flecks in mid iris
    flecks = np.power(np.clip(np.sin(phi * 31.0 + r * 19.0) * np.cos(phi * 53.0 - r * 11.0), 0.0, 1.0), 5.0)
    iris_col = iris_col + np.array([0.40, 0.26, 0.02], dtype=np.float32)[None, None, :] * flecks[:, :, None] * np_smoothstep(0.25, 0.5, r)[:, :, None] * (1.0 - np_smoothstep(0.65, 0.88, r)[:, :, None])

    # Dark limbal ring around r = 0.86..1.00
    limbal_w = np_smoothstep(0.80, 0.91, r) * (1.0 - np_smoothstep(0.98, 1.08, r))
    iris_col = iris_col * (1.0 - limbal_w[:, :, None]) + c_limbal[None, None, :] * limbal_w[:, :, None]

    # Sclera outside r > 1.00
    sclera_w = np_smoothstep(0.97, 1.06, r)
    final_col = iris_col * (1.0 - sclera_w[:, :, None]) + c_sclera[None, None, :] * sclera_w[:, :, None]

    col_srgb = np.power(np.clip(final_col, 0.0, 1.0), 1.0 / 2.2)
    img_iris, _ = save_np_image("Cat_Iris_Albedo", col_srgb, is_srgb=True)
    return img_iris


def generate_cushion_and_nose_textures():
    """Generate cozy bouclé fabric albedo/normal for cushion and pebbled normal for nose."""
    # Cushion 1024x1024 woven bouclé sage-linen fabric
    s = 512
    n1 = value_noise_2d(s, s, 96, 96, seed=7)
    n2 = value_noise_2d(s, s, 210, 210, seed=13)
    ys = np.linspace(0, 1, s, dtype=np.float32)[:, None]
    xs = np.linspace(0, 1, s, dtype=np.float32)[None, :]
    weave = (np.sin(xs * 260.0) * np.sin(ys * 260.0)) * 0.35 + (n1 - 0.5) * 0.45 + (n2 - 0.5) * 0.45
    c_sage = np.array([0.11, 0.18, 0.16], dtype=np.float32)[None, None, :]
    c_var = c_sage * (0.86 + 0.28 * np.clip(weave + 0.5, 0.0, 1.0)[:, :, None])
    c_srgb = np.power(np.clip(c_var, 0.0, 1.0), 1.0 / 2.2)
    gy, gx = np.gradient(weave)
    tlen = np.sqrt(gx * gx * 4.0 + gy * gy * 4.0 + 1.0)
    c_nrm = np.stack([-gx * 2.0 / tlen * 0.5 + 0.5, -gy * 2.0 / tlen * 0.5 + 0.5, 1.0 / tlen * 0.5 + 0.5], axis=-1)
    img_cush_alb, _ = save_np_image("Cushion_Albedo", c_srgb, is_srgb=True)
    img_cush_nrm, _ = save_np_image("Cushion_Normal", c_nrm, is_srgb=False)

    # Nose 512x512 pebbled moist rhinarium normal + rosy gradient
    ns = 512
    pebble = value_noise_2d(ns, ns, 140, 140, seed=99) * 0.6 + value_noise_2d(ns, ns, 240, 240, seed=101) * 0.4
    gy_n, gx_n = np.gradient(pebble)
    tl = np.sqrt(gx_n * gx_n * 3.0 + gy_n * gy_n * 3.0 + 1.0)
    n_nrm = np.stack([-gx_n * 1.7 / tl * 0.5 + 0.5, -gy_n * 1.7 / tl * 0.5 + 0.5, 1.0 / tl * 0.5 + 0.5], axis=-1)
    img_nose_nrm, _ = save_np_image("Cat_Nose_Normal", n_nrm, is_srgb=False)
    return img_cush_alb, img_cush_nrm, img_nose_nrm


def build_pbr_materials(img_alb, img_nrm, img_rgh, img_iris, img_cush_alb, img_cush_nrm, img_nose_nrm):
    """Wire full Principled BSDF materials in Blender 5.3 for photorealistic rendering & clean glTF export."""

    def add_tex_node(nt, img, is_color=True):
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image = img
        return tn

    # 1. Cat Fur Material (Principled + Sheen + Hair Normal + Roughness)
    fur_mat = bpy.data.materials.new("Cat_Fur_PBR")
    fur_mat.use_nodes = True
    nt = fur_mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    t_alb = add_tex_node(nt, img_alb)
    t_rgh = add_tex_node(nt, img_rgh)
    t_nrm = add_tex_node(nt, img_nrm)
    nrm_map = nt.nodes.new("ShaderNodeNormalMap")
    nrm_map.inputs['Strength'].default_value = 0.50
    nt.links.new(t_alb.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(t_rgh.outputs['Color'], bsdf.inputs['Roughness'])
    nt.links.new(t_nrm.outputs['Color'], nrm_map.inputs['Color'])
    nt.links.new(nrm_map.outputs['Normal'], bsdf.inputs['Normal'])
    if 'Sheen Weight' in bsdf.inputs:
        bsdf.inputs['Sheen Weight'].default_value = 0.35
    if 'Sheen Roughness' in bsdf.inputs:
        bsdf.inputs['Sheen Roughness'].default_value = 0.55
    if 'Sheen Tint' in bsdf.inputs:
        bsdf.inputs['Sheen Tint'].default_value = (0.95, 0.76, 0.58, 1.0)
    if 'Subsurface Weight' in bsdf.inputs:
        bsdf.inputs['Subsurface Weight'].default_value = 0.08
    if 'Subsurface Scale' in bsdf.inputs:
        bsdf.inputs['Subsurface Scale'].default_value = 0.008

    # 2. Cat Iris Material
    iris_mat = bpy.data.materials.new("Cat_Iris_PBR")
    iris_mat.use_nodes = True
    nt_i = iris_mat.node_tree
    bsdf_i = next(n for n in nt_i.nodes if n.type == 'BSDF_PRINCIPLED')
    t_ir = add_tex_node(nt_i, img_iris)
    nt_i.links.new(t_ir.outputs['Color'], bsdf_i.inputs['Base Color'])
    bsdf_i.inputs['Roughness'].default_value = 0.25

    # 3. Pupil & Wet Cornea (Crystal-clear glass sheen over iris!)
    pupil_mat = bpy.data.materials.new("Cat_Pupil_PBR")
    pupil_mat.use_nodes = True
    bsdf_p = next(n for n in pupil_mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf_p.inputs['Base Color'].default_value = (0.005, 0.005, 0.007, 1.0)
    bsdf_p.inputs['Roughness'].default_value = 0.95
    if 'Specular IOR Level' in bsdf_p.inputs:
        bsdf_p.inputs['Specular IOR Level'].default_value = 0.0

    cornea_mat = bpy.data.materials.new("Cat_Cornea_PBR")
    cornea_mat.use_nodes = True
    nt_co = cornea_mat.node_tree
    nt_co.nodes.clear()
    out_co = nt_co.nodes.new("ShaderNodeOutputMaterial")
    mix_co = nt_co.nodes.new("ShaderNodeMixShader")
    trans_co = nt_co.nodes.new("ShaderNodeBsdfTransparent")
    gloss_co = nt_co.nodes.new("ShaderNodeBsdfGlossy")
    gloss_co.inputs['Roughness'].default_value = 0.015
    fres_co = nt_co.nodes.new("ShaderNodeLayerWeight")
    fres_co.inputs['Blend'].default_value = 0.10
    nt_co.links.new(fres_co.outputs['Fresnel'], mix_co.inputs['Fac'])
    nt_co.links.new(trans_co.outputs['BSDF'], mix_co.inputs[1])
    nt_co.links.new(gloss_co.outputs['BSDF'], mix_co.inputs[2])
    nt_co.links.new(mix_co.outputs['Shader'], out_co.inputs['Surface'])
    if hasattr(cornea_mat, 'surface_render_method'):
        cornea_mat.surface_render_method = 'BLENDED'
    if hasattr(cornea_mat, 'blend_method'):
        cornea_mat.blend_method = 'BLEND'

    # 4. Moist Pink Nose Leather
    nose_mat = bpy.data.materials.new("Cat_Nose_PBR")
    nose_mat.use_nodes = True
    nt_n = nose_mat.node_tree
    bsdf_n = next(n for n in nt_n.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf_n.inputs['Base Color'].default_value = (0.76, 0.34, 0.34, 1.0)
    bsdf_n.inputs['Roughness'].default_value = 0.24
    if 'Coat Weight' in bsdf_n.inputs:
        bsdf_n.inputs['Coat Weight'].default_value = 0.55
    if 'Subsurface Weight' in bsdf_n.inputs:
        bsdf_n.inputs['Subsurface Weight'].default_value = 0.25
    t_nn = add_tex_node(nt_n, img_nose_nrm)
    nm_n = nt_n.nodes.new("ShaderNodeNormalMap")
    nm_n.inputs['Strength'].default_value = 0.45
    nt_n.links.new(t_nn.outputs['Color'], nm_n.inputs['Color'])
    nt_n.links.new(nm_n.outputs['Normal'], bsdf_n.inputs['Normal'])

    # 5. Cushion Velvet Bouclé Material
    cush_mat = bpy.data.materials.new("Cushion_PBR")
    cush_mat.use_nodes = True
    nt_cu = cush_mat.node_tree
    bsdf_cu = next(n for n in nt_cu.nodes if n.type == 'BSDF_PRINCIPLED')
    t_ca = add_tex_node(nt_cu, img_cush_alb)
    t_cn = add_tex_node(nt_cu, img_cush_nrm)
    nm_cu = nt_cu.nodes.new("ShaderNodeNormalMap")
    nm_cu.inputs['Strength'].default_value = 0.60
    # Tile cushion UV slightly via UV or Generated
    tc = nt_cu.nodes.new("ShaderNodeTexCoord")
    mp = nt_cu.nodes.new("ShaderNodeMapping")
    mp.inputs['Scale'].default_value = (4.0, 4.0, 4.0)
    nt_cu.links.new(tc.outputs['UV'], mp.inputs['Vector'])
    nt_cu.links.new(mp.outputs['Vector'], t_ca.inputs['Vector'])
    nt_cu.links.new(mp.outputs['Vector'], t_cn.inputs['Vector'])
    nt_cu.links.new(t_ca.outputs['Color'], bsdf_cu.inputs['Base Color'])
    nt_cu.links.new(t_cn.outputs['Color'], nm_cu.inputs['Color'])
    nt_cu.links.new(nm_cu.outputs['Normal'], bsdf_cu.inputs['Normal'])
    bsdf_cu.inputs['Roughness'].default_value = 0.86
    if 'Sheen Weight' in bsdf_cu.inputs:
        bsdf_cu.inputs['Sheen Weight'].default_value = 0.65

    # Assign materials to scene objects!
    body = bpy.data.objects["Cat_Body"]
    body.data.materials.clear()
    body.data.materials.append(fur_mat)

    for obj in bpy.data.objects:
        if obj.name.startswith("Cat_Eye_"):
            obj.data.materials.clear()
            obj.data.materials.append(iris_mat)
        elif obj.name.startswith("Cat_Pupil_"):
            obj.data.materials.clear()
            obj.data.materials.append(pupil_mat)
        elif obj.name.startswith("Cat_Cornea_"):
            obj.data.materials.clear()
            obj.data.materials.append(cornea_mat)

    bpy.data.objects["Cat_Nose"].data.materials.clear()
    bpy.data.objects["Cat_Nose"].data.materials.append(nose_mat)
    bpy.data.objects["Cozy_Cushion"].data.materials.clear()
    bpy.data.objects["Cozy_Cushion"].data.materials.append(cush_mat)


def apply_all_textures():
    ensure_tex_dir()
    body = bpy.data.objects["Cat_Body"]
    pos_arr, norm_arr = bake_pos_and_normal_maps(body, size=2048)
    img_alb, img_nrm, img_rgh, _ = generate_cat_coat_textures(pos_arr, norm_arr)
    img_iris = generate_iris_texture(1024)
    img_ca, img_cn, img_nn = generate_cushion_and_nose_textures()
    build_pbr_materials(img_alb, img_nrm, img_rgh, img_iris, img_ca, img_cn, img_nn)
    print("Applied all 2K/1K PBR textures!")


if __name__ == "__main__":
    apply_all_textures()
