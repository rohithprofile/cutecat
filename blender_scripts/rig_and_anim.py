import math
import os
import shutil
import bpy
import bmesh
from mathutils import Vector, Euler, Quaternion

OUT_DIR = r"C:\Users\Rohith\cute-cat-3d\public\models"
TEX_OUT_DIR = r"C:\Users\Rohith\cute-cat-3d\public\textures"
BLEND_PATH = r"C:\Users\Rohith\cute-cat-3d\cat_scene.blend"
GLB_PATH = os.path.join(OUT_DIR, "cat.glb")


def smoothstep(e0, e1, x):
    if e1 == e0:
        return 0.0
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def gauss(x, mu, s):
    d = (x - mu) / s
    return math.exp(-0.5 * d * d)


def build_armature():
    if "Cat_Rig" in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects["Cat_Rig"], do_unlink=True)

    eye_l_loc = Vector(bpy.data.objects["Cat_Eye_L"]["eye_center"])
    eye_r_loc = Vector(bpy.data.objects["Cat_Eye_R"]["eye_center"])

    arm_data = bpy.data.armatures.new("Cat_Rig_Data")
    arm_obj = bpy.data.objects.new("Cat_Rig", arm_data)
    bpy.context.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    arm_obj.show_in_front = True

    with bpy.context.temp_override(object=arm_obj, active_object=arm_obj):
        bpy.ops.object.mode_set(mode='EDIT')
        eb = arm_data.edit_bones

        def add_bone(name, head, tail, parent=None, connect=False, roll=0.0):
            b = eb.new(name)
            b.head = Vector(head)
            b.tail = Vector(tail)
            b.roll = roll
            if parent:
                b.parent = eb[parent]
                b.use_connect = connect
            return b

        add_bone("Root",        (0.0,  0.000, 0.000), (0.0,  0.000, 0.050))
        add_bone("Pelvis",      (0.0,  0.072, 0.045), (0.0,  0.056, 0.105), "Root")
        add_bone("Spine_Lower", (0.0,  0.056, 0.105), (0.0,  0.024, 0.158), "Pelvis", True)
        add_bone("Spine_Upper", (0.0,  0.024, 0.158), (0.0, -0.012, 0.205), "Spine_Lower", True)
        add_bone("Chest",       (0.0, -0.012, 0.205), (0.0, -0.024, 0.242), "Spine_Upper", True)
        add_bone("Neck",        (0.0, -0.024, 0.242), (0.0, -0.032, 0.278), "Chest", True)
        add_bone("Head",        (0.0, -0.032, 0.278), (0.0, -0.072, 0.308), "Neck", True)

        add_bone("Ear_L", ( 0.036, -0.037, 0.328), ( 0.058, -0.041, 0.365), "Head")
        add_bone("Ear_R", (-0.036, -0.037, 0.328), (-0.058, -0.041, 0.365), "Head")
        add_bone("Jaw",   ( 0.000, -0.052, 0.268), ( 0.000, -0.098, 0.256), "Head")

        # Eye bones placed at EXACT eyeball origins pointing straight forward -Y!
        add_bone("Eye_L", eye_l_loc, eye_l_loc + Vector((0.003, -0.024, 0.001)), "Head")
        add_bone("Eye_R", eye_r_loc, eye_r_loc + Vector((-0.003, -0.024, 0.001)), "Head")

        # Swinging Collar Bell
        add_bone("Collar_Bell", (0.0, -0.080, 0.228), (0.0, -0.081, 0.208), "Chest")

        # Forelegs (Left +X, Right -X)
        for side, s in (("L", 1.0), ("R", -1.0)):
            add_bone(f"Shoulder_{side}", (s * 0.026, -0.028, 0.195), (s * 0.034, -0.033, 0.145), "Chest")
            add_bone(f"UpperArm_{side}", (s * 0.034, -0.033, 0.145), (s * 0.030, -0.031, 0.082), f"Shoulder_{side}", True)
            add_bone(f"Forearm_{side}",  (s * 0.030, -0.031, 0.082), (s * 0.026, -0.050, 0.024), f"UpperArm_{side}", True)
            add_bone(f"Paw_{side}",      (s * 0.026, -0.050, 0.024), (s * 0.026, -0.074, 0.006), f"Forearm_{side}", True)

        # Articulated 7-bone Plush Tail
        tail_pts = [
            Vector((0.000,  0.095, 0.034)),
            Vector((0.022,  0.118, 0.025)),
            Vector((0.062,  0.116, 0.020)),
            Vector((0.098,  0.088, 0.018)),
            Vector((0.120,  0.044, 0.020)),
            Vector((0.124, -0.004, 0.026)),
            Vector((0.114, -0.040, 0.040)),
            Vector((0.096, -0.060, 0.058)),
        ]
        for idx in range(len(tail_pts) - 1):
            bname = f"Tail_0{idx+1}"
            pname = "Pelvis" if idx == 0 else f"Tail_0{idx}"
            add_bone(bname, tail_pts[idx], tail_pts[idx + 1], pname, connect=(idx > 0))

        bpy.ops.object.mode_set(mode='OBJECT')

    for pb in arm_obj.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    return arm_obj


