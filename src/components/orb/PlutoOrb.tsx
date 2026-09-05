"use client";

import React, { useRef, useEffect } from "react";
import * as THREE from "three";
import { PlutoState } from "@/types";
import { OrbStateLabels } from "./OrbStateLabels";

interface PlutoOrbProps {
  state: PlutoState;
  size?: number;
}

export function PlutoOrb({ state, size = 420 }: PlutoOrbProps) {
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    // Dimensions
    const width = container.clientWidth || size;
    const height = container.clientHeight || size;

    // Scene, Camera, Renderer
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.z = 8.5;

    const renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: true,
      powerPreference: "high-performance"
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // 1. PARTICLE SPHERE
    const particleCount = 3800;
    const positions = new Float32Array(particleCount * 3);
    const originalPositions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);
    const sizes = new Float32Array(particleCount);

    const baseRadius = 2.2;
    const colorRed = new THREE.Color("#ff1f2d");
    const colorRedBright = new THREE.Color("#ff5566");
    const colorRedDark = new THREE.Color("#880011");

    for (let i = 0; i < particleCount; i++) {
      // Uniform point on sphere
      const u = Math.random();
      const v = Math.random();
      const theta = u * 2.0 * Math.PI;
      const phi = Math.acos(2.0 * v - 1.0);
      const r = baseRadius + (Math.random() - 0.5) * 0.35;

      const x = r * Math.sin(phi) * Math.cos(theta);
      const y = r * Math.sin(phi) * Math.sin(theta);
      const z = r * Math.cos(phi);

      positions[i * 3] = x;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = z;

      originalPositions[i * 3] = x;
      originalPositions[i * 3 + 1] = y;
      originalPositions[i * 3 + 2] = z;

      // Color variation
      const randColor = Math.random();
      let c = colorRed;
      if (randColor > 0.85) c = colorRedBright;
      else if (randColor < 0.25) c = colorRedDark;

      colors[i * 3] = c.r;
      colors[i * 3 + 1] = c.g;
      colors[i * 3 + 2] = c.b;

      sizes[i] = Math.random() * 0.045 + 0.015;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));

    // Particle Material using radial circular sprite texture
    const canvas = document.createElement("canvas");
    canvas.width = 64;
    canvas.height = 64;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      const grad = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
      grad.addColorStop(0, "rgba(255,255,255,1)");
      grad.addColorStop(0.3, "rgba(255,31,45,0.8)");
      grad.addColorStop(0.7, "rgba(255,31,45,0.2)");
      grad.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, 64, 64);
    }
    const texture = new THREE.CanvasTexture(canvas);

    const particleMaterial = new THREE.PointsMaterial({
      size: 0.08,
      map: texture,
      vertexColors: true,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });

    const particleSphere = new THREE.Points(geometry, particleMaterial);
    scene.add(particleSphere);

    // 2. ORBITAL RINGS
    const createRing = (radius: number, tubeRadius: number, colorHex: string, rotX: number, rotY: number) => {
      const ringGeo = new THREE.TorusGeometry(radius, tubeRadius, 16, 100);
      const ringMat = new THREE.MeshBasicMaterial({
        color: new THREE.Color(colorHex),
        transparent: true,
        opacity: 0.45,
        wireframe: true,
        blending: THREE.AdditiveBlending
      });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.rotation.x = rotX;
      ring.rotation.y = rotY;
      return ring;
    };

    const ring1 = createRing(3.1, 0.008, "#ff1f2d", Math.PI / 3, Math.PI / 6);
    const ring2 = createRing(3.6, 0.006, "#ff3344", -Math.PI / 4, Math.PI / 3);
    const ring3 = createRing(4.1, 0.005, "#650b10", Math.PI / 2.2, 0);

    scene.add(ring1);
    scene.add(ring2);
    scene.add(ring3);

    // 3. INNER GLOW CORE SPHERE
    const coreGeo = new THREE.SphereGeometry(1.5, 32, 32);
    const coreMat = new THREE.MeshBasicMaterial({
      color: new THREE.Color("#ff1f2d"),
      transparent: true,
      opacity: 0.15,
      blending: THREE.AdditiveBlending
    });
    const coreMesh = new THREE.Mesh(coreGeo, coreMat);
    scene.add(coreMesh);

    // Animation variables & State tracking
    const clock = new THREE.Clock();

    const animate = () => {
      const elapsedTime = clock.getElapsedTime();

      // State dynamic parameters
      let speedMult = 0.5;
      let pulseScale = 1.0;
      let waveNoise = 0.02;

      switch (state) {
        case "listening":
          speedMult = 1.2;
          pulseScale = 1.08 + Math.sin(elapsedTime * 8) * 0.06;
          waveNoise = 0.08;
          break;
        case "thinking":
          speedMult = 2.2;
          pulseScale = 1.04 + Math.sin(elapsedTime * 12) * 0.04;
          waveNoise = 0.12;
          break;
        case "planning":
          speedMult = 1.8;
          pulseScale = 0.92;
          waveNoise = 0.04;
          break;
        case "executing":
          speedMult = 3.2;
          pulseScale = 1.15 + Math.sin(elapsedTime * 16) * 0.08;
          waveNoise = 0.18;
          break;
        case "success":
          speedMult = 1.5;
          pulseScale = 1.22;
          waveNoise = 0.05;
          break;
        case "error":
          speedMult = 0.8;
          pulseScale = 0.98 + Math.sin(elapsedTime * 20) * 0.05;
          waveNoise = 0.22;
          break;
        case "idle":
        default:
          speedMult = 0.6;
          pulseScale = 1.0 + Math.sin(elapsedTime * 2.5) * 0.03;
          waveNoise = 0.02;
          break;
      }

      // Rotate sphere & rings
      particleSphere.rotation.y = elapsedTime * 0.15 * speedMult;
      particleSphere.rotation.x = Math.sin(elapsedTime * 0.1) * 0.2;

      ring1.rotation.z = elapsedTime * 0.2 * speedMult;
      ring2.rotation.z = -elapsedTime * 0.3 * speedMult;
      ring3.rotation.y = elapsedTime * 0.15 * speedMult;

      // Scale pulse
      particleSphere.scale.set(pulseScale, pulseScale, pulseScale);
      coreMesh.scale.set(pulseScale * 0.9, pulseScale * 0.9, pulseScale * 0.9);

      // Deform particles dynamically based on noise & state
      const posAttr = geometry.attributes.position as THREE.BufferAttribute;
      const array = posAttr.array as Float32Array;

      for (let i = 0; i < particleCount; i++) {
        const ox = originalPositions[i * 3];
        const oy = originalPositions[i * 3 + 1];
        const oz = originalPositions[i * 3 + 2];

        const n = Math.sin(elapsedTime * 3 + ox * 2 + oy * 2) * waveNoise;

        array[i * 3] = ox + ox * n;
        array[i * 3 + 1] = oy + oy * n;
        array[i * 3 + 2] = oz + oz * n;
      }
      posAttr.needsUpdate = true;

      renderer.render(scene, camera);
      requestAnimationFrame(animate);
    };

    const animId = requestAnimationFrame(animate);

    // Resize Handler
    const handleResize = () => {
      if (!container) return;
      const newW = container.clientWidth || size;
      const newH = container.clientHeight || size;
      camera.aspect = newW / newH;
      camera.updateProjectionMatrix();
      renderer.setSize(newW, newH);
    };

    window.addEventListener("resize", handleResize);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", handleResize);
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      geometry.dispose();
      particleMaterial.dispose();
      renderer.dispose();
    };
  }, [state, size]);

  return (
    <div className="relative flex items-center justify-center my-2">
      {/* Background Radial Glow Effect */}
      <div
        className="absolute rounded-full pointer-events-none transition-all duration-700 blur-3xl opacity-40"
        style={{
          width: size * 0.85,
          height: size * 0.85,
          background: "radial-gradient(circle, rgba(255,31,45,0.6) 0%, rgba(101,11,16,0.2) 60%, transparent 100%)"
        }}
      />

      {/* WebGL Three.js Canvas Container */}
      <div
        ref={mountRef}
        style={{ width: size, height: size }}
        className="relative z-10 flex items-center justify-center cursor-pointer"
      />

      {/* State HUD Labels Overlay */}
      <OrbStateLabels state={state} />
    </div>
  );
}
