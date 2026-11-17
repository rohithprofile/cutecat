import math
import bpy
import bmesh
from mathutils import Vector, Euler

# ==============================================================================
# REALISTIC CUTE CAT BUILDER v4 (Broad Triangular Cat Ears, Plush Arms & Jaw)
# Coordinate frame: Front faces -Y, Up is +Z, Left is +X, Right is -X.
# Cushion center pad sits at Z = 0.0. Seated cat height ~ 0.37m.
# ==============================================================================

EYE_POS_R = Vector((-0.0225, -0.0815, 0.2922))
EYE_RADIUS = 0.0172
NOSE_POS = Vector((0.0, -0.1045, 0.2725))


def clear_scene():
    if bpy.context.mode != 'OBJECT':
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except Exception:
            pass
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for col in (
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.lights,
        bpy.data.cameras,
        bpy.data.images,
        bpy.data.armatures,
        bpy.data.actions,
        bpy.data.curves,
    ):
        for item in list(col):
            if item.users == 0:
                col.remove(item)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0


def apply_modifier(obj, mod_name):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
        bpy.ops.object.modifier_apply(modifier=mod_name)


def smoothstep(edge0, edge1, x):
    if edge1 == edge0:
        return 0.0
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def gauss(x, mu, sigma):
    d = (x - mu) / sigma
    return math.exp(-0.5 * d * d)


def eval_spine_profile(t):
    pts = [
        (0.00,  0.095, 0.024),  # Rump resting solidly on cushion
        (0.08,  0.080, 0.050),  # Pelvis
        (0.18,  0.056, 0.102),  # Lumbar
        (0.28,  0.024, 0.156),  # Ribcage
        (0.38, -0.014, 0.204),  # Chest / shoulders
        (0.46, -0.024, 0.244),  # Neck
        (0.54, -0.027, 0.274),  # Smooth occiput / jaw
        (0.64, -0.035, 0.292),  # Cranium mid
        (0.75, -0.052, 0.292),  # Brow / forehead
        (0.85, -0.074, 0.283),  # Eye plane
        (0.93, -0.093, 0.273),  # Whisker pad muzzle
        (1.00, -0.104, 0.268),  # Nose tip / chin
    ]

    def sample_yz(tv):
        for k in range(len(pts) - 1):
            t0, y0, z0 = pts[k]
            t1, y1, z1 = pts[k + 1]
            if tv <= t1 or k == len(pts) - 2:
                u = (tv - t0) / max(1e-6, (t1 - t0))
                ym0, zm0 = pts[max(0, k - 1)][1], pts[max(0, k - 1)][2]
                ym1, zm1 = pts[min(len(pts) - 1, k + 2)][1], pts[min(len(pts) - 1, k + 2)][2]
                dt_prev = max(1e-4, pts[k + 1][0] - pts[max(0, k - 1)][0])
                dt_next = max(1e-4, pts[min(len(pts) - 1, k + 2)][0] - pts[k][0])
                dt = max(1e-4, t1 - t0)
                vy0 = (y1 - ym0) / dt_prev * dt if k > 0 else (y1 - y0)
                vz0 = (z1 - zm0) / dt_prev * dt if k > 0 else (z1 - z0)
                vy1 = (ym1 - y0) / dt_next * dt if k < len(pts) - 2 else (y1 - y0)
                vz1 = (zm1 - z0) / dt_next * dt if k < len(pts) - 2 else (z1 - z0)
                u2 = u * u
                u3 = u2 * u
                return (
                    (2 * u3 - 3 * u2 + 1) * y0 + (u3 - 2 * u2 + u) * vy0 + (-2 * u3 + 3 * u2) * y1 + (u3 - u2) * vy1,
                    (2 * u3 - 3 * u2 + 1) * z0 + (u3 - 2 * u2 + u) * vz0 + (-2 * u3 + 3 * u2) * z1 + (u3 - u2) * vz1,
                )
        return pts[-1][1], pts[-1][2]

    cy, cz = sample_yz(t)
    eps = 0.002
    cy2, cz2 = sample_yz(min(1.0, t + eps))
    cy1, cz1 = sample_yz(max(0.0, t - eps))
    tang = Vector((0.0, cy2 - cy1, cz2 - cz1)).normalized()
    dorsal = Vector((0.0, tang.z, -tang.y)).normalized()

    shape_table = [
        # (t,    rx,     r_dors, r_vent)
        (0.00,  0.015,  0.016,  0.016),
        (0.05,  0.064,  0.050,  0.044),
        (0.14,  0.080,  0.060,  0.064),  # Plush haunches
        (0.24,  0.069,  0.055,  0.066),  # Belly & back
        (0.34,  0.062,  0.049,  0.062),  # Broad chest ruff
        (0.42,  0.052,  0.044,  0.048),  # Shoulders
        (0.49,  0.045,  0.041,  0.034),  # Neck inner bend: rv < bend radius -> ZERO self-intersection!
        (0.56,  0.048,  0.046,  0.034),  # Smooth throat curve
        (0.65,  0.055,  0.051,  0.042),  # Round cranium dome
        (0.75,  0.056,  0.048,  0.044),  # Apple cheeks
        (0.84,  0.047,  0.039,  0.037),  # Orbital / cheek taper
        (0.92,  0.032,  0.023,  0.028),  # Whisker pad muzzle
        (0.97,  0.019,  0.014,  0.018),  # Nose bridge & chin
        (1.00,  0.005,  0.005,  0.005),
    ]

    def sample_radii(tv):
        for k in range(len(shape_table) - 1):
            t0, x0, d0, v0 = shape_table[k]
            t1, x1, d1, v1 = shape_table[k + 1]
            if tv <= t1 or k == len(shape_table) - 2:
                u = smoothstep(t0, t1, tv)
                return (
                    x0 + (x1 - x0) * u,
                    d0 + (d1 - d0) * u,
                    v0 + (v1 - v0) * u,
                )
        return shape_table[-1][1:]

    rx_s, rd_s, rv_s = sample_radii(t)
    return Vector((0.0, cy, cz)), tang, dorsal, rx_s, rd_s, rv_s


