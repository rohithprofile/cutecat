import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { CatAudioEngine } from "./audio.js";
import { attachFurShells } from "./furShells.js";
import { CatToysAndFX } from "./toys.js";

// ==============================================================================
// MOCHI 3D — Peak Interactive Realistic Cat Companion
// ==============================================================================

const container = document.getElementById("canvas-container");
const loaderOverlay = document.getElementById("loader-overlay");
const loaderBar = document.getElementById("loader-bar");
const moodLabel = document.getElementById("mood-label");
const affectionCountEl = document.getElementById("affection-count");
const reactionToast = document.getElementById("reaction-toast");
const hintPill = document.getElementById("hint-pill");

// Renderer
const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.12;
renderer.outputColorSpace = THREE.SRGBColorSpace;
container.appendChild(renderer.domElement);

// Scene & PMREM Environment (makes wet glass eyes & brass bell shine!)
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1b1716);
scene.fog = new THREE.FogExp2(0x1b1716, 0.32);

const pmrem = new THREE.PMREMGenerator(renderer);
const roomEnv = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environment = roomEnv;
scene.environmentIntensity = 0.68;

// Camera & Damped OrbitControls
const camera = new THREE.PerspectiveCamera(36, window.innerWidth / window.innerHeight, 0.05, 25);
camera.position.set(-0.28, 0.34, 0.62);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.065;
controls.target.set(0, 0.175, 0.0);
controls.minDistance = 0.24;
controls.maxDistance = 1.45;
controls.maxPolarAngle = Math.PI * 0.495;
controls.minPolarAngle = 0.22;

// Cozy Floor / Studio Rug under Cushion
const floorMat = new THREE.MeshStandardMaterial({
  color: 0x241f1c,
  roughness: 0.92,
  metalness: 0.02,
});
const floorMesh = new THREE.Mesh(new THREE.CircleGeometry(3.2, 64), floorMat);
floorMesh.rotation.x = -Math.PI / 2;
floorMesh.position.y = -0.062;
floorMesh.receiveShadow = true;
floorMesh.name = "Studio_Floor";
scene.add(floorMesh);

// Subtle warm wood ring / ambient plinth shadow pad
const rugMat = new THREE.MeshStandardMaterial({
  color: 0x322a25,
  roughness: 0.95,
});
const rugMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.46, 0.47, 0.006, 64), rugMat);
rugMesh.position.set(0, -0.059, 0.02);
rugMesh.receiveShadow = true;
scene.add(rugMesh);

// Lighting Rig (Dynamic Presets: Sunbeam, Studio, Moonlight, Golden Hour)
const hemiLight = new THREE.HemisphereLight(0xffe8d2, 0x2e2934, 0.65);
scene.add(hemiLight);

const keyLight = new THREE.DirectionalLight(0xfff1dc, 2.35);
keyLight.position.set(-0.85, 1.35, 1.15);
keyLight.castShadow = true;
keyLight.shadow.mapSize.set(2048, 2048);
keyLight.shadow.camera.near = 0.2;
keyLight.shadow.camera.far = 4.0;
const dCam = 0.45;
keyLight.shadow.camera.left = -dCam;
keyLight.shadow.camera.right = dCam;
keyLight.shadow.camera.top = dCam;
keyLight.shadow.camera.bottom = -dCam;
keyLight.shadow.bias = -0.0004;
keyLight.shadow.normalBias = 0.012;
scene.add(keyLight);

const fillLight = new THREE.DirectionalLight(0xcbe0ff, 0.85);
fillLight.position.set(1.1, 0.65, 0.75);
scene.add(fillLight);

const rimLight = new THREE.SpotLight(0xffcb8c, 3.2, 3.5, Math.PI * 0.35, 0.65, 1.2);
rimLight.position.set(0.35, 0.85, -0.95);
rimLight.target.position.set(0, 0.2, 0);
scene.add(rimLight, rimLight.target);

// Floating Warm Sunbeam Dust Motes
const moteCount = 90;
const moteGeo = new THREE.BufferGeometry();
const motePos = new Float32Array(moteCount * 3);
for (let i = 0; i < moteCount; i++) {
  motePos[i * 3 + 0] = (Math.random() - 0.5) * 1.1;
  motePos[i * 3 + 1] = Math.random() * 0.75;
  motePos[i * 3 + 2] = (Math.random() - 0.5) * 1.1;
}
moteGeo.setAttribute("position", new THREE.BufferAttribute(motePos, 3));
const moteMat = new THREE.PointsMaterial({
  color: 0xffdfba,
  size: 0.006,
  transparent: true,
  opacity: 0.38,
  depthWrite: false,
});
const motes = new THREE.Points(moteGeo, moteMat);
scene.add(motes);

// Audio & Toys
const audio = new CatAudioEngine();
const toys = new CatToysAndFX(scene);

// Interactive State
const state = {
  mode: "pet", // "pet" | "laser" | "yarn"
  lighting: "sunbeam",
  affection: 0,
  pettingEnergy: 0,
  petZone: null,
  isPointerDown: false,
  isPetting: false,
  lastPointer: new THREE.Vector2(),
  pointerNDC: new THREE.Vector2(),
  targetLookWorld: new THREE.Vector3(0, 0.30, 0.65),
  hasCursorTarget: false,
  blinkTimer: 2.2,
  blinkVal: 0,
  happyTimer: 0,
  boopTimer: 0,
  meowTimer: 0,
  blepAmount: 0,
  blepAutoTimer: 9.0,
  earTwitchL: 0,
  earTwitchR: 0,
  swatSide: null,
  swatTimer: 0,
  bellAngle: 0,
  bellVel: 0,
  pupilTarget: 0.32, // 0=basis oval, >0=dilate, <0=slit
  pupilCurrent: 0.32,
  bobaLocked: false,
  camTween: null,
};

