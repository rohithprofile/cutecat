import * as THREE from "three";

/**
 * Interactive 3D Toys & Particle FX:
 *  - Glowing Laser Pointer dot + floor halo
 *  - Bouncy physics Yarn Ball (drag/toss, rolls, bounces off cushion & floor, swatted by paws!)
 *  - Salmon Fish Treat toss
 *  - Floating glowing Hearts / Sparkles when petted!
 */
export class CatToysAndFX {
  constructor(scene) {
    this.scene = scene;
    this.laserGroup = this._createLaserDot();
    this.yarnBall = this._createYarnBall();
    this.treatMesh = this._createTreat();
    this.particles = [];
    this.particleGeo = new THREE.SphereGeometry(0.0045, 8, 8);

    this.yarnVel = new THREE.Vector3();
    this.yarnGrabbed = false;
    this.treatActive = false;
    this.treatTimer = 0;
    this.treatPos = new THREE.Vector3();
  }

  _createLaserDot() {
    const grp = new THREE.Group();
    grp.visible = false;

    const core = new THREE.Mesh(
      new THREE.SphereGeometry(0.0055, 16, 16),
      new THREE.MeshBasicMaterial({ color: 0xff2845 })
    );
    const halo = new THREE.Mesh(
      new THREE.RingGeometry(0.007, 0.015, 24),
      new THREE.MeshBasicMaterial({
        color: 0xff445e,
        transparent: true,
        opacity: 0.55,
        side: THREE.DoubleSide,
      })
    );
    halo.rotation.x = -Math.PI / 2;

    const glow = new THREE.PointLight(0xff2040, 0.45, 0.35);
    glow.position.y = 0.012;

    grp.add(core, halo, glow);
    this.scene.add(grp);
    return grp;
  }

  _createYarnBall() {
    // Procedural textured wound yarn sphere!
    const canvas = document.createElement("canvas");
    canvas.width = 256;
    canvas.height = 256;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#e05a47";
    ctx.fillRect(0, 0, 256, 256);
    for (let i = 0; i < 160; i++) {
      ctx.strokeStyle = i % 3 === 0 ? "#c44230" : i % 3 === 1 ? "#f27b66" : "#d14d3b";
      ctx.lineWidth = 2.5 + Math.random() * 2;
      ctx.beginPath();
      const y0 = Math.random() * 256;
      ctx.moveTo(0, y0);
      ctx.bezierCurveTo(85, y0 + (Math.random() - 0.5) * 40, 170, y0 + (Math.random() - 0.5) * 40, 256, Math.random() * 256);
      ctx.stroke();
    }
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;

    const geo = new THREE.SphereGeometry(0.036, 28, 28);
    const mat = new THREE.MeshStandardMaterial({
      map: tex,
      roughness: 0.88,
      metalness: 0.0,
    });
    const ball = new THREE.Mesh(geo, mat);
    ball.castShadow = true;
    ball.receiveShadow = true;
    ball.visible = false;
    ball.position.set(0.14, 0.04, 0.16);
    ball.name = "Toy_Yarn";
    this.scene.add(ball);
    return ball;
  }

  _createTreat() {
    const grp = new THREE.Group();
    const mat = new THREE.MeshStandardMaterial({ color: 0xe38a4c, roughness: 0.6 });
    const body = new THREE.Mesh(new THREE.SphereGeometry(0.011, 14, 12), mat);
    body.scale.set(1.25, 0.55, 0.78);
    const tail = new THREE.Mesh(new THREE.ConeGeometry(0.0065, 0.012, 8), mat);
    tail.rotation.z = Math.PI / 2;
    tail.position.x = -0.013;
    grp.add(body, tail);
    grp.visible = false;
    grp.castShadow = true;
    this.scene.add(grp);
    return grp;
  }

  spawnHeart(worldPos) {
    const isHeart = Math.random() > 0.35;
    const mat = new THREE.MeshBasicMaterial({
      color: isHeart ? 0xff7799 : 0xffdf9a,
      transparent: true,
      opacity: 0.92,
    });
    const m = new THREE.Mesh(this.particleGeo, mat);
    m.position.copy(worldPos).add(
      new THREE.Vector3((Math.random() - 0.5) * 0.06, 0.02 + Math.random() * 0.03, (Math.random() - 0.5) * 0.05)
    );
    this.scene.add(m);
    this.particles.push({
      mesh: m,
      vel: new THREE.Vector3((Math.random() - 0.5) * 0.04, 0.12 + Math.random() * 0.08, (Math.random() - 0.5) * 0.04),
      age: 0,
      life: 1.0 + Math.random() * 0.5,
    });
  }

