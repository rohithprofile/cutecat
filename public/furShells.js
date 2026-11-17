import * as THREE from "three";

/**
 * Generates real-time 60 FPS GPU Skinned Fur Shells directly bound to Cat_Body's
 * skeleton & morphTargetInfluences so the silhouette is genuinely soft and fluffy!
 */
export function attachFurShells(catBodyMesh, baseMaterial, shellCount = 8) {
  const shells = [];
  const baseParams = {
    map: baseMaterial.map,
    normalMap: baseMaterial.normalMap,
    normalScale: baseMaterial.normalScale ? baseMaterial.normalScale.clone() : new THREE.Vector2(0.5, 0.5),
    roughness: 0.74,
    metalness: 0.0,
    sheen: 0.9,
    sheenRoughness: 0.55,
    sheenColor: new THREE.Color(0xffe0c4),
    transparent: false,
    alphaTest: 0.02,
    depthWrite: true,
    side: THREE.FrontSide,
  };

  for (let i = 1; i <= shellCount; i++) {
    const layerFrac = i / shellCount; // 0.125 .. 1.0
    const mat = new THREE.MeshPhysicalMaterial({ ...baseParams });

    const uniforms = {
      uLayerFrac: { value: layerFrac },
      uFurScale: { value: 0.85 },
      uTime: { value: 0.0 },
    };
    mat.userData.furUniforms = uniforms;
    mat.customProgramCacheKey = () => "cat-gpu-fur-shell-v1";

    mat.onBeforeCompile = (shader) => {
      shader.uniforms.uLayerFrac = uniforms.uLayerFrac;
      shader.uniforms.uFurScale = uniforms.uFurScale;
      shader.uniforms.uTime = uniforms.uTime;

      shader.vertexShader = shader.vertexShader
        .replace(
          "#include <common>",
          `#include <common>
          uniform float uLayerFrac;
          uniform float uFurScale;
          uniform float uTime;
          varying vec3 vRestPos;
          varying float vFurMask;`
        )
        .replace(
          "#include <morphtarget_vertex>",
          `#include <morphtarget_vertex>
          vRestPos = position;
          float distEyeL = length(position - vec3( 0.031, 0.300, 0.084));
          float distEyeR = length(position - vec3(-0.031, 0.300, 0.084));
          float eyeQuiet = smoothstep(0.017, 0.027, min(distEyeL, distEyeR));
          float noseQuiet = smoothstep(0.014, 0.032, length(position - vec3(0.0, 0.272, 0.104)));
          float earQuiet = 1.0 - smoothstep(0.326, 0.345, position.y) * smoothstep(0.028, 0.042, abs(position.x)) * smoothstep(0.032, 0.048, position.z);
          float cheekPlush = 1.0 + 0.45 * exp(-pow((position.y - 0.275)/0.025, 2.0)) * smoothstep(0.025, 0.055, abs(position.x));
          float chestPlush = 1.0 + 0.55 * exp(-pow((position.y - 0.195)/0.045, 2.0)) * smoothstep(0.01, 0.06, position.z);
          vFurMask = clamp(eyeQuiet * noseQuiet * earQuiet, 0.0, 1.0);
          float furShellLen = 0.0038 * uFurScale * vFurMask * max(cheekPlush, chestPlush);`
        )
        .replace(
          "#include <skinning_vertex>",
          `#include <skinning_vertex>
          vec3 nDirFur = normalize(objectNormal);
          transformed += nDirFur * (furShellLen * uLayerFrac);
          transformed.y -= 0.0009 * uLayerFrac * uLayerFrac * uFurScale * vFurMask;
          transformed.x += sin(uTime * 1.4 + vRestPos.y * 22.0 + vRestPos.z * 18.0) * 0.00022 * uLayerFrac * vFurMask;`
        );

      shader.fragmentShader = shader.fragmentShader
        .replace(
          "#include <common>",
          `#include <common>
          uniform float uLayerFrac;
          varying vec3 vRestPos;
          varying float vFurMask;

          float furHash3(vec3 p) {
            p = fract(p * 0.3183099 + 0.1);
            p *= 17.0;
            return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
          }
          float furNoise3(vec3 x) {
            vec3 i = floor(x);
            vec3 f = fract(x);
            f = f * f * (3.0 - 2.0 * f);
            return mix(
              mix(mix(furHash3(i + vec3(0,0,0)), furHash3(i + vec3(1,0,0)), f.x),
                  mix(furHash3(i + vec3(0,1,0)), furHash3(i + vec3(1,1,0)), f.x), f.y),
              mix(mix(furHash3(i + vec3(0,0,1)), furHash3(i + vec3(1,0,1)), f.x),
                  mix(furHash3(i + vec3(0,1,1)), furHash3(i + vec3(1,1,1)), f.x), f.y), f.z
            );
          }`
        )
        .replace(
          "#include <alphatest_fragment>",
          `#include <alphatest_fragment>
          if (vFurMask < 0.08) discard;
          // Anisotropic fine hair fibers stretched vertically/backward along coat flow
          vec3 sampleCoord = vec3(vRestPos.x * 460.0, vRestPos.y * 190.0, vRestPos.z * 420.0);
          float strandA = furNoise3(sampleCoord);
          float strandB = furNoise3(sampleCoord * 1.9 + vec3(3.1, 7.4, 2.8));
          float hairVal = strandA * 0.65 + strandB * 0.35;
          float cutoff = mix(0.28, 0.83, pow(uLayerFrac, 0.85));
          if (hairVal < cutoff) discard;
          // Warm undercoat-to-tip self-shadowing!
          float tipShade = mix(0.76, 1.08, uLayerFrac);
          diffuseColor.rgb *= tipShade;`
        );
    };

    const shellMesh = new THREE.SkinnedMesh(catBodyMesh.geometry, mat);
    shellMesh.name = `Cat_Fur_Shell_${i}`;
    shellMesh.castShadow = false;
    shellMesh.receiveShadow = true;
    shellMesh.frustumCulled = false;
    // Share exact skeleton & bindMatrix & morphTargetInfluences with Cat_Body!
    shellMesh.bind(catBodyMesh.skeleton, catBodyMesh.bindMatrix);
    shellMesh.morphTargetDictionary = catBodyMesh.morphTargetDictionary;
    shellMesh.morphTargetInfluences = catBodyMesh.morphTargetInfluences;

    catBodyMesh.parent.add(shellMesh);
    shells.push(shellMesh);
  }

  return {
    shells,
    setFluffiness(val) {
      for (const s of shells) {
        s.visible = val > 0.02;
        if (s.material.userData.furUniforms) {
          s.material.userData.furUniforms.uFurScale.value = val;
        }
      }
    },
    setMap(tex) {
      for (const s of shells) {
        s.material.map = tex;
        s.material.needsUpdate = true;
      }
    },
    update(timeSec) {
      for (const s of shells) {
        if (s.material.userData.furUniforms) {
          s.material.userData.furUniforms.uTime.value = timeSec;
        }
      }
    },
  };
}