// Model Refs
let catRoot = null;
let catBody = null;
let catNose = null;
let catTongue = null;
let catPupilL = null;
let catPupilR = null;
let catEyeL = null;
let catEyeR = null;
let catCorneaL = null;
let catCorneaR = null;
let collarObjs = [];
let cushionMesh = null;
let furSystem = null;
let originalFurTexture = null;

// Animation & Bones
let mixer = null;
const actions = {};
let activeAction = null;
let activeAnimName = "Idle";
const bones = {};
const boneRestWorldQuat = {};
const interactiveMeshes = [];

// Smooth camera tween helper
function tweenCamera(pos, tgt, duration = 0.65) {
  state.camTween = {
    startPos: camera.position.clone(),
    startTgt: controls.target.clone(),
    endPos: new THREE.Vector3(...pos),
    endTgt: new THREE.Vector3(...tgt),
    t: 0,
    dur: duration,
  };
}

let toastTimeout = null;
function showToast(msg) {
  reactionToast.textContent = msg;
  reactionToast.classList.add("visible");
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => reactionToast.classList.remove("visible"), 1500);
}

function addAffection(pts = 1) {
  state.affection += pts;
  affectionCountEl.textContent = state.affection;
}

// ==============================================================================
// LOAD BLENDER GLB MODEL
// ==============================================================================
const gltfLoader = new GLTFLoader();
gltfLoader.load(
  "./models/cat.glb",
  (gltf) => {
    try {
      catRoot = gltf.scene;
      scene.add(catRoot);

    catRoot.traverse((obj) => {
      if (obj.isBone) {
        bones[obj.name] = obj;
      }
      if (obj.isMesh) {
        obj.castShadow = true;
        obj.receiveShadow = true;

        if (obj.name === "Cat_Body") {
          catBody = obj;
          interactiveMeshes.push(obj);
          originalFurTexture = obj.material.map;
          // Upgrade to lush velvety MeshPhysicalMaterial
          const oldMat = obj.material;
          const furMat = new THREE.MeshPhysicalMaterial({
            map: oldMat.map,
            normalMap: oldMat.normalMap,
            normalScale: new THREE.Vector2(0.55, 0.55),
            roughnessMap: oldMat.roughnessMap,
            roughness: 0.72,
            metalness: 0.0,
            sheen: 0.85,
            sheenRoughness: 0.52,
            sheenColor: new THREE.Color(0xffdfc2),
          });
          obj.material = furMat;
          furSystem = attachFurShells(obj, furMat, 8);
        } else if (obj.name === "Cat_Nose") {
          catNose = obj;
          interactiveMeshes.push(obj);
          obj.material = new THREE.MeshPhysicalMaterial({
            color: 0xe68888,
            roughness: 0.24,
            clearcoat: 0.65,
            clearcoatRoughness: 0.18,
          });
        } else if (obj.name === "Cat_Tongue") {
          catTongue = obj;
          obj.material = new THREE.MeshPhysicalMaterial({
            color: 0xe87a82,
            roughness: 0.35,
            clearcoat: 0.3,
          });
        } else if (obj.name === "Cat_Eye_L" || obj.name === "Cat_Eye_R") {
          if (obj.name === "Cat_Eye_L") catEyeL = obj;
          else catEyeR = obj;
          obj.castShadow = false;
          obj.material = new THREE.MeshStandardMaterial({
            map: obj.material.map,
            roughness: 0.22,
            metalness: 0.0,
          });
        } else if (obj.name === "Cat_Pupil_L" || obj.name === "Cat_Pupil_R") {
          if (obj.name === "Cat_Pupil_L") catPupilL = obj;
          else catPupilR = obj;
          obj.castShadow = false;
          obj.material = new THREE.MeshBasicMaterial({ color: 0x050507 });
        } else if (obj.name === "Cat_Cornea_L" || obj.name === "Cat_Cornea_R") {
          if (obj.name === "Cat_Cornea_L") catCorneaL = obj;
          else catCorneaR = obj;
          obj.castShadow = false;
          obj.receiveShadow = false;
          // Crystal clear wet glass dome with dazzling specular catchlights!
          obj.material = new THREE.MeshPhysicalMaterial({
            color: 0xffffff,
            transparent: true,
            opacity: 0.14,
            roughness: 0.015,
            metalness: 0.0,
            ior: 1.48,
            reflectivity: 1.0,
            clearcoat: 1.0,
            clearcoatRoughness: 0.015,
            envMapIntensity: 2.6,
            depthWrite: false,
          });
          obj.renderOrder = 4;
        } else if (obj.name === "Cat_Whiskers") {
          obj.castShadow = false;
          obj.material = new THREE.MeshPhysicalMaterial({
            color: 0xf9f5f0,
            roughness: 0.32,
            transparent: true,
            opacity: 0.88,
          });
        } else if (obj.name === "Cat_Collar" || obj.name === "Cat_Bell" || obj.name === "Cat_Bell_Ring") {
          collarObjs.push(obj);
        } else if (obj.name === "Cozy_Cushion") {
          cushionMesh = obj;
          obj.castShadow = true;
          obj.receiveShadow = true;
          if (obj.material) {
            obj.material.roughness = 0.88;
            obj.material.sheen = 0.6;
          }
        }
      }
    });

    // Record rest world quaternions of key bones for exact axis-independent additive procedural overrides
    catRoot.updateMatrixWorld(true);
    for (const bName of Object.keys(bones)) {
      const q = new THREE.Quaternion();
      bones[bName].getWorldQuaternion(q);
      boneRestWorldQuat[bName] = q;
    }

    // Setup AnimationMixer with all 7 Blender clips!
    mixer = new THREE.AnimationMixer(catRoot);
    for (const clip of gltf.animations) {
      const act = mixer.clipAction(clip);
      if (clip.name === "Meow" || clip.name === "Playful_Wave" || clip.name === "Stretch") {
        act.setLoop(THREE.LoopOnce);
        act.clampWhenFinished = true;
      } else {
        act.setLoop(THREE.LoopRepeat);
      }
      actions[clip.name] = act;
    }

    mixer.addEventListener("finished", (e) => {
      if (e.action !== actions.Idle) {
        playAnimation("Idle", 0.45);
      }
    });

    playAnimation("Idle", 0.0);

      // Hide loader smoothly!
      loaderBar.style.width = "100%";
      document.body.dataset.catReady = "true";
      loaderOverlay.classList.add("hidden");
    } catch (err) {
      console.error("Init error:", err);
      document.querySelector(".loader-text").textContent = "Init Error: " + (err?.message || err);
    }
  },
  (xhr) => {
    if (xhr.total > 0) {
      loaderBar.style.width = `${Math.round((xhr.loaded / xhr.total) * 100)}%`;
    }
  },
  (err) => {
    console.error("Failed loading cat.glb:", err);
    document.querySelector(".loader-text").textContent = "Error loading 3D model — check console.";
  }
);