def closest_point_on_segment(p, a, b):
    ab = b - a
    l2 = ab.length_squared
    if l2 < 1e-8:
        return a, 0.0
    t = max(0.0, min(1.0, (p - a).dot(ab) / l2))
    return a + ab * t, t


def weight_cat_body(body, arm_obj):
    body.vertex_groups.clear()
    bone_names = [b.name for b in arm_obj.data.bones]
    vgroups = {name: body.vertex_groups.new(name=name) for name in bone_names}

    # Grab tail segment bone heads/tails
    tail_segs = []
    for i in range(1, 8):
        b = arm_obj.data.bones[f"Tail_0{i}"]
        tail_segs.append((f"Tail_0{i}", b.head_local.copy(), b.tail_local.copy()))

    # Precompute foreleg bone segment endpoints for exact distance-based limb isolation!
    fore_segs = {}
    for side in ("L", "R"):
        fore_segs[side] = [
            (f"Shoulder_{side}", arm_obj.data.bones[f"Shoulder_{side}"].head_local.copy(), arm_obj.data.bones[f"Shoulder_{side}"].tail_local.copy()),
            (f"UpperArm_{side}", arm_obj.data.bones[f"UpperArm_{side}"].head_local.copy(), arm_obj.data.bones[f"UpperArm_{side}"].tail_local.copy()),
            (f"Forearm_{side}",  arm_obj.data.bones[f"Forearm_{side}"].head_local.copy(),  arm_obj.data.bones[f"Forearm_{side}"].tail_local.copy()),
            (f"Paw_{side}",      arm_obj.data.bones[f"Paw_{side}"].head_local.copy(),      arm_obj.data.bones[f"Paw_{side}"].tail_local.copy()),
        ]

    for v in body.data.vertices:
        co = v.co
        x, y, z = co.x, co.y, co.z
        ax = abs(x)
        weights = {}

        # Distance to closest foreleg segment on this side
        side_lr = "L" if x >= 0 else "R"
        best_leg_d = 1e9
        for _, a, b in fore_segs[side_lr]:
            cp, _ = closest_point_on_segment(co, a, b)
            d = (co - cp).length
            if d < best_leg_d:
                best_leg_d = d
        # Hindpaw sits around (x=+-0.062, y=-0.025, z=0.012); exclude it strictly from foreleg!
        d_hindpaw = (co - Vector(((1 if x >= 0 else -1) * 0.062, -0.020, 0.012))).length

        # 1. Check Tail region strictly outside left thigh (thigh max X = 0.092 for y in [-0.02, 0.06])
        d_tail_min = min((co - closest_point_on_segment(co, h, t)[0]).length for _, h, t in tail_segs)
        is_tail = (d_tail_min < 0.025) and (
            (y > 0.092 and z < 0.058 and x > -0.018)
            or (x > 0.095 and z < 0.066)
            or (y < -0.025 and z > 0.024 and x > 0.082)
        )
        if is_tail:
            best_i = 0
            best_d = 1e9
            for idx, (bn, h, t) in enumerate(tail_segs):
                cp, _ = closest_point_on_segment(co, h, t)
                d = (co - cp).length
                if d < best_d:
                    best_d = d
                    best_i = idx
            bn_cur = tail_segs[best_i][0]
            weights[bn_cur] = 0.72
            if best_i > 0:
                weights[tail_segs[best_i - 1][0]] = 0.14
            else:
                weights["Pelvis"] = 0.28
            if best_i < len(tail_segs) - 1:
                weights[tail_segs[best_i + 1][0]] = weights.get(tail_segs[best_i + 1][0], 0.0) + 0.14
            else:
                weights[bn_cur] += 0.14

        # 2. Check Forelegs (L / R) strictly by proximity to foreleg capsule (never grabbing hindpaw or belly!)
        elif z < 0.200 and y < -0.008 and ax > 0.005 and best_leg_d < 0.030 and best_leg_d < d_hindpaw - 0.003:
            w_leg = smoothstep(0.200, 0.138, z) * smoothstep(0.005, 0.016, ax) * smoothstep(-0.008, -0.024, y)
            if z > 0.140:
                weights[f"Shoulder_{side_lr}"] = w_leg
                weights["Chest"] = 1.0 - w_leg
            elif z > 0.082:
                u = smoothstep(0.140, 0.082, z)
                weights[f"UpperArm_{side_lr}"] = w_leg * (0.3 + 0.7 * u)
                weights[f"Shoulder_{side_lr}"] = w_leg * (0.7 * (1.0 - u))
                if w_leg < 0.99:
                    weights["Spine_Upper"] = 1.0 - w_leg
            elif z > 0.024:
                u = smoothstep(0.082, 0.024, z)
                weights[f"Forearm_{side_lr}"] = w_leg * (1.0 - u * 0.35)
                weights[f"Paw_{side_lr}"] = w_leg * (u * 0.35)
                if u < 0.25:
                    weights[f"UpperArm_{side_lr}"] = w_leg * (0.25 - u)
                if w_leg < 0.99:
                    weights["Spine_Lower"] = 1.0 - w_leg
            else:
                weights[f"Paw_{side_lr}"] = w_leg
                if w_leg < 0.99:
                    weights["Pelvis"] = 1.0 - w_leg

        # 3. Head, Ears & Jaw!
        elif z >= 0.242 or (y < -0.048 and z >= 0.232):
            w_neck = smoothstep(0.278, 0.242, z)
            w_head = 1.0 - w_neck
            # Ears
            if ax > 0.026 and z > 0.324:
                side = "L" if x > 0 else "R"
                w_ear = smoothstep(0.324, 0.344, z)
                weights[f"Ear_{side}"] = w_ear
                weights["Head"] = 1.0 - w_ear
            # Jaw (lower lip & chin under mouth crease)
            elif ax < 0.028 and y < -0.068 and z < 0.264:
                w_jaw = smoothstep(0.264, 0.252, z) * smoothstep(0.028, 0.012, ax) * 0.85
                weights["Jaw"] = w_jaw
                weights["Head"] = 1.0 - w_jaw
            else:
                if w_head > 0.001:
                    weights["Head"] = w_head
                if w_neck > 0.001:
                    weights["Neck"] = w_neck * 0.7
                    weights["Chest"] = w_neck * 0.3

        # 4. Torso Spine (Pelvis -> Spine_Lower -> Spine_Upper -> Chest)
        else:
            if z < 0.105:
                u = smoothstep(0.055, 0.105, z)
                weights["Pelvis"] = 1.0 - u * 0.45
                weights["Spine_Lower"] = u * 0.45
            elif z < 0.160:
                u = smoothstep(0.105, 0.160, z)
                weights["Spine_Lower"] = 1.0 - u
                weights["Spine_Upper"] = u
            elif z < 0.210:
                u = smoothstep(0.160, 0.210, z)
                weights["Spine_Upper"] = 1.0 - u
                weights["Chest"] = u
            else:
                u = smoothstep(0.210, 0.248, z)
                weights["Chest"] = 1.0 - u * 0.5
                weights["Neck"] = u * 0.5

        tot = sum(weights.values())
        if tot <= 1e-6:
            weights = {"Pelvis": 1.0}
            tot = 1.0
        for bname, w in weights.items():
            if w > 1e-4:
                vgroups[bname].add([v.index], w / tot, 'REPLACE')

    # Attach Armature modifier & parent body to Cat_Rig
    for m in list(body.modifiers):
        if m.type == 'ARMATURE':
            body.modifiers.remove(m)
    body.parent = arm_obj
    arm_mod = body.modifiers.new("Armature", 'ARMATURE')
    arm_mod.object = arm_obj