def get_grid_patch_faces(face_grid, ri_start, ri_end, ui_start, ui_end):
    faces = []
    for ri in range(ri_start, ri_end):
        for ui in range(ui_start, ui_end):
            f = face_grid[ri][ui]
            if f.is_valid:
                faces.append(f)
    return faces


def find_nearest_patch(ring_verts, target_pos, ri_min, ri_max, ui_min, ui_max, r_span=2, u_span=2):
    best = None
    best_d = 1e9
    for ri in range(ri_min, ri_max - r_span + 1):
        for ui in range(ui_min, ui_max - u_span + 1):
            pts = [
                ring_verts[ri + dr][ui + du].co
                for dr in range(r_span + 1)
                for du in range(u_span + 1)
            ]
            c = sum(pts, Vector()) / len(pts)
            d = (c - target_pos).length
            if d < best_d:
                best_d = d
                best = (ri, ri + r_span, ui, ui + u_span)
    return best


def extrude_smooth_tube(bm, faces, steps, shape_fn=None, inset_thickness=0.0018, skip_inset=False):
    if not skip_inset:
        bmesh.ops.inset_region(bm, faces=faces, thickness=inset_thickness, depth=0.0, use_boundary=False)
    cur_faces = [f for f in faces if f.is_valid]

    for step_idx, st in enumerate(steps):
        ext = bmesh.ops.extrude_face_region(bm, geom=cur_faces)
        new_verts = [e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)]
        new_faces = [e for e in ext['geom'] if isinstance(e, bmesh.types.BMFace)]

        face_set = set(new_faces)
        boundary_verts = set()
        for f in new_faces:
            for e in f.edges:
                if sum(1 for lf in e.link_faces if lf in face_set) == 1:
                    boundary_verts.add(e.verts[0])
                    boundary_verts.add(e.verts[1])

        center = st["center"]
        u_ax = st["u_ax"].normalized()
        v_ax = st["v_ax"].normalized()
        v_ax = (v_ax - u_ax * v_ax.dot(u_ax)).normalized()
        rx = st["rx"]
        ry = st["ry"]
        blend = st.get("blend", 1.0)

        cur_c = sum((v.co for v in new_verts), Vector()) / len(new_verts)
        out_dir = u_ax.cross(v_ax).normalized()
        for v in new_verts:
            rel = v.co - cur_c
            pu = rel.dot(u_ax)
            pv = rel.dot(v_ax)
            ang = math.atan2(pv, pu)
            if v in boundary_verts:
                mod = shape_fn(ang, step_idx, True) if shape_fn else (1.0, 1.0, 0.0)
                target = center + u_ax * (math.cos(ang) * rx * mod[0]) + v_ax * (math.sin(ang) * ry * mod[1]) + out_dir * mod[2]
            else:
                r_frac = min(0.45, math.hypot(pu, pv) / max(1e-5, max(rx, ry)) * 0.45)
                mod = shape_fn(ang, step_idx, False) if shape_fn else (r_frac, r_frac, 0.0)
                target = center + u_ax * (math.cos(ang) * rx * mod[0]) + v_ax * (math.sin(ang) * ry * mod[1]) + out_dir * mod[2]
            nat = v.co + st.get("offset", Vector((0.0, 0.0, 0.0)))
            v.co = nat.lerp(target, blend)

            if st.get("floor_clamp") is not None and v.co.z < st["floor_clamp"]:
                v.co.z = st["floor_clamp"]

        # Remove the previous internal cap faces so the tube stays 100% hollow & manifold!
        old_caps = [f for f in cur_faces if f.is_valid]
        if old_caps:
            bmesh.ops.delete(bm, geom=old_caps, context='FACES')
        cur_faces = new_faces
    return cur_faces