function playAnimation(name, fadeSec = 0.35) {
  const next = actions[name];
  if (!next) return;
  if (activeAction === next && next.isRunning()) return;

  next.reset();
  next.enabled = true;
  next.setEffectiveTimeScale(1);
  next.setEffectiveWeight(1);
  if (activeAction && activeAction !== next) {
    next.crossFadeFrom(activeAction, fadeSec, true);
  }
  next.play();
  activeAction = next;
  activeAnimName = name;

  document.querySelectorAll("[data-anim]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.anim === name);
  });

  if (name === "Meow") {
    audio.playMeow("meow");
    state.meowTimer = 0.65;
    showToast("Mee-ow! 🎵");
  } else if (name === "Playful_Wave") {
    audio.playBell(0.8);
    showToast("Wave! 🐾");
  } else if (name === "Sleepy_Nap") {
    moodLabel.textContent = "• Purring Asleep 💤";
  } else if (name === "Idle") {
    moodLabel.textContent = "• Curious & Cozy";
  }
}

// ==============================================================================
// AXIS-INDEPENDENT ADDITIVE BONE ROTATION HELPER
// ==============================================================================
const _tmpParentQ = new THREE.Quaternion();
const _tmpWorldDelta = new THREE.Quaternion();
const _tmpEuler = new THREE.Euler();

function applyWorldDeltaToBone(boneName, pitchX, yawY, rollZ) {
  const bone = bones[boneName];
  const restQ = boneRestWorldQuat[boneName];
  if (!bone || !restQ) return;
  _tmpEuler.set(pitchX, yawY, rollZ, "YXZ");
  _tmpWorldDelta.setFromEuler(_tmpEuler);
  // Conjugate world rotation into bone's local frame: q_local_delta = restQ^-1 * worldDelta * restQ
  const qInv = _tmpParentQ.copy(restQ).invert();
  const localDelta = qInv.multiply(_tmpWorldDelta).multiply(restQ);
  bone.quaternion.multiply(localDelta);
}

// ==============================================================================
// RAYCASTING, PETTING, BOOPING & TOY INTERACTION
// ==============================================================================
const raycaster = new THREE.Raycaster();

function updatePointerNDC(ev) {
  const rect = renderer.domElement.getBoundingClientRect();
  state.pointerNDC.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
  state.pointerNDC.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
}

function classifyCatHit(hit) {
  if (hit.object === catNose) return "nose";
  const p = hit.point;
  // Remember glTF world coords: Y = height, Z = front (+0.11 nose), X = left/right!
  if (p.y > 0.322 && Math.abs(p.x) > 0.024) return p.x > 0 ? "earL" : "earR";
  if (p.y > 0.242) return p.y > 0.285 ? "head" : "chin";
  if (p.y < 0.055 && p.z > 0.03 && Math.abs(p.x) < 0.055) return p.x >= 0 ? "pawL" : "pawR";
  if (p.x > 0.078 && p.y < 0.075) return "tail";
  if (p.y > 0.10 && p.z > 0.01) return "chest";
  return "back";
}

function getCursorWorldLookTarget() {
  raycaster.setFromCamera(state.pointerNDC, camera);
  // Intersect a gentle virtual plane in front of the cat so cursor tracking feels 3D & natural
  const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), -0.45);
  const pt = new THREE.Vector3();
  if (raycaster.ray.intersectPlane(plane, pt)) {
    return pt;
  }
  return new THREE.Vector3(state.pointerNDC.x * 0.4, 0.30 + state.pointerNDC.y * 0.25, 0.45);
}

renderer.domElement.addEventListener("pointerdown", (ev) => {
  audio.unlock();
  updatePointerNDC(ev);
  state.isPointerDown = true;
  state.lastPointer.set(ev.clientX, ev.clientY);

  if (state.mode === "yarn" && toys.yarnBall.visible) {
    raycaster.setFromCamera(state.pointerNDC, camera);
    if (raycaster.intersectObject(toys.yarnBall).length > 0) {
      toys.yarnGrabbed = true;
      controls.enabled = false;
      container.classList.add("grabbing-cursor");
      return;
    }
  }

  if (state.mode === "pet") {
    raycaster.setFromCamera(state.pointerNDC, camera);
    const hits = raycaster.intersectObjects(interactiveMeshes, false);
    if (hits.length > 0) {
      const zone = classifyCatHit(hits[0]);
      state.petZone = zone;
      state.isPetting = true;
      controls.enabled = false; // Stroke cat smoothly without spinning camera!

      if (zone === "nose") {
        state.boopTimer = 0.75;
        state.blinkVal = 1.0;
        audio.playMeow("mrrp");
        addAffection(3);
        toys.spawnHeart(hits[0].point);
        showToast("Boop! *mrrp* 💕");
      } else if (zone === "earL") {
        state.earTwitchL = 1.0;
        audio.playBell(0.45);
        showToast("Ear tickle! 🐾");
      } else if (zone === "earR") {
        state.earTwitchR = 1.0;
        audio.playBell(0.45);
        showToast("Ear tickle! 🐾");
      } else if (zone === "pawL" || zone === "pawR") {
        playAnimation("Playful_Wave", 0.25);
        addAffection(2);
      } else if (zone === "tail") {
        audio.playMeow("mrrp");
        state.earTwitchL = 0.7;
        state.earTwitchR = 0.7;
        showToast("Tail flick! 🐈");
      }
    }
  }
});