def bind_rigid_and_accessory_meshes(arm_obj):
    def attach_armature_weight(obj, weight_fn):
        obj.vertex_groups.clear()
        for b in arm_obj.data.bones:
            obj.vertex_groups.new(name=b.name)
        for v in obj.data.vertices:
            for bn, w in weight_fn(v.co).items():
                if w > 1e-4:
                    obj.vertex_groups[bn].add([v.index], w, 'REPLACE')
        for m in list(obj.modifiers):
            if m.type == 'ARMATURE':
                obj.modifiers.remove(m)
        obj.parent_type = 'OBJECT'
        obj.parent = arm_obj
        mod = obj.modifiers.new("Armature", 'ARMATURE')
        mod.object = arm_obj

    attach_armature_weight(bpy.data.objects["Cat_Nose"], lambda co: {"Head": 1.0})
    attach_armature_weight(bpy.data.objects["Cat_Whiskers"], lambda co: {"Head": 1.0})
    attach_armature_weight(bpy.data.objects["Cat_Tongue"], lambda co: {"Jaw": 0.85, "Head": 0.15})
    attach_armature_weight(bpy.data.objects["Cat_Collar"], lambda co: {"Chest": 0.65, "Neck": 0.35})
    attach_armature_weight(bpy.data.objects["Cat_Bell"], lambda co: {"Collar_Bell": 1.0})
    attach_armature_weight(bpy.data.objects["Cat_Bell_Ring"], lambda co: {"Collar_Bell": 1.0})
    attach_armature_weight(bpy.data.objects["Cat_ToeBeans"], lambda co: {"Paw_L": 1.0} if co.x > 0 else {"Paw_R": 1.0})

    # Bind Eye + Pupil + Cornea via Armature Modifier (1.0 Eye_L / Eye_R) — all baked at origin (0,0,0)!
    for side in ("L", "R"):
        bone_name = f"Eye_{side}"
        for prefix in ("Cat_Eye_", "Cat_Pupil_", "Cat_Cornea_"):
            obj = bpy.data.objects[f"{prefix}{side}"]
            attach_armature_weight(obj, lambda co, bn=bone_name: {bn: 1.0})