  tossTreat() {
    this.treatActive = true;
    this.treatTimer = 0;
    this.treatPos.set((Math.random() - 0.5) * 0.05, 0.18, 0.15);
    this.treatMesh.position.copy(this.treatPos);
    this.treatMesh.visible = true;
  }

  spawnYarn() {
    this.yarnBall.visible = true;
    this.yarnBall.position.set(-0.14, 0.16, 0.18);
    this.yarnVel.set(0.22, 0.12, -0.06);
  }

  hideYarn() {
    this.yarnBall.visible = false;
  }

  update(dt, timeSec, onSwatCallback, onTreatEatCallback) {
    // 1. Update particles
    for (let i = this.particles.length - 1; i >= 0; i--) {
      const p = this.particles[i];
      p.age += dt;
      if (p.age >= p.life) {
        this.scene.remove(p.mesh);
        p.mesh.material.dispose();
        this.particles.splice(i, 1);
        continue;
      }
      p.mesh.position.addScaledVector(p.vel, dt);
      const t = p.age / p.life;
      p.mesh.scale.setScalar(1.0 - t * 0.65);
      p.mesh.material.opacity = 0.9 * (1.0 - t);
    }

    // 2. Pulse laser halo
    if (this.laserGroup.visible) {
      const s = 0.85 + 0.25 * Math.sin(timeSec * 12.0);
      this.laserGroup.children[1].scale.setScalar(s);
    }

    // 3. Yarn ball physics + playful cat boundary swat!
    if (this.yarnBall.visible && !this.yarnGrabbed) {
      this.yarnVel.y -= 3.2 * dt; // gravity
      this.yarnBall.position.addScaledVector(this.yarnVel, dt);

      // Floor / cushion surface bounce
      const rFromCushion = Math.hypot(this.yarnBall.position.x, this.yarnBall.position.z + 0.025);
      const groundY = rFromCushion < 0.24 ? 0.038 : -0.022;
      if (this.yarnBall.position.y < groundY) {
        this.yarnBall.position.y = groundY;
        this.yarnVel.y = Math.abs(this.yarnVel.y) * 0.52;
        this.yarnVel.x *= 0.94;
        this.yarnVel.z *= 0.94;
      }

      // Keep yarn within reachable studio arena
      const distXZ = Math.hypot(this.yarnBall.position.x, this.yarnBall.position.z);
      if (distXZ > 0.42) {
        const nx = this.yarnBall.position.x / distXZ;
        const nz = this.yarnBall.position.z / distXZ;
        this.yarnBall.position.x = nx * 0.42;
        this.yarnBall.position.z = nz * 0.42;
        this.yarnVel.x *= -0.65;
        this.yarnVel.z *= -0.65;
      }

      // Cat body collision + playful swat when ball gets close to front paws!
      const pawDist = Math.hypot(this.yarnBall.position.x, this.yarnBall.position.z - 0.11);
      if (pawDist < 0.095 && this.yarnBall.position.y < 0.14) {
        const pushAngle = Math.atan2(this.yarnBall.position.x, this.yarnBall.position.z - 0.05);
        this.yarnVel.set(Math.sin(pushAngle) * 0.42 + (Math.random() - 0.5) * 0.15, 0.25, Math.cos(pushAngle) * 0.35 + 0.18);
        if (onSwatCallback) onSwatCallback(this.yarnBall.position.x >= 0 ? "L" : "R");
      }

      // Spin yarn visually as it rolls
      this.yarnBall.rotation.x += this.yarnVel.z * dt * 24.0;
      this.yarnBall.rotation.z -= this.yarnVel.x * dt * 24.0;
    }

    // 4. Salmon treat toss & nibble
    if (this.treatActive) {
      this.treatTimer += dt;
      if (this.treatTimer < 0.45) {
        const p = this.treatTimer / 0.45;
        this.treatMesh.position.y = 0.18 * (1 - p * p) + 0.012;
        this.treatMesh.position.z = 0.16 - 0.05 * p;
        this.treatMesh.rotation.y += dt * 8.0;
      } else if (this.treatTimer < 2.2) {
        this.treatMesh.position.y = 0.012;
        if (this.treatTimer > 1.3 && !this._treatAteTriggered) {
          this._treatAteTriggered = true;
          if (onTreatEatCallback) onTreatEatCallback();
        }
        if (this.treatTimer > 1.7) {
          const shrink = Math.max(0.01, 1.0 - (this.treatTimer - 1.7) / 0.4);
          this.treatMesh.scale.setScalar(shrink);
        }
      } else {
        this.treatActive = false;
        this._treatAteTriggered = false;
        this.treatMesh.visible = false;
        this.treatMesh.scale.setScalar(1);
      }
    }
  }
}