let lastParticleAt = 0;
renderer.domElement.addEventListener("pointermove", (ev) => {
  updatePointerNDC(ev);
  state.hasCursorTarget = true;

  if (state.mode === "laser") {
    raycaster.setFromCamera(state.pointerNDC, camera);
    const targets = [floorMesh, rugMesh, ...(cushionMesh ? [cushionMesh] : []), ...interactiveMeshes];
    const hits = raycaster.intersectObjects(targets, false);
    if (hits.length > 0) {
      toys.laserGroup.visible = true;
      toys.laserGroup.position.copy(hits[0].point).add(new THREE.Vector3(0, 0.004, 0));
      state.targetLookWorld.copy(hits[0].point);
      // If laser is right in front of paws, cat bats excitedly!
      if (hits[0].point.y < 0.08 && Math.hypot(hits[0].point.x, hits[0].point.z - 0.12) < 0.095 && state.swatTimer <= 0) {
        state.swatTimer = 0.45;
        state.swatSide = hits[0].point.x >= 0 ? "L" : "R";
        audio.playMeow("chirp");
        audio.playBell(0.75);
      }
    }
    return;
  }

  if (state.mode === "yarn" && toys.yarnGrabbed) {
    raycaster.setFromCamera(state.pointerNDC, camera);
    const dragPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -0.05);
    const pt = new THREE.Vector3();
    if (raycaster.ray.intersectPlane(dragPlane, pt)) {
      pt.x = THREE.MathUtils.clamp(pt.x, -0.38, 0.38);
      pt.z = THREE.MathUtils.clamp(pt.z, -0.35, 0.38);
      toys.yarnVel.copy(pt).sub(toys.yarnBall.position).multiplyScalar(14.0);
      toys.yarnBall.position.copy(pt);
    }
    return;
  }

  // Hover/stroke petting
  raycaster.setFromCamera(state.pointerNDC, camera);
  const hits = raycaster.intersectObjects(interactiveMeshes, false);

  if (state.isPetting && hits.length > 0) {
    const moveDist = Math.hypot(ev.clientX - state.lastPointer.x, ev.clientY - state.lastPointer.y);
    state.lastPointer.set(ev.clientX, ev.clientY);
    if (moveDist > 2) {
      const zone = classifyCatHit(hits[0]);
      state.petZone = zone;
      state.pettingEnergy = Math.min(1.0, state.pettingEnergy + moveDist * 0.012);
      state.happyTimer = 1.6;
      moodLabel.textContent = "• Purring Blissfully ♥";

      const now = performance.now();
      if (now - lastParticleAt > 180) {
        lastParticleAt = now;
        addAffection(1);
        toys.spawnHeart(hits[0].point);
      }
    }
  } else {
    container.classList.toggle("petting-cursor", state.mode === "pet" && hits.length > 0);
  }
});

window.addEventListener("pointerup", () => {
  state.isPointerDown = false;
  state.isPetting = false;
  toys.yarnGrabbed = false;
  controls.enabled = true;
  container.classList.remove("grabbing-cursor");
});

// ==============================================================================
// LIVE COAT & EYE COLOR CUSTOMIZER (Canvas-composited preserving 2K hair strands!)
// ==============================================================================
const COAT_PALETTES = {
  ginger: null, // uses original baked Blender texture
  silver:  { baseL: [0.62, 0.64, 0.67], baseD: [0.38, 0.40, 0.44], stripe: [0.15, 0.16, 0.19], white: [0.94, 0.94, 0.96], ear: [0.78, 0.56, 0.58] },
  cream:   { baseL: [0.88, 0.78, 0.65], baseD: [0.72, 0.60, 0.46], stripe: [0.60, 0.48, 0.36], white: [0.97, 0.94, 0.90], ear: [0.85, 0.58, 0.56] },
  tuxedo:  { baseL: [0.14, 0.14, 0.16], baseD: [0.06, 0.06, 0.08], stripe: [0.04, 0.04, 0.05], white: [0.96, 0.96, 0.97], ear: [0.55, 0.36, 0.38] },
  siamese: { baseL: [0.88, 0.81, 0.70], baseD: [0.76, 0.67, 0.56], stripe: [0.34, 0.24, 0.18], white: [0.92, 0.86, 0.76], ear: [0.28, 0.19, 0.14] },
};

let maskImageData = null;
let albedoImageData = null;
async function ensureCoatSourcePixels() {
  if (maskImageData && albedoImageData) return true;
  const loadImg = (src) =>
    new Promise((res, rej) => {
      const im = new Image();
      im.onload = () => res(im);
      im.onerror = rej;
      im.src = src;
    });
  try {
    const [mImg, aImg] = await Promise.all([
      loadImg("./textures/Cat_Coat_Mask.png"),
      loadImg("./textures/Cat_Fur_Albedo.png"),
    ]);
    const sz = 1024;
    const c1 = document.createElement("canvas");
    c1.width = sz; c1.height = sz;
    const x1 = c1.getContext("2d");
    x1.drawImage(mImg, 0, 0, sz, sz);
    maskImageData = x1.getImageData(0, 0, sz, sz).data;

    const c2 = document.createElement("canvas");
    c2.width = sz; c2.height = sz;
    const x2 = c2.getContext("2d");
    x2.drawImage(aImg, 0, 0, sz, sz);
    albedoImageData = x2.getImageData(0, 0, sz, sz).data;
    return true;
  } catch (e) {
    console.warn("Coat recoloring textures unavailable:", e);
    return false;
  }
}