def build_facial_shape_keys(body):
    """Build smooth Blink_L, Blink_R, Happy_Squint, Meow_Open, Nose_Scrunch, Cheek_Puff, Breathe_Inhale + Tongue Blep."""
    if body.data.shape_keys:
        body.shape_key_clear()

    sk_basis = body.shape_key_add(name="Basis")
    sk_blink_l = body.shape_key_add(name="Blink_L")
    sk_blink_r = body.shape_key_add(name="Blink_R")
    sk_happy   = body.shape_key_add(name="Happy_Squint")
    sk_meow    = body.shape_key_add(name="Meow_Open")
    sk_scrunch = body.shape_key_add(name="Nose_Scrunch")
    sk_puff    = body.shape_key_add(name="Cheek_Puff")
    sk_breathe = body.shape_key_add(name="Breathe_Inhale")

    # Measure eyelid centers & orbital vertices
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    rim_by_side = {}
    eye_center_by_side = {}
    for side, cond in (("L", lambda x: x > 0), ("R", lambda x: x < 0)):
        rim_vs = {v.index for e in bm.edges if len(e.link_faces) == 1 for v in e.verts if cond(v.co.x)}
        rim_c = sum((bm.verts[i].co for i in rim_vs), Vector()) / max(1, len(rim_vs))
        rim_by_side[side] = rim_vs
        eye_center_by_side[side] = rim_c - Vector(((1 if side == "L" else -1) * 0.14, -0.988, 0.04)).normalized() * 0.0110
    bm.free()

    for idx, v in enumerate(body.data.vertices):
        co = v.co
        x, y, z = co.x, co.y, co.z
        ax = abs(x)

        # Blink_L & Blink_R: close upper & lower eyelids smoothly along eyeball curvature!
        for side, sk_blk in (("L", sk_blink_l), ("R", sk_blink_r)):
            if (side == "L" and x > 0.005) or (side == "R" and x < -0.005):
                ec = eye_center_by_side[side]
                d = (co - ec).length
                # Influence eyelid + soft surrounding lid skin within 2.5cm of eye center
                w_eye = smoothstep(0.0245, 0.0165, d)
                if w_eye > 0.001 and y < -0.068:
                    # Drop upper lid (z > ec.z + 0.001) down to meeting line z_meet; lift lower lid slightly
                    z_meet = ec.z + 0.0010
                    if z > z_meet:
                        dz = -(z - z_meet) * 0.90 * w_eye
                    else:
                        dz = (z_meet - z) * 0.22 * w_eye
                    new_co = Vector((x, y, z + dz))
                    # Project gently onto protective lid sphere outside eyeball (R = 0.0176)
                    rel = new_co - ec
                    if rel.length < 0.0176:
                        new_co = ec + rel.normalized() * 0.0176
                    sk_blk.data[idx].co = new_co

                    # Happy_Squint ^_^ (lifts lower lid into cute happy curve + raises cheeks!)
                    if z <= z_meet + 0.003:
                        hq_dz = (z_meet + 0.0045 - z) * 0.65 * w_eye
                    else:
                        hq_dz = -(z - z_meet - 0.003) * 0.50 * w_eye
                    hq_co = Vector((x, y, z + hq_dz))
                    rel_h = hq_co - ec
                    if rel_h.length < 0.0176:
                        hq_co = ec + rel_h.normalized() * 0.0176
                    sk_happy.data[idx].co = hq_co

        # Happy_Squint cheek smile lift
        if y < -0.055 and 0.260 < z < 0.292 and 0.014 < ax < 0.056:
            w_ch = gauss(z, 0.275, 0.010) * gauss(ax, 0.036, 0.016) * smoothstep(-0.055, -0.085, y)
            sk_happy.data[idx].co += Vector((0.0, -0.0018 * w_ch, 0.0028 * w_ch))

        # Meow_Open: opens mouth slit cleanly!
        if ax < 0.025 and y < -0.075 and 0.244 < z < 0.270:
            w_m = smoothstep(0.025, 0.005, ax) * smoothstep(-0.075, -0.095, y)
            if z < 0.260:
                sk_meow.data[idx].co += Vector((0.0, 0.0025 * w_m, -0.0068 * w_m * gauss(z, 0.254, 0.006)))
            else:
                sk_meow.data[idx].co += Vector((0.0, -0.0012 * w_m, 0.0018 * w_m * gauss(z, 0.264, 0.004)))

        # Nose_Scrunch: cute muzzle wrinkle when booped!
        if ax < 0.028 and y < -0.080 and 0.264 < z < 0.292:
            w_ns = smoothstep(0.028, 0.005, ax) * gauss(z, 0.276, 0.009) * smoothstep(-0.080, -0.102, y)
            sk_scrunch.data[idx].co += Vector((0.0, 0.0012 * w_ns, 0.0026 * w_ns))

        # Cheek_Puff: fluffy `:3` puff!
        if y < -0.045 and 0.256 < z < 0.292 and 0.012 < ax < 0.058:
            w_cp = gauss(z, 0.274, 0.012) * gauss(ax, 0.038, 0.015) * smoothstep(-0.045, -0.085, y)
            sk_puff.data[idx].co += Vector((math.copysign(0.0030 * w_cp, x), -0.0024 * w_cp, 0.0))

        # Breathe_Inhale: gentle ribcage & chest expansion
        if 0.085 < z < 0.225:
            w_br = gauss(z, 0.160, 0.045)
            n_dir = Vector((x, y, 0.0))
            if n_dir.length > 1e-4:
                n_dir.normalize()
                sk_breathe.data[idx].co += n_dir * (0.0028 * w_br)

    # Tongue Blep shape key!
    tongue = bpy.data.objects["Cat_Tongue"]
    if tongue.data.shape_keys:
        tongue.shape_key_clear()
    tongue.shape_key_add(name="Basis")
    sk_blep = tongue.shape_key_add(name="Blep")
    for idx, v in enumerate(tongue.data.vertices):
        # Slide tongue 11mm forward & 1mm up out between lips!
        sk_blep.data[idx].co = v.co + Vector((0.0, -0.0115, 0.0010))