def build_cat_base_mesh():
    bm = bmesh.new()

    t_vals = [
        0.00, 0.03, 0.065, 0.105, 0.145, 0.185, 0.23, 0.275, 0.32, 0.365,
        0.41, 0.455, 0.495, 0.535, 0.575, 0.615, 0.655, 0.695, 0.735, 0.77,
        0.805, 0.838, 0.87, 0.90, 0.93, 0.958, 0.98, 1.00
    ]
    nu = 20

    ring_verts = []
    for ri, t in enumerate(t_vals):
        center, tang, dorsal, rx, rd, rv = eval_spine_profile(t)
        row = []
        for ui in range(nu + 1):
            phi = math.pi * (ui / nu)
            sx = -math.sin(phi)
            sz = math.cos(phi)
            r_vert = rd if sz >= 0 else rv
            p = center + Vector((sx * rx, 0.0, 0.0)) + dorsal * (sz * r_vert)

            if t < 0.20 and p.z < 0.002:
                p.z = 0.002 + 0.15 * (p.z - 0.002)

            # Plush folded haunch thighs + tucked hindpaws sculpted seamlessly into lower body!
            if 0.02 < t < 0.26 and 0.34 * math.pi < phi < 0.88 * math.pi:
                thigh_w = gauss(t, 0.135, 0.060) * gauss(phi, 0.60 * math.pi, 0.18 * math.pi)
                p.x -= 0.018 * thigh_w
                p.y -= 0.014 * thigh_w
                p.z -= 0.012 * thigh_w
                # Tucked rounded hindpaw peeking gently forward at bottom front of haunch!
                hp_w = gauss(t, 0.095, 0.036) * gauss(phi, 0.68 * math.pi, 0.12 * math.pi)
                p.y -= 0.036 * hp_w
                p.x += 0.008 * hp_w
                p.z -= 0.018 * hp_w
                if p.z < 0.002:
                    p.z = 0.002

            # Soft rounded chest bib fullness
            if 0.24 < t < 0.48 and phi > 0.58 * math.pi:
                chest_w = gauss(t, 0.35, 0.075) * smoothstep(0.58 * math.pi, math.pi, phi)
                p.y -= 0.012 * chest_w

            # Facial sculpting
            if t > 0.65:
                # Plush apple cheeks focused cleanly on front-lateral face (not behind neck!)
                cheek_w = gauss(t, 0.81, 0.055) * gauss(phi, 0.54 * math.pi, 0.20 * math.pi)
                p.x -= 0.0050 * cheek_w
                p.y -= 0.0040 * cheek_w
                p.z -= 0.0015 * cheek_w

                # Gentle orbital socket indentation (avoid pinching nose bridge!)
                d_eye = (p - EYE_POS_R).length
                if d_eye < 0.022 and p.y < -0.055 and p.x < -0.011:
                    w_soc = smoothstep(0.022, 0.010, d_eye)
                    p.y += 0.0036 * w_soc

                # Smooth wide feline nose bridge
                bridge_w = gauss(t, 0.88, 0.075) * gauss(phi, 0.0, 0.28 * math.pi)
                p.y -= 0.0035 * bridge_w
                p.z += 0.0018 * bridge_w

                # Cute puffy `:3` twin whisker pads
                pad_w = gauss(t, 0.925, 0.034) * gauss(phi, 0.45 * math.pi, 0.22 * math.pi)
                p.y -= 0.0085 * pad_w
                p.x -= 0.0048 * pad_w
                p.z -= 0.0025 * pad_w

                # Philtrum cleft
                if phi < 0.16 * math.pi and 0.93 < t < 0.985:
                    p.y += 0.0025 * gauss(t, 0.958, 0.015) * (1.0 - phi / (0.16 * math.pi))

                # Soft cute chin
                chin_w = gauss(t, 0.92, 0.04) * gauss(phi, math.pi, 0.22 * math.pi)
                p.z -= 0.0042 * chin_w
                p.y -= 0.0028 * chin_w

            if ui == 0 or ui == nu:
                p.x = 0.0

            row.append(bm.verts.new(p))
        ring_verts.append(row)

    bm.verts.ensure_lookup_table()
    face_grid = []
    for ri in range(len(ring_verts) - 1):
        r0 = ring_verts[ri]
        r1 = ring_verts[ri + 1]
        frow = []
        for ui in range(nu):
            frow.append(bm.faces.new((r0[ui], r0[ui + 1], r1[ui + 1], r1[ui])))
        face_grid.append(frow)

    v_rump = bm.verts.new(Vector((0.0, 0.098, 0.034)))
    for ui in range(nu):
        bm.faces.new((v_rump, ring_verts[0][ui + 1], ring_verts[0][ui]))

    v_nose = bm.verts.new(Vector((0.0, -0.106, 0.270)))
    last_r = ring_verts[-1]
    for ui in range(nu):
        bm.faces.new((last_r[ui], last_r[ui + 1], v_nose))

    bm.faces.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    # ------------------------------------------------------------------
    # 1. REAL EYELID OPENINGS (Clean Symmetrical Almond Lids, Zero Pinch!)
    # ------------------------------------------------------------------
    eye_patch = find_nearest_patch(ring_verts, EYE_POS_R, 18, 25, 1, 9, r_span=2, u_span=2)
    eye_faces = get_grid_patch_faces(face_grid, *eye_patch)
    bmesh.ops.inset_region(bm, faces=eye_faces, thickness=0.0018, depth=0.0002, use_boundary=False)
    eye_faces = [f for f in eye_faces if f.is_valid]
    fset_eye = set(eye_faces)
    lid_rim_verts = set()
    for f in eye_faces:
        for e in f.edges:
            if sum(1 for lf in e.link_faces if lf in fset_eye) == 1:
                lid_rim_verts.add(e.verts[0])
                lid_rim_verts.add(e.verts[1])
    bmesh.ops.delete(bm, geom=eye_faces, context='FACES')

    eye_gaze = Vector((-0.14, -0.988, 0.04)).normalized()
    eye_up = Vector((0.0, 0.04, 0.999)).normalized()
    eye_right = eye_up.cross(eye_gaze).normalized()
    eye_center = EYE_POS_R + Vector((-0.004, 0.004, 0.004)) - eye_gaze * 0.0095

    for v in lid_rim_verts:
        if not v.is_valid:
            continue
        rel = v.co - eye_center
        ang = math.atan2(rel.dot(eye_up), rel.dot(eye_right))
        lx = math.cos(ang) * 0.0138
        lz = math.sin(ang) * 0.0118 + 0.0010 * math.cos(ang)
        r_orb = 0.0176
        ly = math.sqrt(max(0.00001, r_orb * r_orb - lx * lx - lz * lz))
        v.co = eye_center + eye_right * lx + eye_up * lz + eye_gaze * ly

    outer_ring = {e.other_vert(v) for v in lid_rim_verts for e in v.link_edges if e.other_vert(v) not in lid_rim_verts}
    for v in outer_ring:
        rel = v.co - eye_center
        if rel.length < 0.0190:
            v.co = eye_center + rel.normalized() * 0.0192

    lid_edges = [
        e for e in bm.edges
        if e.verts[0] in lid_rim_verts and e.verts[1] in lid_rim_verts and len(e.link_faces) == 1
    ]
    if lid_edges:
        ext_lid = bmesh.ops.extrude_edge_only(bm, edges=lid_edges)
        in_verts = [e for e in ext_lid['geom'] if isinstance(e, bmesh.types.BMVert)]
        for v in in_verts:
            v.co += eye_gaze * (-0.0020)
            rel = v.co - eye_center
            if rel.length < 0.0166:
                v.co = eye_center + rel.normalized() * 0.0166

    # ------------------------------------------------------------------
    # 2. BROAD TRIANGULAR CUTE CAT EARS (Wide Base, Soft Triangle!)
    # ------------------------------------------------------------------
    ear_target = Vector((-0.033, -0.038, 0.324))
    ear_patch = find_nearest_patch(ring_verts, ear_target, 13, 19, 2, 8, r_span=3, u_span=3)
    ear_faces = get_grid_patch_faces(face_grid, *ear_patch)
    ear_u = Vector((0.82, 0.0, 0.57)).normalized()
    ear_v = Vector((0.0, 1.0, 0.0)).normalized()

    ear_steps = [
        {"center": Vector((-0.037, -0.037, 0.330)), "u_ax": ear_u, "v_ax": ear_v, "rx": 0.0265, "ry": 0.0155, "blend": 0.35, "offset": Vector((-0.005, 0.0, 0.007))},
        {"center": Vector((-0.044, -0.038, 0.342)), "u_ax": ear_u, "v_ax": ear_v, "rx": 0.0215, "ry": 0.0115, "blend": 0.85, "offset": Vector((-0.005, 0.0, 0.009))},
        {"center": Vector((-0.051, -0.039, 0.352)), "u_ax": ear_u, "v_ax": ear_v, "rx": 0.0148, "ry": 0.0080, "blend": 1.0},
        {"center": Vector((-0.056, -0.040, 0.360)), "u_ax": ear_u, "v_ax": ear_v, "rx": 0.0085, "ry": 0.0050, "blend": 1.0},
        {"center": Vector((-0.059, -0.041, 0.365)), "u_ax": ear_u, "v_ax": ear_v, "rx": 0.0038, "ry": 0.0028, "blend": 1.0},
    ]
    extrude_smooth_tube(bm, ear_faces, ear_steps, skip_inset=True)

    # Carve soft concave inner ear bowl on front face
    bm.verts.ensure_lookup_table()
    for v in bm.verts:
        if v.co.x < -0.025 and v.co.z > 0.328 and v.co.y < -0.036:
            d_ear = math.hypot((v.co.x + 0.043) * 0.85, v.co.z - 0.348)
            if d_ear < 0.022:
                v.co.y += 0.0068 * smoothstep(0.022, 0.002, d_ear)

    # ------------------------------------------------------------------
    # 3. PLUSH MUSCULAR FORELEGS + CLOSE TOGETHER PLUMP 4-TOED PAWS
    # ------------------------------------------------------------------
    fore_target = Vector((-0.034, -0.034, 0.168))
    fore_patch = find_nearest_patch(ring_verts, fore_target, 6, 11, 11, 17, r_span=2, u_span=2)
    fore_faces = get_grid_patch_faces(face_grid, *fore_patch)
    leg_u = Vector((1.0, 0.0, 0.0))
    leg_v = Vector((0.0, -1.0, 0.0))

    def paw_shape(ang, step_idx, is_bound):
        sc = 1.0 if is_bound else 0.35
        if step_idx >= 5 and math.sin(ang) > 0.15:
            lobe = 0.94 + 0.14 * abs(math.cos(2.5 * ang))
            return sc * lobe, sc * (lobe * 1.08), 0.0
        return sc, sc, 0.0

    fore_steps = [
        {"center": Vector((-0.034, -0.034, 0.145)), "u_ax": leg_u, "v_ax": leg_v, "rx": 0.0260, "ry": 0.0280},
        {"center": Vector((-0.032, -0.029, 0.112)), "u_ax": leg_u, "v_ax": leg_v, "rx": 0.0235, "ry": 0.0250},
        {"center": Vector((-0.029, -0.034, 0.075)), "u_ax": leg_u, "v_ax": leg_v, "rx": 0.0210, "ry": 0.0220},
        {"center": Vector((-0.027, -0.044, 0.042)), "u_ax": leg_u, "v_ax": leg_v, "rx": 0.0195, "ry": 0.0205},
        {"center": Vector((-0.026, -0.055, 0.021)), "u_ax": leg_u, "v_ax": leg_v, "rx": 0.0210, "ry": 0.0235, "floor_clamp": 0.001},
        {"center": Vector((-0.026, -0.066, 0.011)), "u_ax": leg_u, "v_ax": leg_v, "rx": 0.0230, "ry": 0.0270, "floor_clamp": 0.001},
        {"center": Vector((-0.026, -0.068, 0.001)), "u_ax": leg_u, "v_ax": leg_v, "rx": 0.0210, "ry": 0.0255, "floor_clamp": 0.001},
    ]
    extrude_smooth_tube(bm, fore_faces, fore_steps, shape_fn=paw_shape)

    # ------------------------------------------------------------------
    # MIRROR ACROSS X=0, THEN EXTRUDE SINGLE GUARANTEED-CONNECTED TAIL!
    # ------------------------------------------------------------------
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    mesh = bpy.data.meshes.new("Cat_Body_Mesh")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("Cat_Body", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj

    mir = obj.modifiers.new("Mirror", 'MIRROR')
    mir.use_axis[0] = True
    mir.use_clip = True
    mir.merge_threshold = 0.0006
    apply_modifier(obj, "Mirror")

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    # Select ONE exact 2x2 connected quad patch from the single centerline rump vertex!
    rump_target = Vector((0.0, 0.095, 0.036))
    center_candidates = [v for v in bm.verts if abs(v.co.x) < 0.0015 and v.co.y > 0.075 and 0.022 < v.co.z < 0.056]
    v_tail_root = min(center_candidates, key=lambda v: (v.co - rump_target).length)
    tail_faces = [f for f in v_tail_root.link_faces if f.is_valid]

    if tail_faces:
        tail_spline = [
            (Vector((0.012,  0.114, 0.028)), 0.0195),
            (Vector((0.044,  0.122, 0.022)), 0.0205),
            (Vector((0.080,  0.106, 0.019)), 0.0205),
            (Vector((0.108,  0.074, 0.018)), 0.0200),
            (Vector((0.122,  0.032, 0.020)), 0.0195),
            (Vector((0.124, -0.010, 0.026)), 0.0185),
            (Vector((0.115, -0.044, 0.040)), 0.0160),
            (Vector((0.102, -0.058, 0.054)), 0.0120),
            (Vector((0.096, -0.062, 0.060)), 0.0060),
        ]
        prev_pt = Vector((0.0, 0.095, 0.035))
        # Parallel transport frame so tail NEVER twists along 180-deg curve!
        prev_u = Vector((1.0, 0.0, 0.0))
        tail_steps = []
        for pt, rad in tail_spline:
            ax = (pt - prev_pt).normalized()
            u_ax = (prev_u - ax * prev_u.dot(ax)).normalized()
            v_ax = ax.cross(u_ax).normalized()
            prev_u = u_ax
            tail_steps.append({
                "center": pt, "u_ax": u_ax, "v_ax": v_ax,
                "rx": rad, "ry": rad, "floor_clamp": 0.002,
            })
            prev_pt = pt
        extrude_smooth_tube(bm, tail_faces, tail_steps)

    # Gentle cute `:3` mouth slit indentation
    bm.verts.ensure_lookup_table()
    for v in bm.verts:
        if abs(v.co.x) < 0.016 and v.co.y < -0.090 and 0.252 < v.co.z < 0.264:
            w_m = gauss(v.co.z, 0.258, 0.0028) * smoothstep(0.016, 0.004, abs(v.co.x))
            v.co.y += 0.0055 * w_m

    # Targeted Laplacian relaxation on rear jaw, ear base, and shoulder-chest crease
    for _pass in range(8):
        deltas = {}
        for v in bm.verts:
            in_jaw = (v.co.y > -0.052 and v.co.y < 0.015 and 0.232 < v.co.z < 0.280)
            in_ear = (abs(v.co.x) > 0.024 and v.co.z > 0.324)
            in_shd = (0.006 < abs(v.co.x) < 0.040 and -0.062 < v.co.y < -0.018 and 0.125 < v.co.z < 0.215)
            if (in_jaw or in_ear or in_shd) and abs(v.co.x) > 0.001 and len(v.link_edges) > 0:
                avg = sum((e.other_vert(v).co for e in v.link_edges), Vector()) / len(v.link_edges)
                deltas[v] = (avg - v.co) * 0.42
        for v, d in deltas.items():
            v.co += d

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(obj.data)
    bm.free()

    sm = obj.modifiers.new("Smooth", 'SMOOTH')
    sm.factor = 0.22
    sm.iterations = 2
    apply_modifier(obj, "Smooth")

    # Apply Subsurf level 2 cleanly so UVs, vertex weights, and shape keys match final mesh!
    sub = obj.modifiers.new("Subsurf", 'SUBSURF')
    sub.levels = 2
    sub.render_levels = 2
    apply_modifier(obj, "Subsurf")

    for f in obj.data.polygons:
        f.use_smooth = True

    return obj


def assign_polar_eye_uvs(mesh, radius):
    """Assign exact polar UVs where V=1.0 is front gaze (-Y) and U wraps around (X, Z)."""
    uv_layer = mesh.uv_layers.new(name="UVMap")
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            co = mesh.vertices[mesh.loops[li].vertex_index].co
            ny = max(-1.0, min(1.0, -co.y / max(1e-6, radius)))
            theta = math.acos(ny)
            phi = math.atan2(co.z, co.x)
            u = (phi / (2.0 * math.pi)) % 1.0
            v = 1.0 - (theta / math.pi)
            uv_layer.data[li].uv = (u, v)


def get_eyelid_centers(body):
    """Measure final Right & Left eyelid rim centers directly from Cat_Body after smoothing/Subsurf."""
    bm = bmesh.new()
    bm.from_mesh(body.data)
    centers = {}
    for side, cond in (("R", lambda x: x < 0), ("L", lambda x: x > 0)):
        rim_vs = [v.co for e in bm.edges if len(e.link_faces) == 1 for v in e.verts if cond(v.co.x)]
        c = sum(rim_vs, Vector()) / len(rim_vs)
        centers[side] = c
    bm.free()
    return centers


def build_eyes(body=None):
    """
    Build 3-layer Eyes centered dynamically behind the measured final eyelid rim centers!
    """
    eye_objs = []
    from mathutils import Matrix
    rim_centers = get_eyelid_centers(body) if body is not None else {
        "R": Vector((-0.0315, -0.0846, 0.3020)),
        "L": Vector(( 0.0315, -0.0846, 0.3020)),
    }
    for side, sign in (("R", -1.0), ("L", 1.0)):
        rim_c = rim_centers[side]
        # Gaze slightly forward-outward from rim center so iris+pupil align symmetrically in front view!
        gaze_dir = Vector((sign * 0.14, -0.988, 0.04)).normalized()
        # Keep eyeball strictly smaller than orbital socket rim (r_eye = 0.0156 < r_orb = 0.0176) so ZERO upper/lower clipping!
        r_eye = 0.0156
        pos = rim_c - gaze_dir * 0.0095
        eye_rot = gaze_dir.to_track_quat('-Y', 'Z').to_euler()

        # 1. Eyeball + Iris baked into world coordinates (origin=(0,0,0) for clean Armature binding!)
        mat_world = Matrix.Translation(pos) @ eye_rot.to_matrix().to_4x4()
        bm_eye = bmesh.new()
        bmesh.ops.create_uvsphere(bm_eye, u_segments=40, v_segments=28, radius=r_eye)
        bmesh.ops.recalc_face_normals(bm_eye, faces=bm_eye.faces[:])
        emesh = bpy.data.meshes.new(f"Cat_Eye_{side}_Mesh")
        bm_eye.to_mesh(emesh)
        bm_eye.free()
        assign_polar_eye_uvs(emesh, r_eye)
        emesh.transform(mat_world)
        eye = bpy.data.objects.new(f"Cat_Eye_{side}", emesh)
        eye["eye_center"] = list(pos)
        bpy.context.collection.objects.link(eye)
        for p in eye.data.polygons:
            p.use_smooth = True

        # 2. Curved 2-ring Dynamic Pupil baked into world coordinates (with morph targets!)
        bm = bmesh.new()
        n_seg = 48
        r_pup = r_eye + 0.00068
        center_v = bm.verts.new(Vector((0.0, -r_pup, 0.0)))

        def make_pupil_ring(rx_p, rz_p, frac):
            verts = []
            for i in range(n_seg):
                a = 2.0 * math.pi * i / n_seg
                px = math.cos(a) * rx_p * frac
                pz = math.sin(a) * rz_p * frac
                py = -math.sqrt(max(0.00001, r_pup * r_pup - px * px - pz * pz))
                verts.append(bm.verts.new(Vector((px, py, pz))))
            return verts

        ring_in = make_pupil_ring(0.0046, 0.0094, 0.55)
        ring_out = make_pupil_ring(0.0046, 0.0094, 1.00)
        for i in range(n_seg):
            i2 = (i + 1) % n_seg
            bm.faces.new((center_v, ring_in[i], ring_in[i2]))
            bm.faces.new((ring_in[i], ring_out[i], ring_out[i2], ring_in[i2]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        pmesh = bpy.data.meshes.new(f"Cat_Pupil_{side}_Mesh")
        bm.to_mesh(pmesh)
        bm.free()
        pmesh.transform(mat_world)

        pupil = bpy.data.objects.new(f"Cat_Pupil_{side}", pmesh)
        bpy.context.collection.objects.link(pupil)
        for p in pupil.data.polygons:
            p.use_smooth = True

        pupil.shape_key_add(name="Basis")
        sk_dil = pupil.shape_key_add(name="Pupil_Dilate")
        sk_slit = pupil.shape_key_add(name="Pupil_Slit")
        for r_idx, frac in ((0, 0.55), (1, 1.00)):
            offset = 1 + r_idx * n_seg
            for i in range(n_seg):
                vi = offset + i
                ang = 2.0 * math.pi * i / n_seg
                dx = math.cos(ang) * 0.0106 * frac
                dz = math.sin(ang) * 0.0110 * frac
                dy = -math.sqrt(max(0.00001, r_pup * r_pup - dx * dx - dz * dz))
                sk_dil.data[vi].co = mat_world @ Vector((dx, dy, dz))
                sx = math.cos(ang) * 0.0015 * frac
                sz = math.sin(ang) * 0.0098 * frac
                sy = -math.sqrt(max(0.00001, r_pup * r_pup - sx * sx - sz * sz))
                sk_slit.data[vi].co = mat_world @ Vector((sx, sy, sz))

        # 3. Wet Glossy Cornea Dome baked into world coordinates!
        bm_cor = bmesh.new()
        bmesh.ops.create_uvsphere(bm_cor, u_segments=36, v_segments=24, radius=r_eye + 0.0010)
        for v in bm_cor.verts:
            if v.co.y < 0:
                v.co.y *= 1.05
        bmesh.ops.recalc_face_normals(bm_cor, faces=bm_cor.faces[:])
        cmesh = bpy.data.meshes.new(f"Cat_Cornea_{side}_Mesh")
        bm_cor.to_mesh(cmesh)
        bm_cor.free()
        cmesh.transform(mat_world)
        cornea = bpy.data.objects.new(f"Cat_Cornea_{side}", cmesh)
        bpy.context.collection.objects.link(cornea)
        for p in cornea.data.polygons:
            p.use_smooth = True

        eye_objs.extend([eye, pupil, cornea])
    return eye_objs


def build_nose():
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=3, radius=0.0086, calc_uvs=True)
    for v in bm.verts:
        x, y, z = v.co.x, v.co.y, v.co.z
        taper = 0.65 + 0.55 * smoothstep(-0.0086, 0.0086, z)
        nx = x * 1.15 * taper
        nz = z * 0.72
        ny = y * 0.65
        if 0.0025 < abs(nx) < 0.0075 and -0.0045 < nz < 0.001 and ny < 0:
            ny += 0.0018 * gauss(abs(nx), 0.0048, 0.0015) * gauss(nz, -0.0015, 0.0015)
        if abs(nx) < 0.002 and nz < 0.001 and ny < 0:
            ny += 0.0008 * (1.0 - abs(nx) / 0.002)
        v.co = Vector((nx, ny, nz)) + NOSE_POS

    mesh = bpy.data.meshes.new("Cat_Nose_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    uv_n = mesh.uv_layers.new(name="UVMap")
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            co = mesh.vertices[mesh.loops[li].vertex_index].co - NOSE_POS
            uv_n.data[li].uv = (co.x * 45.0 + 0.5, co.z * 45.0 + 0.5)
    nose = bpy.data.objects.new("Cat_Nose", mesh)
    bpy.context.collection.objects.link(nose)
    for p in nose.data.polygons:
        p.use_smooth = True
    return nose


def build_whiskers():
    bm = bmesh.new()

    def add_whisker(p0, p1, p2, r0=0.00026, r1=0.00004, steps=12, sides=5):
        rings = []
        for si in range(steps + 1):
            t = si / steps
            pt = ((1 - t) ** 2) * p0 + 2 * (1 - t) * t * p1 + (t ** 2) * p2
            tang = (2 * (1 - t) * (p1 - p0) + 2 * t * (p2 - p1)).normalized()
            ref = Vector((0, 0, 1)) if abs(tang.z) < 0.9 else Vector((1, 0, 0))
            u_ax = tang.cross(ref).normalized()
            v_ax = u_ax.cross(tang).normalized()
            rad = r0 * (1.0 - t) + r1 * t
            rings.append([bm.verts.new(pt + u_ax * (math.cos(2 * math.pi * k / sides) * rad)
                                       + v_ax * (math.sin(2 * math.pi * k / sides) * rad))
                          for k in range(sides)])
        for si in range(steps):
            for k in range(sides):
                k2 = (k + 1) % sides
                bm.faces.new((rings[si][k], rings[si][k2], rings[si + 1][k2], rings[si + 1][k]))
        bm.faces.new(rings[-1])

    for sign in (-1.0, 1.0):
        rows = [
            (0.269, -0.099, 0.011, 4, -0.008,  0.008, 0.072),
            (0.265, -0.100, 0.013, 5, -0.015,  0.010, 0.082),
            (0.261, -0.098, 0.012, 4, -0.021,  0.006, 0.068),
        ]
        for rz, ry, rx, cnt, zdroop, ysw, length in rows:
            for i in range(cnt):
                frac = i / max(1, cnt - 1)
                p0 = Vector((sign * (rx + frac * 0.007), ry + frac * 0.005, rz - frac * 0.002))
                p1 = p0 + Vector((sign * length * 0.52, -0.006 + ysw * frac, 0.002 + zdroop * 0.35))
                p2 = p0 + Vector((sign * length, 0.008 + ysw * (0.5 + frac), zdroop - frac * 0.004))
                add_whisker(p0, p1, p2)

        for i in range(3):
            frac = i / 2.0
            p0 = Vector((sign * (0.018 + frac * 0.008), -0.082 + frac * 0.004, 0.312 - frac * 0.002))
            p1 = p0 + Vector((sign * 0.005, 0.008, 0.011))
            p2 = p0 + Vector((sign * 0.011, 0.021, 0.016 - frac * 0.003))
            add_whisker(p0, p1, p2, r0=0.00018, r1=0.00004)

    mesh = bpy.data.meshes.new("Cat_Whiskers_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    whiskers = bpy.data.objects.new("Cat_Whiskers", mesh)
    bpy.context.collection.objects.link(whiskers)
    for p in whiskers.data.polygons:
        p.use_smooth = True
    return whiskers


def build_collar_and_bell():
    # Snug, fitted around neck with smooth forward dip to bell!
    bpy.ops.mesh.primitive_torus_add(
        major_segments=48, minor_segments=16,
        major_radius=0.046, minor_radius=0.0044,
        location=(0.0, -0.031, 0.236),
        rotation=(math.radians(22.0), 0.0, 0.0)
    )
    collar = bpy.context.active_object
    collar.name = "Cat_Collar"
    collar.scale = (1.05, 1.07, 0.90)
    with bpy.context.temp_override(object=collar, active_object=collar, selected_objects=[collar]):
        bpy.ops.object.transform_apply(scale=True)
    for p in collar.data.polygons:
        p.use_smooth = True

    bell_pos = Vector((0.0, -0.081, 0.214))
    bpy.ops.mesh.primitive_uv_sphere_add(segments=28, ring_count=18, radius=0.0092, location=bell_pos)
    bell = bpy.context.active_object
    bell.name = "Cat_Bell"
    for p in bell.data.polygons:
        p.use_smooth = True

    bpy.ops.mesh.primitive_torus_add(
        major_segments=20, minor_segments=8,
        major_radius=0.0032, minor_radius=0.0009,
        location=(0.0, -0.080, 0.224),
        rotation=(0.0, math.radians(90.0), 0.0)
    )
    ring = bpy.context.active_object
    ring.name = "Cat_Bell_Ring"
    for p in ring.data.polygons:
        p.use_smooth = True

    return [collar, bell, ring]


def build_tongue():
    """Cute pink cat tongue tucked inside mouth (emerges during Meow / Blep!)."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
    for v in bm.verts:
        x = v.co.x * 0.0075
        y = v.co.y * 0.0110
        z = v.co.z * 0.0024
        # Slight upward spoon curve at tip
        if y < 0:
            z += 0.0014 * smoothstep(0.0, -0.011, y)
        v.co = Vector((x, y - 0.086, z + 0.257))
    mesh = bpy.data.meshes.new("Cat_Tongue_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    tongue = bpy.data.objects.new("Cat_Tongue", mesh)
    bpy.context.collection.objects.link(tongue)
    for p in tongue.data.polygons:
        p.use_smooth = True
    return tongue


def unwrap_cat_uvs(body):
    """Unwrap Cat_Body with Smart UV Project so zero UV islands overlap during 2K baking."""
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    with bpy.context.temp_override(object=body, active_object=body, selected_objects=[body]):
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.018)
        bpy.ops.object.mode_set(mode='OBJECT')


def build_toe_beans():
    bm = bmesh.new()
    for sign in (-1.0, 1.0):
        pad_centers = [
            (Vector((sign * 0.026, -0.062, 0.0035)), (0.0072, 0.0065, 0.0032)),
            (Vector((sign * 0.016, -0.078, 0.0032)), (0.0032, 0.0040, 0.0026)),
            (Vector((sign * 0.023, -0.081, 0.0032)), (0.0033, 0.0042, 0.0026)),
            (Vector((sign * 0.030, -0.080, 0.0032)), (0.0033, 0.0042, 0.0026)),
            (Vector((sign * 0.037, -0.076, 0.0032)), (0.0030, 0.0038, 0.0025)),
        ]
        for c, sc in pad_centers:
            ret = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
            for v in ret['verts']:
                v.co = Vector((v.co.x * sc[0], v.co.y * sc[1], v.co.z * sc[2])) + c

    mesh = bpy.data.meshes.new("Cat_ToeBeans_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    beans = bpy.data.objects.new("Cat_ToeBeans", mesh)
    bpy.context.collection.objects.link(beans)
    for p in beans.data.polygons:
        p.use_smooth = True
    return beans


def build_cozy_cushion():
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=1.0, calc_uvs=True)
    for v in bm.verts:
        x, y, z = v.co.x, v.co.y, v.co.z
        r = math.hypot(x, y)
        ang = math.atan2(y, x)
        rad_x = 0.250
        rad_y = 0.235
        bolster = 0.022 * gauss(r, 0.85, 0.14) if z > -0.2 else 0.0
        pleat = 0.0022 * math.cos(18.0 * ang) * smoothstep(0.45, 0.92, r)
        dent = -0.004 * smoothstep(0.50, 0.0, r) if z > 0 else 0.0
        z_shaped = math.copysign(abs(z) ** 0.55, z)
        pz = z_shaped * 0.032 - 0.028 + bolster + pleat + dent
        if pz < -0.060:
            pz = -0.060
        v.co = Vector((x * rad_x, y * rad_y + 0.025, pz))

    mesh = bpy.data.meshes.new("Cozy_Cushion_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    uv_c = mesh.uv_layers.new(name="UVMap")
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            co = mesh.vertices[mesh.loops[li].vertex_index].co
            uv_c.data[li].uv = (co.x * 2.0 + 0.5, co.y * 2.0 + 0.5)
    cushion = bpy.data.objects.new("Cozy_Cushion", mesh)
    bpy.context.collection.objects.link(cushion)
    for p in cushion.data.polygons:
        p.use_smooth = True
    return cushion


def setup_basic_lighting_and_camera():
    scene = bpy.context.scene

    def add_area(name, loc, target, energy, size, color):
        ld = bpy.data.lights.new(name, 'AREA')
        ld.energy = energy
        ld.size = size
        ld.color = color
        lo = bpy.data.objects.new(name, ld)
        lo.location = loc
        direction = (Vector(target) - Vector(loc)).normalized()
        lo.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
        bpy.context.collection.objects.link(lo)
        return lo

    add_area("Key_Light", (-0.55, -0.82, 0.72), (0.0, -0.04, 0.22), 18.0, 1.05, (1.0, 0.94, 0.86))
    add_area("Fill_Light", (0.70, -0.65, 0.45), (0.0, -0.04, 0.20), 10.0, 1.15, (0.88, 0.93, 1.0))
    add_area("Bounce_Light", (0.05, -0.75, 0.08), (0.0, -0.04, 0.16), 3.5, 0.95, (1.0, 0.92, 0.85))
    add_area("Rim_Light", (0.25, 0.75, 0.65), (0.0, -0.02, 0.26), 18.0, 0.65, (1.0, 0.88, 0.72))

    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = 55.0
    cam_obj = bpy.data.objects.new("Camera", cam_data)
    cam_pos = Vector((-0.46, -0.82, 0.38))
    cam_target = Vector((0.0, -0.02, 0.18))
    cam_obj.location = cam_pos
    cam_obj.rotation_euler = (cam_target - cam_pos).normalized().to_track_quat('-Z', 'Y').to_euler()
    bpy.context.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    world = bpy.data.worlds.new("StudioWorld")
    scene.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs['Color'].default_value = (0.08, 0.075, 0.085, 1.0)
    bg.inputs['Strength'].default_value = 0.7


def assign_preview_materials(body, eyes, nose, whiskers, collar_parts, beans, cushion):
    def make_bsdf(name, color, rough=0.5, metallic=0.0, coat=0.0, trans=0.0):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        bsdf.inputs['Base Color'].default_value = (*color, 1.0)
        bsdf.inputs['Roughness'].default_value = rough
        bsdf.inputs['Metallic'].default_value = metallic
        if 'Coat Weight' in bsdf.inputs:
            bsdf.inputs['Coat Weight'].default_value = coat
        if 'Transmission Weight' in bsdf.inputs:
            bsdf.inputs['Transmission Weight'].default_value = trans
        return mat

    fur_mat = make_bsdf("Cat_Fur_Preview", (0.85, 0.55, 0.32), rough=0.68)
    body.data.materials.append(fur_mat)
    nose.data.materials.append(make_bsdf("Cat_Nose_Mat", (0.85, 0.48, 0.48), rough=0.25, coat=0.45))
    whiskers.data.materials.append(make_bsdf("Cat_Whiskers_Mat", (0.96, 0.94, 0.91), rough=0.28))
    beans.data.materials.append(make_bsdf("Cat_Beans_Mat", (0.86, 0.52, 0.54), rough=0.45))
    cushion.data.materials.append(make_bsdf("Cushion_Mat", (0.24, 0.30, 0.28), rough=0.88))

    collar_parts[0].data.materials.append(make_bsdf("Collar_Mat", (0.16, 0.38, 0.30), rough=0.55))
    gold = make_bsdf("Bell_Gold", (0.95, 0.74, 0.28), rough=0.22, metallic=0.95)
    collar_parts[1].data.materials.append(gold)
    collar_parts[2].data.materials.append(gold)

    iris_mat = make_bsdf("Cat_Iris_Mat", (0.35, 0.62, 0.28), rough=0.35)
    pupil_mat = make_bsdf("Cat_Pupil_Mat", (0.01, 0.01, 0.01), rough=0.92)
    cornea_mat = make_bsdf("Cat_Cornea_Mat", (1.0, 1.0, 1.0), rough=0.015, coat=1.0, trans=0.96)
    for obj in eyes:
        if "Eye_" in obj.name:
            obj.data.materials.append(iris_mat)
        elif "Pupil_" in obj.name:
            obj.data.materials.append(pupil_mat)
        elif "Cornea_" in obj.name:
            obj.data.materials.append(cornea_mat)


def main():
    clear_scene()
    body = build_cat_base_mesh()
    unwrap_cat_uvs(body)
    eyes = build_eyes(body)
    nose = build_nose()
    tongue = build_tongue()
    whiskers = build_whiskers()
    collar_parts = build_collar_and_bell()
    beans = build_toe_beans()
    cushion = build_cozy_cushion()
    setup_basic_lighting_and_camera()
    assign_preview_materials(body, eyes, nose, whiskers, collar_parts, beans, cushion)
    tongue.data.materials.append(bpy.data.materials["Cat_Nose_Mat"])
    print(f"Built cat v4.2! Body verts={len(body.data.vertices)}, polys={len(body.data.polygons)}")


if __name__ == "__main__":
    main()