async function applyCoatPreset(key) {
  if (!catBody) return;
  if (key === "ginger" && originalFurTexture) {
    catBody.material.map = originalFurTexture;
    catBody.material.needsUpdate = true;
    if (furSystem) furSystem.setMap(originalFurTexture);
    return;
  }
  const ok = await ensureCoatSourcePixels();
  if (!ok) return;
  const pal = COAT_PALETTES[key];
  const sz = 1024;
  const canvas = document.createElement("canvas");
  canvas.width = sz;
  canvas.height = sz;
  const ctx = canvas.getContext("2d");
  const out = ctx.createImageData(sz, sz);
  const dst = out.data;

  for (let i = 0; i < sz * sz; i++) {
    const p = i * 4;
    const st = maskImageData[p] / 255;
    const wh = maskImageData[p + 1] / 255;
    const er = maskImageData[p + 2] / 255;
    // Extract micro-hair brightness modulation from original albedo luminance!
    const lum = (albedoImageData[p] * 0.299 + albedoImageData[p + 1] * 0.587 + albedoImageData[p + 2] * 0.114) / 255;
    const strandMod = THREE.MathUtils.clamp(0.75 + (lum - 0.55) * 0.7, 0.55, 1.18);

    let r = (pal.baseD[0] * (1 - lum) + pal.baseL[0] * lum) * strandMod;
    let g = (pal.baseD[1] * (1 - lum) + pal.baseL[1] * lum) * strandMod;
    let b = (pal.baseD[2] * (1 - lum) + pal.baseL[2] * lum) * strandMod;

    r = r * (1 - st) + pal.stripe[0] * strandMod * st;
    g = g * (1 - st) + pal.stripe[1] * strandMod * st;
    b = b * (1 - st) + pal.stripe[2] * strandMod * st;

    r = r * (1 - wh) + pal.white[0] * (0.88 + 0.12 * lum) * wh;
    g = g * (1 - wh) + pal.white[1] * (0.88 + 0.12 * lum) * wh;
    b = b * (1 - wh) + pal.white[2] * (0.88 + 0.12 * lum) * wh;

    r = r * (1 - er) + pal.ear[0] * er;
    g = g * (1 - er) + pal.ear[1] * er;
    b = b * (1 - er) + pal.ear[2] * er;

    dst[p] = Math.min(255, Math.max(0, r * 255));
    dst[p + 1] = Math.min(255, Math.max(0, g * 255));
    dst[p + 2] = Math.min(255, Math.max(0, b * 255));
    dst[p + 3] = 255;
  }
  ctx.putImageData(out, 0, 0);
  const tex = new THREE.CanvasTexture(canvas);
  tex.flipY = false; // glTF UV convention!
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.needsUpdate = true;

  catBody.material.map = tex;
  catBody.material.needsUpdate = true;
  if (furSystem) furSystem.setMap(tex);
}