def create_action_and_nla(arm_obj, body, tongue, pupil_l, pupil_r, name, keys_fn, frame_end):
    """
    Build one clean Animation Clip across Armature bones & Shape Keys,
    and push BOTH onto NLA tracks sharing `name` so glTF exports them unified!
    """
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = frame_end

    # Ensure animation_data on all animated datablocks
    for obj_or_sk in (arm_obj, body.data.shape_keys, tongue.data.shape_keys, pupil_l.data.shape_keys, pupil_r.data.shape_keys):
        if not obj_or_sk.animation_data:
            obj_or_sk.animation_data_create()

    arm_act = bpy.data.actions.new(f"{name}_Rig")
    arm_obj.animation_data.action = arm_act

    sk_acts = {}
    for tag, sk in (("body", body.data.shape_keys), ("tongue", tongue.data.shape_keys), ("pl", pupil_l.data.shape_keys), ("pr", pupil_r.data.shape_keys)):
        act = bpy.data.actions.new(f"{name}_{tag}")
        sk.animation_data.action = act
        sk_acts[tag] = act

    # Reset all pose bones & shape keys before authoring keys
    for pb in arm_obj.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
    for sk in (body.data.shape_keys, tongue.data.shape_keys, pupil_l.data.shape_keys, pupil_r.data.shape_keys):
        for kb in sk.key_blocks:
            kb.value = 0.0

    def set_rot(bname, deg_xyz, frame):
        pb = arm_obj.pose.bones[bname]
        pb.rotation_quaternion = Euler([math.radians(a) for a in deg_xyz], 'XYZ').to_quaternion()
        pb.keyframe_insert("rotation_quaternion", frame=frame)

    def set_sk(sk, key_name, val, frame):
        kb = sk.key_blocks[key_name]
        kb.value = val
        kb.keyframe_insert("value", frame=frame)

    keys_fn(set_rot, set_sk, body.data.shape_keys, tongue.data.shape_keys, pupil_l.data.shape_keys, pupil_r.data.shape_keys)

    # Set linear/smooth interpolation & push to matching NLA tracks
    for act in [arm_act] + list(sk_acts.values()):
        # Ensure Blender 5 layered/channelbag compatibility cleanly via fcurves if available
        fcs = getattr(act, "fcurves", None)
        if fcs:
            for fc in fcs:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'BEZIER'

    # Push Armature action -> NLA track named `name`
    trk = arm_obj.animation_data.nla_tracks.new()
    trk.name = name
    strip = trk.strips.new(name, 1, arm_act)
    strip.action_frame_start = 1
    strip.action_frame_end = frame_end
    arm_obj.animation_data.action = None

    # Push ShapeKey actions -> NLA tracks with SAME `name` so glTF merges them into one clip!
    for tag, sk in (("body", body.data.shape_keys), ("tongue", tongue.data.shape_keys), ("pl", pupil_l.data.shape_keys), ("pr", pupil_r.data.shape_keys)):
        act = sk_acts[tag]
        # Only push if keyframes were actually recorded!
        has_keys = bool(getattr(act, "fcurves", None) and len(act.fcurves) > 0) or (hasattr(act, "layers") and len(act.layers) > 0)
        if has_keys:
            t_sk = sk.animation_data.nla_tracks.new()
            t_sk.name = name
            s_sk = t_sk.strips.new(name, 1, act)
            s_sk.action_frame_start = 1
            s_sk.action_frame_end = frame_end
        sk.animation_data.action = None


def build_all_animations(arm_obj):
    body = bpy.data.objects["Cat_Body"]
    tongue = bpy.data.objects["Cat_Tongue"]
    pl = bpy.data.objects["Cat_Pupil_L"]
    pr = bpy.data.objects["Cat_Pupil_R"]

    # Clear existing NLA tracks
    for target in (arm_obj, body.data.shape_keys, tongue.data.shape_keys, pl.data.shape_keys, pr.data.shape_keys):
        if target.animation_data:
            for t in list(target.animation_data.nla_tracks):
                target.animation_data.nla_tracks.remove(t)
            target.animation_data.action = None

    # 1. Idle (120 frames = 5s loop: gentle breathing, lazy tail swish, blink, micro head drift)
    def anim_idle(set_rot, set_sk, b_sk, t_sk, pl_sk, pr_sk):
        for f in (1, 30, 60, 90, 120):
            phase = 2.0 * math.pi * (f - 1) / 119.0
            br = 0.5 - 0.5 * math.cos(phase * 2.0)
            set_sk(b_sk, "Breathe_Inhale", br * 0.85, f)
            set_rot("Spine_Upper", (br * 1.6, 0.0, 0.0), f)
            set_rot("Chest", (-br * 1.2, 0.0, 0.0), f)
            set_rot("Neck", (math.sin(phase) * 1.5, math.sin(phase * 0.5) * 1.2, math.cos(phase) * 2.0), f)
            set_rot("Head", (math.sin(phase + 0.5) * 2.2, math.cos(phase) * 2.5, math.sin(phase) * 3.0), f)
            set_rot("Ear_L", (math.sin(phase * 2.0) * 2.5, 0.0, 0.0), f)
            set_rot("Ear_R", (math.cos(phase * 2.0) * 2.5, 0.0, 0.0), f)
            for ti in range(1, 8):
                sway = math.sin(phase + ti * 0.55) * (2.5 + ti * 1.2)
                curl = math.cos(phase + ti * 0.45) * (1.5 + ti * 0.8)
                set_rot(f"Tail_0{ti}", (curl, 0.0, sway), f)
        # Cute quick natural blink around f=44..50
        for f, bv in ((1, 0.0), (43, 0.0), (46, 1.0), (50, 0.0), (120, 0.0)):
            set_sk(b_sk, "Blink_L", bv, f)
            set_sk(b_sk, "Blink_R", bv, f)

    create_action_and_nla(arm_obj, body, tongue, pl, pr, "Idle", anim_idle, 120)

    # 2. Purr_Knead (72 frames = 3s loop: happy squint + alternating paw kneading!)
    def anim_purr(set_rot, set_sk, b_sk, t_sk, pl_sk, pr_sk):
        for f in range(1, 73, 9):
            p = 2.0 * math.pi * (f - 1) / 71.0
            set_sk(b_sk, "Happy_Squint", 0.88, f)
            set_sk(b_sk, "Cheek_Puff", 0.65, f)
            set_sk(b_sk, "Breathe_Inhale", 0.5 + 0.4 * math.sin(p * 2.0), f)
            set_sk(pl_sk, "Pupil_Dilate", 0.85, f)
            set_sk(pr_sk, "Pupil_Dilate", 0.85, f)
            set_rot("Head", (-6.0 + math.sin(p) * 3.0, math.cos(p) * 5.0, math.sin(p) * 4.0), f)
            set_rot("Ear_L", (-8.0, -5.0, 0.0), f)
            set_rot("Ear_R", (-8.0, 5.0, 0.0), f)
            # Alternating left/right biscuit kneading!
            kl = max(0.0, math.sin(p * 2.0))
            kr = max(0.0, -math.sin(p * 2.0))
            set_rot("UpperArm_L", (-14.0 * kl, 0.0, 0.0), f)
            set_rot("Forearm_L", (18.0 * kl, 0.0, 0.0), f)
            set_rot("Paw_L", (-22.0 * kl, 0.0, 0.0), f)
            set_rot("UpperArm_R", (-14.0 * kr, 0.0, 0.0), f)
            set_rot("Forearm_R", (18.0 * kr, 0.0, 0.0), f)
            set_rot("Paw_R", (-22.0 * kr, 0.0, 0.0), f)
            for ti in range(1, 8):
                set_rot(f"Tail_0{ti}", (math.sin(p + ti * 0.5) * 4.0, 0.0, 6.0 + math.cos(p + ti * 0.5) * 6.0), f)

    create_action_and_nla(arm_obj, body, tongue, pl, pr, "Purr_Knead", anim_purr, 72)

    # 3. Playful_Wave (60 frames = 2.5s: lifts right paw & waves cutely!)
    def anim_wave(set_rot, set_sk, b_sk, t_sk, pl_sk, pr_sk):
        keyframes = [
            (1,  0.0,  0.0),
            (14, 1.0,  0.0),
            (24, 1.0,  1.0),
            (34, 1.0, -1.0),
            (44, 1.0,  0.8),
            (60, 0.0,  0.0),
        ]
        for f, lift, wave in keyframes:
            set_sk(pl_sk, "Pupil_Dilate", 0.95 * lift, f)
            set_sk(pr_sk, "Pupil_Dilate", 0.95 * lift, f)
            set_rot("Spine_Upper", (4.0 * lift, -3.0 * lift, 0.0), f)
            set_rot("Head", (4.0 * lift, -10.0 * lift, 6.0 * lift), f)
            set_rot("Shoulder_R", (-15.0 * lift, 0.0, -6.0 * lift), f)
            set_rot("UpperArm_R", (-52.0 * lift, 8.0 * wave, 6.0 * lift), f)
            set_rot("Forearm_R", (-28.0 * lift, 0.0, 14.0 * wave), f)
            set_rot("Paw_R", (-15.0 * lift + 18.0 * wave, 0.0, 10.0 * wave), f)
            set_rot("Collar_Bell", (6.0 * wave, 0.0, 10.0 * wave), f)

    create_action_and_nla(arm_obj, body, tongue, pl, pr, "Playful_Wave", anim_wave, 60)

    # 4. Curious_Tilt (72 frames = 3s)
    def anim_curious(set_rot, set_sk, b_sk, t_sk, pl_sk, pr_sk):
        for f, w in ((1, 0.0), (16, 1.0), (52, 1.0), (72, 0.0)):
            set_sk(pl_sk, "Pupil_Dilate", 0.85 * w, f)
            set_sk(pr_sk, "Pupil_Dilate", 0.85 * w, f)
            set_rot("Neck", (3.0 * w, 8.0 * w, 4.0 * w), f)
            set_rot("Head", (5.0 * w, 18.0 * w, 8.0 * w), f)
            set_rot("Ear_L", (10.0 * w, 0.0, 4.0 * w), f)
            set_rot("Ear_R", (-4.0 * w, 0.0, -4.0 * w), f)
            for ti in range(1, 8):
                set_rot(f"Tail_0{ti}", (8.0 * w, 0.0, 4.0 * w), f)

    create_action_and_nla(arm_obj, body, tongue, pl, pr, "Curious_Tilt", anim_curious, 72)

    # 5. Meow (48 frames = 2s: chin lift, jaw open, tongue peek, ear perk!)
    def anim_meow(set_rot, set_sk, b_sk, t_sk, pl_sk, pr_sk):
        for f, m, c in ((1, 0.0, 0.0), (10, 0.4, 0.5), (20, 1.0, 1.0), (32, 0.65, 0.8), (48, 0.0, 0.0)):
            set_sk(b_sk, "Meow_Open", m, f)
            set_sk(b_sk, "Cheek_Puff", 0.35 * m, f)
            set_sk(t_sk, "Blep", 0.35 * m, f)
            set_rot("Head", (-8.0 * c, 0.0, 0.0), f)
            set_rot("Jaw", (20.0 * m, 0.0, 0.0), f)
            set_rot("Ear_L", (8.0 * c, 0.0, 0.0), f)
            set_rot("Ear_R", (8.0 * c, 0.0, 0.0), f)
            set_sk(b_sk, "Breathe_Inhale", 0.9 * c, f)

    create_action_and_nla(arm_obj, body, tongue, pl, pr, "Meow", anim_meow, 48)

    # 6. Stretch (84 frames = 3.5s)
    def anim_stretch(set_rot, set_sk, b_sk, t_sk, pl_sk, pr_sk):
        for f, s in ((1, 0.0), (24, 1.0), (56, 1.0), (84, 0.0)):
            set_sk(b_sk, "Happy_Squint", 0.75 * s, f)
            set_sk(b_sk, "Breathe_Inhale", 1.0 * s, f)
            set_rot("Spine_Lower", (14.0 * s, 0.0, 0.0), f)
            set_rot("Spine_Upper", (12.0 * s, 0.0, 0.0), f)
            set_rot("Chest", (-10.0 * s, 0.0, 0.0), f)
            set_rot("Head", (-18.0 * s, 0.0, 0.0), f)
            for side in ("L", "R"):
                set_rot(f"UpperArm_{side}", (-35.0 * s, 0.0, 0.0), f)
                set_rot(f"Forearm_{side}", (18.0 * s, 0.0, 0.0), f)
                set_rot(f"Paw_{side}", (15.0 * s, 0.0, 0.0), f)
            for ti in range(1, 8):
                set_rot(f"Tail_0{ti}", (12.0 * s, 0.0, -5.0 * s), f)

    create_action_and_nla(arm_obj, body, tongue, pl, pr, "Stretch", anim_stretch, 84)

    # 7. Sleepy_Nap (120 frames = 5s loop: tucked cozy head, closed eyes, slow deep breathing!)
    def anim_sleep(set_rot, set_sk, b_sk, t_sk, pl_sk, pr_sk):
        for f in (1, 40, 80, 120):
            p = 2.0 * math.pi * (f - 1) / 119.0
            br = 0.5 - 0.5 * math.cos(p)
            set_sk(b_sk, "Blink_L", 1.0, f)
            set_sk(b_sk, "Blink_R", 1.0, f)
            set_sk(b_sk, "Breathe_Inhale", br, f)
            set_rot("Spine_Lower", (8.0 + br * 1.5, 0.0, 0.0), f)
            set_rot("Spine_Upper", (10.0 + br * 1.8, 0.0, 0.0), f)
            set_rot("Neck", (14.0, 6.0, 4.0), f)
            set_rot("Head", (18.0 + br * 1.5, 8.0, 6.0), f)
            set_rot("Ear_L", (-10.0, -8.0, 0.0), f)
            set_rot("Ear_R", (-10.0, 8.0, 0.0), f)
            for ti in range(1, 8):
                set_rot(f"Tail_0{ti}", (-3.0, 0.0, 8.0), f)

    create_action_and_nla(arm_obj, body, tongue, pl, pr, "Sleepy_Nap", anim_sleep, 120)

    # Leave only Idle active in Blender viewport (mute others? Wait: test NLA mute vs export!)
    # Note: io_scene_gltf2 exports NLA tracks even when muted? Let's verify, or set Idle as active!
    for t in arm_obj.animation_data.nla_tracks:
        t.mute = (t.name != "Idle")
    for sk in (body.data.shape_keys, tongue.data.shape_keys, pl.data.shape_keys, pr.data.shape_keys):
        if sk.animation_data:
            for t in sk.animation_data.nla_tracks:
                t.mute = (t.name != "Idle")

    for pb in arm_obj.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
    for sk in (body.data.shape_keys, tongue.data.shape_keys, pl.data.shape_keys, pr.data.shape_keys):
        for kb in sk.key_blocks:
            kb.value = 0.0
    bpy.context.scene.frame_set(1)