function buildIrisCanvasTexture(innerHex, midHex, darkHex) {
  const sz = 512;
  const c = document.createElement("canvas");
  c.width = sz; c.height = sz;
  const ctx = c.getContext("2d");
  const img = ctx.createImageData(sz, sz);
  const d = img.data;
  const cIn = new THREE.Color(innerHex);
  const cMid = new THREE.Color(midHex);
  const cDk = new THREE.Color(darkHex);

  for (let y = 0; y < sz; y++) {
    // Note: flipY=false -> y=sz-1 corresponds to V=1.0 (front pupil pole)
    const v = y / (sz - 1);
    const theta = (1.0 - v) * Math.PI;
    const r = theta / (64 * Math.PI / 180);
    for (let x = 0; x < sz; x++) {
      const phi = (x / (sz - 1)) * Math.PI * 2;
      const fib =
        Math.sin(phi * 48 + Math.sin(r * 14)) * 0.35 +
        Math.sin(phi * 112 - r * 8) * 0.30 +
        Math.cos(phi * 210 + r * 22) * 0.20;
      const f01 = THREE.MathUtils.clamp(fib * 0.5 + 0.5, 0, 1);
      const goldMix = 1.0 - THREE.MathUtils.smoothstep(r, 0.18, 0.42 + (f01 - 0.5) * 0.15);
      const scleraW = THREE.MathUtils.smoothstep(r, 0.96, 1.05);
      const limbalW = THREE.MathUtils.smoothstep(r, 0.80, 0.91) * (1 - THREE.MathUtils.smoothstep(r, 0.98, 1.08));

      let cr = cDk.r * (1 - f01) + cMid.r * f01;
      let cg = cDk.g * (1 - f01) + cMid.g * f01;
      let cb = cDk.b * (1 - f01) + cMid.b * f01;

      cr = cr * (1 - goldMix) + cIn.r * goldMix;
      cg = cg * (1 - goldMix) + cIn.g * goldMix;
      cb = cb * (1 - goldMix) + cIn.b * goldMix;

      cr = cr * (1 - limbalW) + 0.05 * limbalW;
      cg = cg * (1 - limbalW) + 0.07 * limbalW;
      cb = cb * (1 - limbalW) + 0.07 * limbalW;

      cr = cr * (1 - scleraW) + 0.86 * scleraW;
      cg = cg * (1 - scleraW) + 0.84 * scleraW;
      cb = cb * (1 - scleraW) + 0.80 * scleraW;

      const idx = (y * sz + x) * 4;
      d[idx] = Math.round(Math.pow(cr, 1 / 2.2) * 255);
      d[idx + 1] = Math.round(Math.pow(cg, 1 / 2.2) * 255);
      d[idx + 2] = Math.round(Math.pow(cb, 1 / 2.2) * 255);
      d[idx + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  const tex = new THREE.CanvasTexture(c);
  tex.flipY = false;
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function applyEyePreset(preset) {
  if (!catEyeL || !catEyeR) return;
  if (preset === "emerald") {
    const tex = buildIrisCanvasTexture(0xd89a28, 0x4ca83c, 0x163d18);
    catEyeL.material.map = tex; catEyeR.material.map = tex;
  } else if (preset === "sapphire") {
    const tex = buildIrisCanvasTexture(0x88c8ff, 0x2674d9, 0x0c2b66);
    catEyeL.material.map = tex; catEyeR.material.map = tex;
  } else if (preset === "amber") {
    const tex = buildIrisCanvasTexture(0xf5c84c, 0xd46b15, 0x5c2204);
    catEyeL.material.map = tex; catEyeR.material.map = tex;
  } else if (preset === "odd") {
    catEyeL.material.map = buildIrisCanvasTexture(0x88c8ff, 0x2674d9, 0x0c2b66);
    catEyeR.material.map = buildIrisCanvasTexture(0xf5c84c, 0xd46b15, 0x5c2204);
  }
  catEyeL.material.needsUpdate = true;
  catEyeR.material.needsUpdate = true;
}

// ==============================================================================
// LIGHTING MOOD PRESETS
// ==============================================================================
function applyLightingMood(mood) {
  state.lighting = mood;
  if (mood === "sunbeam") {
    scene.background.setHex(0x1e1815);
    scene.fog.color.setHex(0x1e1815);
    keyLight.color.setHex(0xfff0d6);
    keyLight.intensity = 2.4;
    fillLight.color.setHex(0xcbe0ff);
    fillLight.intensity = 0.85;
    rimLight.color.setHex(0xffc985);
    rimLight.intensity = 3.2;
    hemiLight.intensity = 0.65;
    moteMat.color.setHex(0xffdfba);
    moteMat.opacity = 0.42;
  } else if (mood === "studio") {
    scene.background.setHex(0x191a1f);
    scene.fog.color.setHex(0x191a1f);
    keyLight.color.setHex(0xffffff);
    keyLight.intensity = 2.6;
    fillLight.color.setHex(0xd8e4ff);
    fillLight.intensity = 1.05;
    rimLight.color.setHex(0xfff4e8);
    rimLight.intensity = 2.5;
    hemiLight.intensity = 0.72;
    moteMat.opacity = 0.08;
  } else if (mood === "moonlight") {
    scene.background.setHex(0x0d101c);
    scene.fog.color.setHex(0x0d101c);
    keyLight.color.setHex(0x9bb8ff);
    keyLight.intensity = 1.35;
    fillLight.color.setHex(0x4b5c8c);
    fillLight.intensity = 0.55;
    rimLight.color.setHex(0xffaa5e);
    rimLight.intensity = 4.2; // Cozy warm bedside lamp rim!
    hemiLight.intensity = 0.42;
    moteMat.color.setHex(0xa8c9ff);
    moteMat.opacity = 0.48;
  } else if (mood === "sunset") {
    scene.background.setHex(0x211414);
    scene.fog.color.setHex(0x211414);
    keyLight.color.setHex(0xffae70);
    keyLight.intensity = 2.5;
    fillLight.color.setHex(0xb886c9);
    fillLight.intensity = 0.75;
    rimLight.color.setHex(0xff8f52);
    rimLight.intensity = 3.8;
    hemiLight.intensity = 0.55;
    moteMat.color.setHex(0xffb580);
    moteMat.opacity = 0.46;
  }
}

// ==============================================================================
// UI WIRING
// ==============================================================================
document.getElementById("cam-portrait-btn").addEventListener("click", () => tweenCamera([-0.26, 0.34, 0.60], [0, 0.18, 0.0]));
document.getElementById("cam-closeup-btn").addEventListener("click", () => tweenCamera([-0.08, 0.32, 0.34], [0, 0.285, 0.04]));
document.getElementById("cam-full-btn").addEventListener("click", () => tweenCamera([0.38, 0.42, 0.76], [0, 0.14, 0.0]));

const audioBtn = document.getElementById("audio-btn");
audioBtn.addEventListener("click", () => {
  audio.unlock();
  const next = !audio.enabled;
  audio.setEnabled(next);
  audioBtn.textContent = next ? "🔊 Sound On" : "🔇 Muted";
});

const drawerBtn = document.getElementById("drawer-btn");
const sideDrawer = document.getElementById("side-drawer");
drawerBtn.addEventListener("click", () => {
  sideDrawer.classList.toggle("open");
  drawerBtn.classList.toggle("active", sideDrawer.classList.contains("open"));
});

document.querySelectorAll("[data-mode]").forEach((btn) => {
  btn.addEventListener("click", () => {
    audio.unlock();
    const m = btn.dataset.mode;
    state.mode = m;
    document.querySelectorAll("[data-mode]").forEach((b) => b.classList.toggle("active", b === btn));
    container.classList.toggle("laser-cursor", m === "laser");
    if (m === "laser") {
      toys.hideYarn();
      toys.laserGroup.visible = true;
      hintPill.textContent = "Move cursor anywhere to tease Mochi with the laser dot!";
      moodLabel.textContent = "• Hunting Laser! 🎯";
      audio.playMeow("chirp");
    } else if (m === "yarn") {
      toys.laserGroup.visible = false;
      toys.spawnYarn();
      hintPill.textContent = "Grab & toss the yarn ball toward Mochi's paws!";
      moodLabel.textContent = "• Playful Mode 🧶";
    } else {
      toys.laserGroup.visible = false;
      toys.hideYarn();
      hintPill.textContent = "Stroke head, cheeks or chin to purr • Tap nose to boop • Drag empty space to orbit";
      moodLabel.textContent = "• Curious & Cozy";
    }
  });
});

document.getElementById("treat-btn").addEventListener("click", () => {
  audio.unlock();
  toys.tossTreat();
  showToast("Salmon Treat! 🐟");
  audio.playMeow("mrrp");
});

document.querySelectorAll("[data-anim]").forEach((btn) => {
  btn.addEventListener("click", () => {
    audio.unlock();
    playAnimation(btn.dataset.anim, 0.35);
  });
});

document.getElementById("blep-btn").addEventListener("click", () => {
  audio.unlock();
  state.blepAmount = state.blepAmount > 0.5 ? 0 : 1;
  showToast(state.blepAmount > 0 ? "Cute Blep! 😛" : "Tucked tongue!");
});

document.getElementById("lighting-chips").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-light]");
  if (!btn) return;
  document.querySelectorAll("#lighting-chips .chip-btn").forEach((b) => b.classList.toggle("active", b === btn));
  applyLightingMood(btn.dataset.light);
});

document.getElementById("coat-chips").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-coat]");
  if (!btn) return;
  document.querySelectorAll("#coat-chips .chip-btn").forEach((b) => b.classList.toggle("active", b === btn));
  applyCoatPreset(btn.dataset.coat);
});