def export_glb():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(TEX_OUT_DIR, exist_ok=True)

    # Copy Cat_Coat_Mask.png + Fur Normal/Roughness/Iris to public/textures/ for Three.js live coat switcher!
    src_tex = r"C:\Users\Rohith\cute-cat-3d\textures"
    for fname in ("Cat_Coat_Mask.png", "Cat_Fur_Albedo.png", "Cat_Fur_Normal.png", "Cat_Fur_Roughness.png", "Cat_Iris_Albedo.png"):
        sp = os.path.join(src_tex, fname)
        if os.path.exists(sp):
            shutil.copy2(sp, os.path.join(TEX_OUT_DIR, fname))

    # Temporarily swap Cat_Cornea_PBR to Principled BSDF so glTF exports clean transparent glossy material!
    cornea_mat = bpy.data.materials["Cat_Cornea_PBR"]
    old_nodes_backup = True
    nt = cornea_mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.02
    bsdf.inputs['IOR'].default_value = 1.45
    if 'Alpha' in bsdf.inputs:
        bsdf.inputs['Alpha'].default_value = 0.08
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

    # Select only cat + cushion (exclude lights/camera so Three.js manages lights/camera cleanly!)
    bpy.ops.object.select_all(action='DESELECT')
    export_names = [
        "Cat_Rig", "Cat_Body", "Cat_Nose", "Cat_Tongue", "Cat_Whiskers",
        "Cat_Collar", "Cat_Bell", "Cat_Bell_Ring", "Cat_ToeBeans",
        "Cat_Eye_L", "Cat_Eye_R", "Cat_Pupil_L", "Cat_Pupil_R",
        "Cat_Cornea_L", "Cat_Cornea_R", "Cozy_Cushion"
    ]
    for n in export_names:
        if n in bpy.data.objects:
            bpy.data.objects[n].select_set(True)

    bpy.ops.export_scene.gltf(
        filepath=GLB_PATH,
        export_format='GLB',
        use_selection=True,
        export_apply=True,
        export_animations=True,
        export_animation_mode='NLA_TRACKS',
        export_skins=True,
        export_morph=True,
        export_morph_animation=True,
        export_anim_slide_to_zero=True,
        export_image_format='AUTO',
    )
    print(f"Exported GLB to {GLB_PATH} ({os.path.getsize(GLB_PATH)/1024/1024:.2f} MB)")

    # Restore EEVEE crystal-clear glass shader on Cat_Cornea_PBR for Blender viewport/renders!
    nt.nodes.clear()
    out_co = nt.nodes.new("ShaderNodeOutputMaterial")
    mix_co = nt.nodes.new("ShaderNodeMixShader")
    trans_co = nt.nodes.new("ShaderNodeBsdfTransparent")
    gloss_co = nt.nodes.new("ShaderNodeBsdfGlossy")
    gloss_co.inputs['Roughness'].default_value = 0.015
    fres_co = nt.nodes.new("ShaderNodeLayerWeight")
    fres_co.inputs['Blend'].default_value = 0.10
    nt.links.new(fres_co.outputs['Fresnel'], mix_co.inputs['Fac'])
    nt.links.new(trans_co.outputs['BSDF'], mix_co.inputs[1])
    nt.links.new(gloss_co.outputs['BSDF'], mix_co.inputs[2])
    nt.links.new(mix_co.outputs['Shader'], out_co.inputs['Surface'])

    # Save full .blend file cleanly!
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    print(f"Saved Blender file to {BLEND_PATH}")


def main():
    body = bpy.data.objects["Cat_Body"]
    arm_obj = build_armature()
    weight_cat_body(body, arm_obj)
    bind_rigid_and_accessory_meshes(arm_obj)
    build_facial_shape_keys(body)
    build_all_animations(arm_obj)
    export_glb()


if __name__ == "__main__":
    main()