document.getElementById("eye-chips").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-eye]");
  if (!btn) return;
  document.querySelectorAll("#eye-chips .chip-btn").forEach((b) => b.classList.toggle("active", b === btn));
  applyEyePreset(btn.dataset.eye);
});

const furSlider = document.getElementById("fur-slider");
const furVal = document.getElementById("fur-val");
furSlider.addEventListener("input", () => {
  const v = parseFloat(furSlider.value);
  if (furSystem) furSystem.setFluffiness(v);
  furVal.textContent = v < 0.05 ? "Smooth" : v < 0.5 ? "Short" : v < 0.9 ? "Plush" : "Ultra Fluffy";
});

const collarBtn = document.getElementById("collar-toggle");
collarBtn.addEventListener("click", () => {
  const vis = !collarBtn.classList.contains("active");
  collarBtn.classList.toggle("active", vis);
  collarBtn.textContent = vis ? "🔔 Collar On" : "🔕 Collar Off";
  collarObjs.forEach((o) => (o.visible = vis));
});

const pupilLockBtn = document.getElementById("pupil-lock-toggle");
pupilLockBtn.addEventListener("click", () => {
  state.bobaLocked = !state.bobaLocked;
  pupilLockBtn.classList.toggle("active", state.bobaLocked);
});

window.addEventListener("resize", () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

// ==============================================================================
// MAIN ANIMATION & PROCEDURAL LIFELIKE BEHAVIOR LOOP
// ==============================================================================
let lastFrameMs = performance.now();
let startFrameMs = lastFrameMs;

function setMorph(mesh, name, val) {
  if (!mesh || !mesh.morphTargetDictionary || !mesh.morphTargetInfluences) return;
  const idx = mesh.morphTargetDictionary[name];
  if (idx !== undefined) {
    mesh.morphTargetInfluences[idx] = Math.max(mesh.morphTargetInfluences[idx], val);
  }
}

function animate() {
  requestAnimationFrame(animate);
  const nowMs = performance.now();
  const dt = Math.min(0.05, Math.max(0.001, (nowMs - lastFrameMs) * 0.001));
  lastFrameMs = nowMs;
  const timeSec = (nowMs - startFrameMs) * 0.001;

  // Smooth Camera Preset Tween
  if (state.camTween) {
    state.camTween.t += dt / state.camTween.dur;
    const u = Math.min(1, state.camTween.t);
    const ease = u * u * (3 - 2 * u);
    camera.position.lerpVectors(state.camTween.startPos, state.camTween.endPos, ease);
    controls.target.lerpVectors(state.camTween.startTgt, state.camTween.endTgt, ease);
    if (u >= 1) state.camTween = null;
  }
  controls.update();

  // Gently drift dust motes
  motes.rotation.y = timeSec * 0.03;

  // Update Toys + Callbacks
  toys.update(
    dt,
    timeSec,
    (side) => {
      if (state.swatTimer <= 0) {
        state.swatTimer = 0.48;
        state.swatSide = side;
        audio.playMeow("chirp");
        audio.playBell(0.9);
      }
    },
    () => {
      // Treat eaten!
      state.happyTimer = 2.4;
      state.meowTimer = 0.35;
      addAffection(5);
      toys.spawnHeart(new THREE.Vector3(0, 0.25, 0.12));
      toys.spawnHeart(new THREE.Vector3(0.03, 0.28, 0.10));
      showToast("Yum!! *purr* 🐟💕");
    }
  );

  // Update Audio Purr
  state.pettingEnergy = Math.max(0, state.pettingEnergy - dt * 0.55);
  state.happyTimer = Math.max(0, state.happyTimer - dt);
  state.boopTimer = Math.max(0, state.boopTimer - dt);
  state.meowTimer = Math.max(0, state.meowTimer - dt);
  state.earTwitchL = Math.max(0, state.earTwitchL - dt * 2.8);
  state.earTwitchR = Math.max(0, state.earTwitchR - dt * 2.8);
  state.swatTimer = Math.max(0, state.swatTimer - dt);

  const purrAmt = state.happyTimer > 0 ? Math.min(1, 0.45 + state.pettingEnergy * 0.65) : (activeAnimName === "Purr_Knead" ? 0.85 : activeAnimName === "Sleepy_Nap" ? 0.35 : 0);
  audio.setPurr(purrAmt);
  audio.update(dt);

  if (furSystem) furSystem.update(timeSec);

  if (mixer && catBody) {
    mixer.update(dt);

    // 1. Autonomous Natural Blinking
    state.blinkTimer -= dt;
    if (state.blinkTimer <= 0) {
      state.blinkTimer = 2.8 + Math.random() * 3.4;
      state.blinkVal = 1.0;
    }
    state.blinkVal = Math.max(0, state.blinkVal - dt * 7.5);
    const blinkCurve = Math.sin(state.blinkVal * Math.PI);
    setMorph(catBody, "Blink_L", blinkCurve);
    setMorph(catBody, "Blink_R", blinkCurve);

    // 2. Petting Bliss & Nose Boop Morphs
    if (state.happyTimer > 0) {
      const h = Math.min(1, state.happyTimer * 1.4);
      setMorph(catBody, "Happy_Squint", h * 0.85);
      setMorph(catBody, "Cheek_Puff", h * 0.65);
    }
    if (state.boopTimer > 0) {
      const b = Math.sin((state.boopTimer / 0.75) * Math.PI);
      setMorph(catBody, "Nose_Scrunch", b * 0.95);
    }
    if (state.meowTimer > 0) {
      const m = Math.sin((state.meowTimer / 0.65) * Math.PI);
      setMorph(catBody, "Meow_Open", m * 0.85);
    }
    if (toys.treatActive && toys.treatTimer > 0.7 && toys.treatTimer < 1.8) {
      const nibble = Math.abs(Math.sin(toys.treatTimer * 14.0));
      setMorph(catBody, "Meow_Open", nibble * 0.45);
      applyWorldDeltaToBone("Head", 0.38, 0, 0);
      applyWorldDeltaToBone("Neck", 0.18, 0, 0);
    }

    // 3. Cute Tongue Blep!
    if (catTongue && catTongue.morphTargetInfluences) {
      const idxBlep = catTongue.morphTargetDictionary["Blep"];
      if (idxBlep !== undefined) {
        const cur = catTongue.morphTargetInfluences[idxBlep];
        const nextB = cur + (state.blepAmount - cur) * Math.min(1, dt * 7.0);
        catTongue.morphTargetInfluences[idxBlep] = nextB;
        if (nextB > 0.05) setMorph(catBody, "Meow_Open", Math.max(0.18 * nextB, 0));
      }
    }

    // 4. Dynamic Pupil Dilation (bright studio -> slit, playful/moonlight/boba -> big dark cute circles!)
    let targetPup = 0.25;
    if (state.bobaLocked || state.mode === "laser" || state.mode === "yarn" || state.happyTimer > 0 || state.lighting === "moonlight") {
      targetPup = 0.96;
    } else if (state.lighting === "studio") {
      targetPup = -0.35; // Sleek feline vertical slit in bright studio light!
    }
    state.pupilCurrent += (targetPup - state.pupilCurrent) * Math.min(1, dt * 5.0);
    for (const pMesh of [catPupilL, catPupilR]) {
      if (!pMesh || !pMesh.morphTargetInfluences) continue;
      const dIdx = pMesh.morphTargetDictionary["Pupil_Dilate"];
      const sIdx = pMesh.morphTargetDictionary["Pupil_Slit"];
      if (dIdx !== undefined) pMesh.morphTargetInfluences[dIdx] = Math.max(0, state.pupilCurrent);
      if (sIdx !== undefined) pMesh.morphTargetInfluences[sIdx] = Math.max(0, -state.pupilCurrent);
    }

    // 5. Real-time Eye & Head Tracking (Cursor / Laser / Yarn Ball!)
    let desiredTarget = null;
    if (state.mode === "laser" && toys.laserGroup.visible) {
      desiredTarget = toys.laserGroup.position;
    } else if (state.mode === "yarn" && toys.yarnBall.visible) {
      desiredTarget = toys.yarnBall.position;
    } else if (state.hasCursorTarget && activeAnimName !== "Sleepy_Nap") {
      desiredTarget = getCursorWorldLookTarget();
    }

    if (desiredTarget && activeAnimName !== "Sleepy_Nap") {
      state.targetLookWorld.lerp(desiredTarget, Math.min(1, dt * 8.0));
      const headOrigin = new THREE.Vector3(0, 0.295, 0.04);
      const dir = state.targetLookWorld.clone().sub(headOrigin);
      const yaw = THREE.MathUtils.clamp(Math.atan2(dir.x, Math.max(0.18, dir.z)), -0.58, 0.58);
      const pitch = THREE.MathUtils.clamp(-Math.atan2(dir.y, Math.hypot(dir.x, Math.max(0.22, dir.z))), -0.38, 0.42);
      const roll = state.isPetting ? (state.petZone === "earL" ? -0.18 : 0.14) * Math.sin(timeSec * 3.0) : -yaw * 0.18;

      applyWorldDeltaToBone("Neck", pitch * 0.35, yaw * 0.35, 0);
      applyWorldDeltaToBone("Head", pitch * 0.65, yaw * 0.65, roll);
      applyWorldDeltaToBone("Eye_L", pitch * 0.35, yaw * 0.35, 0);
      applyWorldDeltaToBone("Eye_R", pitch * 0.35, yaw * 0.35, 0);
    }

    // 6. Ear Twitch Spring & Playful Paw Swat Override!
    if (state.earTwitchL > 0.01) {
      const tw = Math.sin(state.earTwitchL * Math.PI * 3.0) * state.earTwitchL * 0.42;
      applyWorldDeltaToBone("Ear_L", -Math.abs(tw), 0, -tw * 0.6);
    }
    if (state.earTwitchR > 0.01) {
      const tw = Math.sin(state.earTwitchR * Math.PI * 3.0) * state.earTwitchR * 0.42;
      applyWorldDeltaToBone("Ear_R", -Math.abs(tw), 0, tw * 0.6);
    }
    if (state.swatTimer > 0) {
      const sw = Math.sin((state.swatTimer / 0.48) * Math.PI);
      const s = state.swatSide || "R";
      applyWorldDeltaToBone(`UpperArm_${s}`, -sw * 0.95, 0, 0);
      applyWorldDeltaToBone(`Forearm_${s}`, -sw * 0.45, 0, 0);
      applyWorldDeltaToBone(`Paw_${s}`, sw * 0.45, 0, 0);
    }

    // 7. Gentle Spring Collar Bell Pendulum!
    const bellImpulse = (state.swatTimer > 0 ? 0.5 : 0) + (state.isPetting ? 0.18 : 0) + (activeAnimName === "Playful_Wave" ? 0.4 : 0);
    const springForce = -48.0 * state.bellAngle - 5.5 * state.bellVel + Math.sin(timeSec * 14.0) * bellImpulse;
    state.bellVel += springForce * dt;
    state.bellAngle += state.bellVel * dt;
    applyWorldDeltaToBone("Collar_Bell", state.bellAngle * 0.5, 0, state.bellAngle);
  }

  renderer.render(scene, camera);
}

animate();
