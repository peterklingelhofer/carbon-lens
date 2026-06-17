import { useQuery } from "@tanstack/react-query";
import Globe, { type GlobeInstance } from "globe.gl";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import * as THREE from "three";
import { api } from "../api/client";
import { qualityFromSource, snapshotEnabled, useSnapshot } from "../api/snapshot";
import { InfoTip } from "../components/InfoTip";
import { PowerMix } from "../components/PowerMix";
import { RegionForecast, RegionHistory, RegionWeather } from "../components/RegionDetail";
import { DATA_QUALITY_TIP_RICH, MARGINAL_TIP, SURPLUS_TIP } from "../copy";
import { niceKm, timeAgo } from "../lib/format";
import { intensityColor, intensityRGB, renewableRGB } from "../lib/intensity";
import { subsolarPoint } from "../lib/sun";
import { isCleanSurplus } from "../lib/surplus";

// Some browsers/machines can't create a WebGL context (hardware acceleration
// off, GPU blocklisted, headless). Detect it up front so we can show a graceful
// fallback instead of letting three.js throw and crash into the ErrorBoundary.
function webglAvailable(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return (
      !!window.WebGLRenderingContext &&
      !!(
        canvas.getContext("webgl2") ||
        canvas.getContext("webgl") ||
        canvas.getContext("experimental-webgl")
      )
    );
  } catch {
    return false;
  }
}

// A spinnable 3D globe plotting every cloud region at its real datacenter
// coordinates, glowing by carbon intensity (green = clean, red = dirty), with
// bar height = renewable share and a radar pulse per site. Data is the same
// real/estimated snapshot the dashboard uses - no continuous-surface coloring,
// so empty regions are simply dark (honest), not faked.

// Self-hosted from public/textures (copied from three-globe). Avoids three-globe's
// exports-field restriction on deep imports and any runtime CDN dependency.
const EARTH_NIGHT = "/textures/earth-night.jpg";
const EARTH_TOPOLOGY = "/textures/earth-topology.png";
const NIGHT_SKY = "/textures/night-sky.png";

// A recent global true-color mosaic from NASA GIBS (free, public domain, CORS-open),
// as one equirectangular image. We don't draw it as-is -- a shader keeps only its
// near-white pixels (clouds and ice) and drops everything else, so it reads as a
// faint cloud veil over the night Earth rather than a second opaque globe. We use
// VIIRS rather than MODIS on purpose: VIIRS's ~3000 km swath overlaps pass-to-pass,
// so its daily mosaic is gap-free, where MODIS leaves triangular inter-orbit gaps
// that would show through as bands of missing cloud. A date a couple of days back
// gives the mosaic time to fill in.
function gibsCloudUrl(): string {
  const day = new Date(Date.now() - 2 * 86_400_000).toISOString().slice(0, 10);
  const params = new URLSearchParams({
    SERVICE: "WMS",
    VERSION: "1.3.0",
    REQUEST: "GetMap",
    FORMAT: "image/jpeg",
    LAYERS: "VIIRS_SNPP_CorrectedReflectance_TrueColor",
    CRS: "EPSG:4326",
    BBOX: "-90,-180,90,180",
    WIDTH: "2048",
    HEIGHT: "1024",
    TIME: day,
  });
  return `https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?${params}`;
}

// The globe's own Earth mesh, found by matching its radius (it carries the night
// texture). We hang the cloud sphere off this mesh and reuse ITS geometry, so the
// clouds inherit the exact same UVs and world transform -- guaranteeing the cloud
// image lines up with the continents without re-deriving any rotation.
function findEarthMesh(globe: GlobeInstance): THREE.Mesh | null {
  const radius = globe.getGlobeRadius();
  let found: THREE.Mesh | null = null;
  globe.scene().traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (!mesh.isMesh) return;
    const mat = mesh.material as THREE.Material & { map?: unknown };
    if (!mat || !("map" in mat) || !mat.map) return;
    const geom = mesh.geometry as THREE.BufferGeometry;
    if (!geom.boundingSphere) geom.computeBoundingSphere();
    const r = (geom.boundingSphere?.radius ?? 0) * mesh.scale.x;
    // Skip the far larger background-sky sphere; keep the one sized like the globe.
    if (Math.abs(r - radius) < radius * 0.1) found = mesh;
  });
  return found;
}

interface GlobePoint {
  provider: string;
  region: string;
  location: string;
  grid_zone: string;
  lat: number;
  lng: number;
  intensity: number;
  renewable: number;
  source: string;
  quality?: "live" | "estimated" | "mock";
  gridLoadMw?: number | null;
  consumptionIntensity?: number;
  marginalIntensity?: number;
  powerBreakdown?: Record<string, number>;
}

// Total grid load (whole balancing authority, all consumers), formatted.
function formatLoad(mw?: number | null): string | null {
  if (mw == null) return null;
  return mw >= 1000 ? `${(mw / 1000).toFixed(1)} GW` : `${Math.round(mw)} MW`;
}

type Metric = "renewable" | "intensity";

function metricRGB(p: GlobePoint, metric: Metric): [number, number, number] {
  return metric === "renewable" ? renewableRGB(p.renewable) : intensityRGB(p.intensity);
}

// Altitude (in globe-radius units) of each beam for the selected metric.
function beamAltitude(p: GlobePoint, metric: Metric): number {
  const frac = metric === "intensity" ? Math.min(1, p.intensity / 800) : p.renewable / 100;
  return 0.04 + frac * 0.5;
}

// A tapered, open-ended beam of UNIT height whose color fades to transparent at
// the tip - it reads as a glowing light shaft, not a solid blocky cylinder. The
// height is applied per-frame via mesh.scale.y so the metric toggle just
// rescales existing meshes (no geometry rebuild).
function buildBeam(p: GlobePoint, globeRadius: number, colorMetric: Metric): THREE.Mesh {
  const radius = globeRadius * 0.0075;
  // Straight cylinder (no taper), unit height (scaled per-frame). Capped ends
  // (not open) so it reads as a filled volume: looking down from above, the
  // line of sight passes the transparent tip and lands on the full-color base
  // cap, so the beam appears filled with color rather than hollow.
  const geom = new THREE.CylinderGeometry(radius, radius, 1, 20, 8, false);
  geom.translate(0, 0.5, 0); // base at the origin (globe surface), tip near y=1

  const pos = geom.attributes.position;

  // Subtle, unique ripple on the tip so beams don't end in a perfect flat cut.
  // Build-time only (once per beam, never per frame): a gentle wave around the
  // rim with a per-beam random phase/amplitude shortens the top vertices, so
  // each beam fades out along its own uneven edge.
  const phase = Math.random() * Math.PI * 2;
  const lobes = 2 + Math.floor(Math.random() * 2); // 2–3 lobes
  const amp = 0.05 + Math.random() * 0.04;
  for (let i = 0; i < pos.count; i++) {
    const y = pos.getY(i);
    if (y <= 0.78) continue; // only the top ~fifth ripples
    const k = (y - 0.78) / 0.22; // ramp in toward the tip
    const theta = Math.atan2(pos.getZ(i), pos.getX(i));
    const wave = Math.sin(theta * lobes + phase) * 0.5 + 0.5; // 0..1
    pos.setY(i, y - wave * amp * k);
  }

  const [r, g, b] = metricRGB(p, colorMetric).map((c) => c / 255) as [number, number, number];
  const colors = new Float32Array(pos.count * 4);
  for (let i = 0; i < pos.count; i++) {
    const t = Math.min(1, Math.max(0, pos.getY(i))); // 0 base → 1 tip (unit height)
    // Full, saturated color through the lower ~⅔ of the beam, fading to
    // transparent only near the tip - so the hue reads clearly even zoomed out.
    const alpha = Math.min(1, (1 - t) * 1.5);
    colors.set([r, g, b, alpha], i * 4);
  }
  geom.setAttribute("color", new THREE.BufferAttribute(colors, 4));

  // Normal (alpha) blending preserves the true hue. Additive blending washed
  // colors toward white - yellow especially - and over the bright city-lights
  // texture. depthWrite:false keeps overlapping beams compositing cleanly.
  const mat = new THREE.MeshBasicMaterial({
    vertexColors: true,
    transparent: true,
    depthWrite: false,
    blending: THREE.NormalBlending,
    side: THREE.DoubleSide,
  });
  return new THREE.Mesh(geom, mat);
}

function useGlobePoints() {
  const { data: snapshot } = useSnapshot();
  const apiEnabled = !snapshotEnabled;

  const { data: apiRegions } = useQuery({
    queryKey: ["globe-regions"],
    queryFn: () => api.regions(),
    enabled: apiEnabled,
  });
  const { data: apiIntensities } = useQuery({
    queryKey: ["globe-intensities", apiRegions?.length ?? 0],
    queryFn: () =>
      api.carbonIntensityBatch(
        (apiRegions ?? []).map((r) => ({
          provider: r.provider,
          region: r.region,
        })),
      ),
    enabled: apiEnabled && !!apiRegions?.length,
  });

  return useMemo<GlobePoint[]>(() => {
    if (snapshot) {
      return snapshot.regions
        .map((r): GlobePoint | null => {
          const i = snapshot.intensities[`${r.provider}/${r.region}`];
          if (!i) return null;
          return {
            provider: r.provider,
            region: r.region,
            location: r.location,
            grid_zone: r.grid_zone,
            lat: r.latitude,
            lng: r.longitude,
            intensity: i.carbon_intensity_gco2_kwh,
            renewable: i.renewable_percentage,
            source: i.source,
            quality: i.quality ?? qualityFromSource(i.source),
            gridLoadMw: i.grid_load_mw,
            consumptionIntensity: i.consumption_intensity_gco2_kwh,
            marginalIntensity: i.marginal_intensity_gco2_kwh ?? undefined,
            powerBreakdown: i.power_breakdown_mw,
          };
        })
        .filter((p): p is GlobePoint => p !== null);
    }
    if (apiRegions && apiIntensities) {
      return apiRegions
        .map((r): GlobePoint | null => {
          const i = apiIntensities[`${r.provider}/${r.region}`];
          if (!i) return null;
          return {
            provider: r.provider,
            region: r.region,
            location: r.location,
            grid_zone: r.grid_zone,
            lat: r.latitude,
            lng: r.longitude,
            intensity: i.carbon_intensity_gco2_kwh,
            renewable: i.renewable_percentage,
            source: i.source,
            quality: i.quality ?? qualityFromSource(i.source),
            gridLoadMw: i.grid_load_mw,
            consumptionIntensity: i.consumption_intensity_gco2_kwh,
            marginalIntensity: i.marginal_intensity_gco2_kwh ?? undefined,
            powerBreakdown: i.power_breakdown_mw,
          };
        })
        .filter((p): p is GlobePoint => p !== null);
    }
    return [];
  }, [snapshot, apiRegions, apiIntensities]);
}

// Shared width so the metric toggles and the colour legend always line up.
const PANEL_W = 250;
const EARTH_KM = 6371; // mean Earth radius - globe radius (world units) maps to this
// Radial height of a full (max-value) beam, in globe-radius units (= beamAltitude max).
const MAX_BEAM_ALT = 0.04 + 0.5;

// Round to a "nice" 1 / 2 / 5 × 10^n value for the map scale bar.
function MetricToggle({
  label,
  value,
  onChange,
  tip,
}: {
  label: string;
  value: Metric;
  onChange: (m: Metric) => void;
  tip?: string;
}) {
  return (
    <div style={{ marginBottom: 4 }}>
      <div
        style={{
          fontSize: "0.64rem",
          color: "#94a3b8",
          marginBottom: 3,
          textTransform: "uppercase",
          letterSpacing: "0.04em",
          display: "inline-flex",
          alignItems: "center",
        }}
      >
        {label}
        {tip && <InfoTip label={label} text={tip} placement="top" />}
      </div>
      <div
        style={{
          display: "flex",
          width: PANEL_W,
          border: "1px solid rgba(255,255,255,0.2)",
          borderRadius: 6,
          overflow: "hidden",
          background: "rgba(10,15,20,0.6)",
        }}
      >
        {(["renewable", "intensity"] as Metric[]).map((m) => (
          <button
            type="button"
            key={m}
            onClick={() => onChange(m)}
            style={{
              flex: 1,
              textAlign: "center",
              whiteSpace: "nowrap",
              border: "none",
              cursor: "pointer",
              padding: "3px 6px",
              fontSize: "0.68rem",
              // Constant weight - the green fill signals "active", so we don't
              // bold (which would widen the text and wrap it to two lines).
              fontWeight: 500,
              background: value === m ? "var(--btn-green)" : "transparent",
              color: value === m ? "#fff" : "#cbd5e1",
            }}
          >
            {m === "renewable" ? "Renewable %" : "Carbon intensity"}
          </button>
        ))}
      </div>
    </div>
  );
}

// A minimal one-line layer switch (icon + label), struck through and dimmed when
// off. Used for the cloud and daylight overlays in the legend.
function LayerToggle({
  on,
  onToggle,
  icon,
  label,
  title,
}: {
  on: boolean;
  onToggle: () => void;
  icon: string;
  label: string;
  title: string;
}) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onToggle}
      title={title}
      style={{
        background: "none",
        border: "none",
        cursor: "pointer",
        padding: 0,
        whiteSpace: "nowrap",
        fontSize: "0.62rem",
        lineHeight: 1.1,
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        color: on ? "#cbd5e1" : "#64748b",
        textDecoration: on ? "none" : "line-through",
      }}
    >
      <span aria-hidden>{icon}</span> {label}
    </button>
  );
}

export default function CarbonGlobe() {
  const containerRef = useRef<HTMLDivElement>(null);
  const globeRef = useRef<GlobeInstance | null>(null);
  const points = useGlobePoints();
  const { data: snapshot, isError: dataError } = useSnapshot();
  const [selected, setSelected] = useState<GlobePoint | null>(null);
  // Default to a BIVARIATE view: colour = carbon intensity (the rigorous metric -
  // lower gCO₂/kWh is genuinely cleaner, nuclear included), height = renewable %.
  // Two channels, two variables - not the same thing shown twice.
  const [heightMetric, setHeightMetric] = useState<Metric>("renewable");
  const [colorMetric, setColorMetric] = useState<Metric>("intensity");
  // Map scale + beam reference, recomputed as the camera zooms (shared px↔km basis):
  //   km / px  = the distance scale bar
  //   beamPx   = on-screen length of a full (100%) beam at this zoom
  const [scale, setScale] = useState<{
    km: number;
    px: number;
    beamPx: number;
  } | null>(null);
  // Set when WebGL can't be created - we render a fallback instead of the globe.
  // Probed lazily on mount so the fallback shows on the first render, with the
  // try/catch below as a backup for context-lost-after-probe.
  const [webglError, setWebglError] = useState(() => !webglAvailable());
  // The bottom-left legend is collapsed by default on small screens (it's tall);
  // a toggle expands it. Open by default on desktop.
  const [legendOpen, setLegendOpen] = useState(
    () => typeof window === "undefined" || !window.matchMedia("(max-width: 720px)").matches,
  );

  // Read inside globe.gl accessors so a toggle takes effect without re-init.
  const heightMetricRef = useRef<Metric>(heightMetric);
  const colorMetricRef = useRef<Metric>(colorMetric);

  // Layer toggles. Both meshes come up asynchronously (clouds load over the network;
  // daylight is revealed on globe-ready), so each toggle drives a ref the reveal path
  // reads for its initial state, plus a live effect that flips visibility after.
  const [showClouds, setShowClouds] = useState(true);
  const showCloudsRef = useRef(true);
  const cloudMeshRef = useRef<THREE.Mesh | null>(null);
  const [showSolar, setShowSolar] = useState(true);
  const showSolarRef = useRef(true);
  const sunMeshRef = useRef<THREE.Mesh | null>(null);

  // Instantiate the globe once.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    // Initial state already reflects the probe; just skip globe init if no WebGL.
    if (!webglAvailable()) return;

    let globe: GlobeInstance;
    try {
      globe = new Globe(el);
    } catch {
      // WebGL context creation failed even though the probe passed (e.g. context
      // lost / driver exhausted) - fall back gracefully rather than crash. This
      // is a one-shot error path, not a cascading-render risk.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setWebglError(true);
      return;
    }
    globe
      .globeImageUrl(EARTH_NIGHT)
      .bumpImageUrl(EARTH_TOPOLOGY)
      .backgroundImageUrl(NIGHT_SKY)
      .showAtmosphere(true)
      .atmosphereColor("#3a9efd")
      .atmosphereAltitude(0.18)
      // Points are invisible - they exist only as hover/click hit-targets that
      // span each beam. The visible beams are the custom layer below.
      .pointLat("lat")
      .pointLng("lng")
      .pointAltitude((d) => beamAltitude(d as GlobePoint, heightMetricRef.current))
      .pointRadius(0.5)
      .pointColor(() => "rgba(255,255,255,0)")
      .pointsMerge(false)
      .pointLabel((d) => {
        const p = d as GlobePoint;
        const tag =
          p.quality === "estimated"
            ? '<span style="color:#fbbf24">estimated · intermittent upstream</span>'
            : '<span style="color:#4ade80">live grid data</span>';
        return `
          <div style="font-family:system-ui;background:rgba(10,15,20,0.92);border:1px solid rgba(255,255,255,0.15);border-radius:8px;padding:8px 10px;color:#fff;font-size:12px;min-width:180px">
            <div style="font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:#9ca3af;font-size:10px">${p.provider} · ${p.region}</div>
            <div style="margin:2px 0 6px;color:#d1d5db">${p.location} <span style="color:#6b7280">(${p.grid_zone})</span></div>
            <div style="font-size:18px;font-weight:700;color:${intensityColor(p.intensity)}">${p.intensity} <span style="font-size:11px;font-weight:400;color:#9ca3af">gCO₂/kWh</span></div>
            <div style="color:#86efac">${p.renewable}% renewable</div>
            ${p.marginalIntensity != null ? `<div style="color:#cbd5e1">Marginal ~${p.marginalIntensity} <span style="font-size:11px;color:#9ca3af">gCO₂/kWh · extra kWh now</span></div>` : ""}
            ${formatLoad(p.gridLoadMw) ? `<div style="color:#93c5fd">Grid load: ${formatLoad(p.gridLoadMw)} <span style="color:#6b7280">(whole grid)</span></div>` : ""}
            <div style="margin-top:4px;font-size:10px">${tag}</div>
          </div>`;
      })
      .ringLat("lat")
      .ringLng("lng")
      .ringMaxRadius((d) => 2 + ((d as GlobePoint).renewable / 100) * 3)
      .ringPropagationSpeed(1.4)
      .ringRepeatPeriod((d: object) => 2400 - ((d as GlobePoint).renewable / 100) * 1400)
      .ringColor((d: object) => {
        const [r, g, b] = metricRGB(d as GlobePoint, colorMetricRef.current);
        return (t: number) => `rgba(${r},${g},${b},${Math.sqrt(1 - t)})`;
      })
      .onPointClick((d: object) => {
        const p = d as GlobePoint;
        setSelected(p);
        globe.pointOfView({ lat: p.lat, lng: p.lng, altitude: 1.6 }, 900);
      })
      // Glowing light-shaft beams (replaces the blocky default cylinders).
      .customThreeObject((d: object) =>
        buildBeam(d as GlobePoint, globe.getGlobeRadius(), colorMetricRef.current),
      )
      .customThreeObjectUpdate((obj: object, d: object) => {
        const p = d as GlobePoint;
        const mesh = obj as THREE.Mesh;
        const c = globe.getCoords(p.lat, p.lng, 0); // base on the surface
        mesh.position.set(c.x, c.y, c.z);
        // Orient the beam (+Y) radially outward from the globe center.
        const radial = new THREE.Vector3(c.x, c.y, c.z).normalize();
        mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), radial);
        // Scale unit-height beam to the selected metric's altitude.
        mesh.scale.y = beamAltitude(p, heightMetricRef.current) * globe.getGlobeRadius();
        // Recolor in place (keeps the per-vertex alpha gradient) so the color
        // metric toggle updates without rebuilding geometry.
        const colorAttr = (mesh.geometry as THREE.BufferGeometry).getAttribute(
          "color",
        ) as THREE.BufferAttribute;
        const [cr, cg, cb] = metricRGB(p, colorMetricRef.current).map((c) => c / 255);
        for (let i = 0; i < colorAttr.count; i++) colorAttr.setXYZ(i, cr, cg, cb);
        colorAttr.needsUpdate = true;
      });

    globe.width(el.clientWidth).height(el.clientHeight);
    const controls = globe.controls() as {
      autoRotate: boolean;
      autoRotateSpeed: number;
      enableZoom: boolean;
    };
    controls.autoRotateSpeed = 0.55;
    controls.enableZoom = true;

    // Capture mode: `?lng=120` (optionally &lat=&alt=) freezes the camera at an
    // exact longitude, so screenshot frames have perfectly uniform rotation for
    // building a smooth GIF. With no params, the live app auto-rotates.
    const params = new URLSearchParams(window.location.search);
    const capLng = params.get("lng");
    if (capLng !== null) {
      controls.autoRotate = false;
      globe.pointOfView({
        lat: parseFloat(params.get("lat") ?? "12"),
        lng: parseFloat(capLng),
        altitude: parseFloat(params.get("alt") ?? "2.9"),
      });
    } else {
      controls.autoRotate = true;
      globe.pointOfView({ lat: 25, lng: 0, altitude: 2.4 });
    }

    globeRef.current = globe;

    // Kill the globe's specular highlight: the default Phong material throws a
    // camera-relative glare on the surface, which now reads as wrong next to the
    // physically-placed daylight. Matte the surface so only our daylight lights it.
    const globeMat = globe.globeMaterial() as THREE.MeshPhongMaterial;
    if (globeMat && "shininess" in globeMat) {
      globeMat.specular = new THREE.Color(0x000000);
      globeMat.shininess = 0;
      globeMat.needsUpdate = true;
    }

    // Soft daylight: a thin transparent overlay sphere whose warmth follows the
    // real irradiance falloff -- brightest where the sun is overhead and fading by
    // cos(solar zenith) to nothing at the day/night edge. dot(surfaceNormal, sunDir)
    // IS that cosine, so the shader is just that, additively blended and subtle.
    const sunMat = new THREE.ShaderMaterial({
      uniforms: {
        uSunDir: { value: new THREE.Vector3(1, 0, 0) },
        uColor: { value: new THREE.Color(0xffe7a0) },
        uMaxAlpha: { value: 0.18 },
        uFalloff: { value: 1.4 },
      },
      vertexShader: `
        varying vec3 vNormalW;
        void main() {
          vNormalW = normalize(mat3(modelMatrix) * normal);
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }`,
      fragmentShader: `
        uniform vec3 uSunDir; uniform vec3 uColor; uniform float uMaxAlpha; uniform float uFalloff;
        varying vec3 vNormalW;
        void main() {
          float c = max(0.0, dot(normalize(vNormalW), normalize(uSunDir)));
          gl_FragColor = vec4(uColor, pow(c, uFalloff) * uMaxAlpha);
        }`,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      side: THREE.FrontSide,
    });
    const sunMesh = new THREE.Mesh(
      new THREE.SphereGeometry(globe.getGlobeRadius() * 1.002, 64, 48),
      sunMat,
    );
    // Hidden until the globe texture is ready, so the daylight never shows before
    // the Earth it's meant to be lighting (no cart before the horse on spawn).
    sunMesh.visible = false;
    globe.scene().add(sunMesh);

    // Faint cloud veil: a near-real-time NASA mosaic kept only where it's white
    // (clouds and ice), drawn on a thin concentric shell over the Earth. Built once
    // the globe is ready (so the Earth mesh exists to hang it off and reuse its UVs)
    // and only after the image loads -- if NASA is unreachable, the globe is fine
    // without it. `disposed` guards the async load against an unmount mid-flight.
    let disposed = false;
    let cloudMesh: THREE.Mesh | null = null;
    let cloudMat: THREE.ShaderMaterial | null = null;
    let cloudTex: THREE.Texture | null = null;
    const addClouds = () => {
      new THREE.TextureLoader().load(
        gibsCloudUrl(),
        (tex) => {
          const earth = findEarthMesh(globe);
          if (disposed || !earth) {
            tex.dispose();
            return;
          }
          cloudTex = tex;
          cloudMat = new THREE.ShaderMaterial({
            uniforms: { uClouds: { value: tex }, uOpacity: { value: 0.08 } },
            vertexShader: `
              varying vec2 vUv;
              void main() {
                vUv = uv;
                gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
              }`,
            fragmentShader: `
              uniform sampler2D uClouds; uniform float uOpacity;
              varying vec2 vUv;
              void main() {
                vec3 c = texture2D(uClouds, vUv).rgb;
                // The achromatic floor: high only for white/grey (clouds, ice),
                // low for coloured land and dark ocean / no-data gaps.
                float white = min(c.r, min(c.g, c.b));
                float a = smoothstep(0.5, 0.85, white) * uOpacity;
                // The daily true-color mosaic is daytime only, so a winter pole is
                // black no-data ending in a ragged, scalloped terminator. Rather than
                // fade at a fixed latitude (which leaves a hard step wherever the
                // ragged edge actually falls), sample poleward and dissolve the cloud
                // INTO the void: the more no-data sits just toward the pole, the more
                // this pixel fades. Gated to high latitude so the gap-free rest of the
                // globe is untouched.
                float lat = (vUv.y - 0.5) * 180.0;
                float poleDir = sign(lat);
                float voidNear = 0.0;
                for (int k = 1; k <= 5; k++) {
                  vec2 suv = vec2(vUv.x, vUv.y + poleDir * float(k) * 0.010);
                  vec3 sc = texture2D(uClouds, suv).rgb;
                  voidNear += 1.0 - step(0.04, min(sc.r, min(sc.g, sc.b)));
                }
                voidNear = (voidNear / 5.0) * smoothstep(38.0, 55.0, abs(lat));
                a *= 1.0 - voidNear;
                gl_FragColor = vec4(vec3(1.0), a);
              }`,
            transparent: true,
            depthWrite: false,
            side: THREE.FrontSide,
          });
          // Reuse the Earth's geometry/UVs; a hair larger so it sits just above the
          // surface. As a child of the Earth mesh it inherits the same transform.
          cloudMesh = new THREE.Mesh(earth.geometry, cloudMat);
          cloudMesh.scale.setScalar(1.003);
          cloudMesh.renderOrder = 1;
          cloudMesh.visible = showCloudsRef.current;
          cloudMeshRef.current = cloudMesh;
          earth.add(cloudMesh);
        },
        undefined,
        () => {
          // NASA unreachable / blocked -- skip clouds silently, keep the globe.
        },
      );
    };

    globe.onGlobeReady(() => {
      sunMesh.visible = showSolarRef.current;
      sunMeshRef.current = sunMesh;
      addClouds();
    });

    // Point the daylight at the subsolar point; refresh each minute (~15°/h).
    const refreshSun = () => {
      const s = subsolarPoint(new Date());
      const c = globe.getCoords(s.lat, s.lng, 0);
      sunMat.uniforms.uSunDir.value.set(c.x, c.y, c.z).normalize();
    };
    refreshSun();
    const sunTimer = setInterval(refreshSun, 60_000);

    // Map scale bar: measure how many km a screen pixel covers near the view
    // centre (1° of latitude ≈ 111.32 km), then pick a nice round distance.
    const computeScale = () => {
      const pov = globe.pointOfView();
      const a = globe.getScreenCoords(pov.lat, pov.lng, 0);
      const b = globe.getScreenCoords(pov.lat + 1, pov.lng, 0);
      if (!a || !b) return;
      const px = Math.hypot(b.x - a.x, b.y - a.y);
      if (!px || !Number.isFinite(px)) return;
      const kmPerPx = 111.32 / px;
      const km = niceKm(70 * kmPerPx); // aim for a ~70px bar
      // A full beam's radial height (MAX_BEAM_ALT × Earth radius) measured in the
      // same km↔px basis, so the height ruler and the distance bar track zoom together.
      const beamPx = (MAX_BEAM_ALT * EARTH_KM) / kmPerPx;
      setScale({ km, px: km / kmPerPx, beamPx });
    };
    globe.onZoom(() => computeScale());
    const scaleTimer = setTimeout(computeScale, 250);

    const onResize = () => {
      globe.width(el.clientWidth).height(el.clientHeight);
      computeScale();
    };
    window.addEventListener("resize", onResize);

    // Pause auto-rotation while the user is interacting; resume after.
    let resumeTimer: ReturnType<typeof setTimeout>;
    const pause = () => {
      controls.autoRotate = false;
      clearTimeout(resumeTimer);
      resumeTimer = setTimeout(() => {
        controls.autoRotate = true;
      }, 3500);
    };
    el.addEventListener("pointerdown", pause);

    return () => {
      window.removeEventListener("resize", onResize);
      el.removeEventListener("pointerdown", pause);
      clearTimeout(resumeTimer);
      clearTimeout(scaleTimer);
      clearInterval(sunTimer);
      globe.scene().remove(sunMesh);
      sunMesh.geometry.dispose();
      sunMat.dispose();
      // Tear down the cloud shell if it loaded; guard the in-flight load too. Do
      // NOT dispose its geometry -- it's the Earth mesh's, shared and still in use.
      disposed = true;
      cloudMeshRef.current = null;
      sunMeshRef.current = null;
      if (cloudMesh) cloudMesh.removeFromParent();
      cloudMat?.dispose();
      cloudTex?.dispose();
      globe._destructor?.();
      el.replaceChildren();
    };
  }, []);

  // Feed data into the globe whenever the data OR the selected metric changes.
  // The globe.gl accessors read the metric refs, and they only re-run when the
  // layer data is re-digested -- so a metric toggle must re-feed here too, or the
  // beams never rescale/recolor. We sync the refs first so the re-digest below
  // reads the new metric.
  useEffect(() => {
    const globe = globeRef.current;
    if (!globe) return;
    heightMetricRef.current = heightMetric;
    colorMetricRef.current = colorMetric;
    // Fresh array copies force globe.gl to re-digest, so the accessors re-read
    // the metric refs: beams rescale (height) and recolor (color), rings and
    // hit-targets update too.
    globe
      .pointsData([...(points as object[])])
      .ringsData([...(points as object[])])
      .customLayerData([...(points as object[])]);
  }, [points, heightMetric, colorMetric]);

  // Toggle the cloud veil. The mesh may not have loaded yet, so also stash the
  // desired state in a ref the loader reads when it finishes.
  useEffect(() => {
    showCloudsRef.current = showClouds;
    if (cloudMeshRef.current) cloudMeshRef.current.visible = showClouds;
  }, [showClouds]);

  // Toggle the daylight glow. sunMeshRef is set only on globe-ready, so flipping it
  // here can't reveal the daylight before the globe (the ref is null until then).
  useEffect(() => {
    showSolarRef.current = showSolar;
    if (sunMeshRef.current) sunMeshRef.current.visible = showSolar;
  }, [showSolar]);

  const liveCount = points.filter((p) => p.quality === "live").length;
  const estCount = points.filter((p) => p.quality === "estimated").length;
  // `?bare` hides the overlays - used only for capturing clean globe screenshots.
  const bare = typeof window !== "undefined" && window.location.search.includes("bare");

  // Height ruler geometry - a 100% beam's true on-screen length at this zoom.
  // The bar is drawn at that length but capped to the panel; ticks beyond the
  // panel are dropped and a "+" marks that the full 100% sits off-panel.
  const beamPx = scale?.beamPx ?? PANEL_W;
  const heightBarW = Math.min(beamPx, PANEL_W);
  const heightCapped = beamPx > PANEL_W + 1;
  // Pick a nice tick step for the *visible* value range so 4–6 labels always
  // span the bar - even when it's capped and only a slice of the beam shows.
  const heightMax = heightMetric === "renewable" ? 100 : 800; // value at full beam
  const heightSteps = heightMetric === "renewable" ? [2, 5, 10, 25, 50] : [25, 50, 100, 200, 400];
  const heightVisibleMax = heightMax * Math.min(1, PANEL_W / beamPx);
  const heightStep =
    heightSteps.find((s) => heightVisibleMax / s <= 6) ?? heightSteps[heightSteps.length - 1];
  const heightTicks: { label: string; pos: number }[] = [];
  for (let v = 0; v <= heightVisibleMax + 0.5; v += heightStep) {
    const pos = (beamPx * v) / heightMax;
    if (pos > PANEL_W + 0.5) break;
    heightTicks.push({
      label: heightMetric === "intensity" && v >= heightMax ? `${v}+` : `${v}`,
      pos,
    });
  }

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "calc(100vh - 56px)",
        background: "#000",
        overflow: "hidden",
      }}
    >
      <style>{`
        .globe-legend-toggle { display: none; }
        /* Description-in-tooltip swap: the long description shows as text on desktop;
           on mobile it's hidden and folded into the mobile info icon. */
        .globe-tip-mobile { display: none; }
        @media (max-width: 720px) {
          .globe-links-inline { display: none; }
          /* Title: trim to essentials so it doesn't dominate a phone screen */
          .globe-title { max-width: 78vw; }
          .globe-title p { font-size: 0.74rem !important; }
          .globe-title-desc { display: none; }
          .globe-tip-desktop { display: none; }
          .globe-tip-mobile { display: inline-flex; align-items: center; }
          /* Legend: collapse behind a toggle; hide everything but the toggle when closed */
          .globe-legend-toggle {
            display: inline-flex; align-items: center; gap: 4px;
            background: rgba(10,15,20,0.7); color: #cbd5e1;
            border: 1px solid rgba(255,255,255,0.2); border-radius: 6px;
            font-size: 0.72rem; padding: 4px 9px; cursor: pointer; pointer-events: auto;
          }
          /* Collapsed: show only the toggle, hide every other legend element. */
          .globe-legend:not(.open) > *:not(.globe-legend-toggle) { display: none !important; }
          /* Detail panel: full-width sheet near the top instead of a floating box */
          .globe-detail {
            left: 12px !important; right: 12px !important; width: auto !important;
            max-height: 55vh; overflow: auto;
          }
        }
      `}</style>
      <div ref={containerRef} style={{ position: "absolute", inset: 0 }} />

      {/* WebGL unavailable - graceful fallback instead of a crashed page */}
      {webglError && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "2rem",
            textAlign: "center",
          }}
        >
          <div style={{ maxWidth: 540, color: "#cbd5e1" }}>
            <div style={{ fontSize: "2.5rem", marginBottom: "0.5rem" }} aria-hidden>
              🌐
            </div>
            <h1
              style={{
                color: "#fff",
                margin: "0 0 0.5rem",
                fontSize: "1.4rem",
              }}
            >
              The 3D globe needs WebGL
            </h1>
            <p
              style={{
                fontSize: "0.95rem",
                lineHeight: 1.6,
                margin: "0 0 0.75rem",
              }}
            >
              Your browser couldn't start WebGL, so the interactive globe can't render here. This
              usually means hardware acceleration is turned off, or your browser or GPU has it
              blocked.
            </p>
            <p
              style={{
                fontSize: "0.9rem",
                lineHeight: 1.6,
                color: "#94a3b8",
                margin: "0 0 1.25rem",
              }}
            >
              Try enabling hardware acceleration in your browser settings, updating your browser, or
              opening this in Chrome. The same live data is available as a table:
            </p>
            <Link
              to="/dashboard"
              style={{
                display: "inline-block",
                padding: "0.7rem 1.75rem",
                borderRadius: 8,
                background: "var(--btn-green)",
                color: "#fff",
                fontWeight: 600,
                textDecoration: "none",
              }}
            >
              View the Grid Data dashboard →
            </Link>
          </div>
        </div>
      )}

      {/* Title overlay */}
      <div
        className="globe-title"
        style={{
          position: "absolute",
          top: 20,
          left: 24,
          color: "#fff",
          pointerEvents: "none",
          textShadow: "0 1px 8px rgba(0,0,0,0.8)",
          display: bare || webglError ? "none" : undefined,
        }}
      >
        {/* Visually hidden - kept for the document outline / screen readers. */}
        <h1
          style={{
            position: "absolute",
            width: 1,
            height: 1,
            padding: 0,
            margin: -1,
            overflow: "hidden",
            clip: "rect(0,0,0,0)",
            whiteSpace: "nowrap",
            border: 0,
          }}
        >
          Carbon Globe
        </h1>
        <p
          className="globe-title-desc"
          style={{
            margin: 0,
            fontSize: "0.85rem",
            color: "#cbd5e1",
            maxWidth: 380,
          }}
        >
          {points.length} cloud regions by live grid carbon intensity and renewable share. Drag to
          spin, scroll to zoom, hover a node for detail.
        </p>
        {points.length > 0 && (
          <p
            style={{
              margin: "6px 0 0",
              fontSize: "0.75rem",
              color: "#94a3b8",
              pointerEvents: "auto",
              display: "inline-flex",
              alignItems: "center",
            }}
          >
            <span style={{ color: "#4ade80" }}>● {liveCount} live</span>
            {estCount > 0 && (
              <span style={{ color: "#fbbf24", marginLeft: 10 }}>● {estCount} estimated</span>
            )}
            {/* Desktop: the description is shown above, so this icon only explains live vs estimated. */}
            <span className="globe-tip-desktop">
              <InfoTip label="live vs estimated" text={DATA_QUALITY_TIP_RICH} placement="bottom" />
            </span>
            {/* Mobile: the description is hidden to declutter, so it's folded into this icon. */}
            <span className="globe-tip-mobile">
              <InfoTip
                label="about this view"
                text={
                  <>
                    Drag to spin, tap a node for detail.
                    <br />
                    <br />
                    {DATA_QUALITY_TIP_RICH}
                  </>
                }
                placement="bottom"
              />
            </span>
          </p>
        )}
        {snapshot && (
          <p style={{ margin: "3px 0 0", fontSize: "0.7rem", color: "#64748b" }}>
            Data updated {timeAgo(snapshot.generated_at)}
          </p>
        )}
        {/* Always-available text alternative - for keyboard, screen-reader and
            colour-vision users who can't read the colour-coded beams. Hidden on
            mobile to declutter; both destinations live in the nav (Grid Data,
            Methodology), and the no-WebGL fallback keeps its own table link. */}
        <p
          className="globe-links-inline"
          style={{
            margin: "6px 0 0",
            pointerEvents: "auto",
            fontSize: "0.72rem",
          }}
        >
          <Link to="/dashboard" style={{ color: "#7dd3fc", textDecoration: "underline" }}>
            View as a table →
          </Link>
          <Link
            to="/methodology"
            style={{
              color: "#7dd3fc",
              textDecoration: "underline",
              marginLeft: 12,
            }}
          >
            Methodology
          </Link>
        </p>
      </div>

      {/* Controls + legend (bottom-left) */}
      <div
        className={`globe-legend${legendOpen ? " open" : ""}`}
        style={{
          position: "absolute",
          bottom: 24,
          left: 24,
          color: "#fff",
          fontSize: "0.7rem",
          textShadow: "0 1px 6px rgba(0,0,0,0.8)",
          display: bare || webglError ? "none" : undefined,
        }}
      >
        {/* Collapse toggle - visible only on small screens (CSS); sits above the
            keys so collapsing it reclaims the vertical space they take. */}
        <button
          type="button"
          className="globe-legend-toggle"
          aria-expanded={legendOpen}
          onClick={() => setLegendOpen((o) => !o)}
          style={{ marginBottom: legendOpen ? 8 : 0 }}
        >
          {legendOpen ? "▾ Hide legend" : "▸ Legend"}
        </button>
        {/* Color: control + its legend (a gradient) */}
        <MetricToggle
          label="Color"
          value={colorMetric}
          onChange={setColorMetric}
          tip={
            colorMetric === "intensity"
              ? "Beam colour shows carbon intensity - gCO₂/kWh, grams of CO₂ per kilowatt-hour of electricity. Green = lower (cleaner), red = higher (dirtier)."
              : "Beam colour shows renewable share - the % from renewables (wind, solar, hydro) right now; greener = higher. Note: this excludes nuclear, so a clean nuclear/hydro grid (France, Sweden) can read low here yet still emit very little CO₂. Carbon intensity is the better 'how clean' measure."
          }
        />
        {colorMetric === "intensity" ? (
          <>
            <div
              style={{
                width: PANEL_W,
                height: 12,
                borderRadius: 6,
                background: "linear-gradient(90deg,#22c55e,#84cc16,#eab308,#f97316,#ef4444)",
              }}
            />
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                width: PANEL_W,
                marginTop: 2,
                marginBottom: 12,
                color: "#94a3b8",
              }}
            >
              <span>0 (greener)</span>
              <span>500+ gCO₂ (dirtier)</span>
            </div>
          </>
        ) : (
          <>
            <div
              style={{
                width: PANEL_W,
                height: 12,
                borderRadius: 6,
                background: "linear-gradient(90deg,#ef4444,#f97316,#eab308,#84cc16,#22c55e)",
              }}
            />
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                width: PANEL_W,
                marginTop: 2,
                marginBottom: 12,
                color: "#94a3b8",
              }}
            >
              <span>0% (dirtier)</span>
              <span>100% (greener)</span>
            </div>
          </>
        )}

        {/* Height: control + its legend (a beam laid flat, with a measurable scale) */}
        <MetricToggle
          label="Height"
          value={heightMetric}
          onChange={setHeightMetric}
          tip={
            heightMetric === "renewable"
              ? "Beam height shows renewable share. Compare a beam to the scale below to read its value - a full-height beam ≈ 100%, flat ≈ 0%. On a globe on-screen height also depends on where a beam sits, so it's approximate."
              : "Beam height shows carbon intensity (gCO₂/kWh). Compare a beam to the scale below to read its value - a full-height beam ≈ 800+ gCO₂/kWh, flat ≈ 0. On a globe on-screen height also depends on where a beam sits, so it's approximate."
          }
        />
        {/* A full beam laid flat at its true on-screen length - lay a beam against it. */}
        <div aria-hidden style={{ position: "relative", width: PANEL_W, height: 12 }}>
          <div
            style={{
              position: "absolute",
              left: 0,
              top: 0,
              width: heightBarW,
              height: 12,
              borderRadius: 6,
              background: heightCapped
                ? "#e2e8f0"
                : "linear-gradient(to right, #e2e8f0, #e2e8f0 70%, rgba(226,232,240,0.12))",
            }}
          />
          {heightTicks.map((t) => (
            <div
              key={t.label}
              style={{
                position: "absolute",
                left: t.pos,
                top: -2,
                width: 1,
                height: 16,
                background: "rgba(148,163,184,0.75)",
              }}
            />
          ))}
          {heightCapped && (
            <span
              style={{
                position: "absolute",
                left: PANEL_W + 3,
                top: -1,
                fontSize: "0.7rem",
                color: "#94a3b8",
              }}
            >
              +
            </span>
          )}
        </div>
        <div
          style={{
            position: "relative",
            width: PANEL_W,
            height: 12,
            marginTop: 3,
          }}
        >
          {heightTicks.map((t) => (
            <span
              key={t.label}
              style={{
                position: "absolute",
                left: t.pos,
                transform: t.pos === 0 ? "none" : "translateX(-50%)",
                fontSize: "0.58rem",
                color: "#94a3b8",
              }}
            >
              {t.label}
            </span>
          ))}
        </div>
        <div
          style={{
            width: PANEL_W,
            marginTop: 1,
            fontSize: "0.58rem",
            color: "#94a3b8",
          }}
        >
          {heightMetric === "renewable" ? "% renewable - beam height" : "gCO₂/kWh - beam height"}
          {heightCapped && " · zoom out for full 100%"}
        </div>

        {/* Map scale bar - real surface distance at the current zoom. Part of the
            legend, so it collapses with everything else when the legend is hidden. */}
        {/* One row: distance ruler on the left, the two layer toggles side by side on
            the right. Centre-aligned so the toggles sit against the ruler's middle. */}
        <div
          style={{
            marginTop: 14,
            width: PANEL_W,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 8,
          }}
        >
          {scale ? (
            <div title="Approximate surface distance at this zoom (near the centre of view)">
              <div
                style={{
                  width: Math.min(scale.px, PANEL_W),
                  height: 6,
                  borderBottom: "2px solid #94a3b8",
                  borderLeft: "2px solid #94a3b8",
                  borderRight: "2px solid #94a3b8",
                  boxSizing: "border-box",
                }}
              />
              <span style={{ fontSize: "0.62rem", color: "#94a3b8" }}>
                ≈ {scale.km.toLocaleString("en-US")} km
              </span>
            </div>
          ) : (
            <span />
          )}
          <div
            style={{
              display: "flex",
              flexDirection: "row",
              gap: 10,
              alignItems: "center",
              marginRight: 10,
            }}
          >
            <LayerToggle
              on={showClouds}
              onToggle={() => setShowClouds((v) => !v)}
              icon="☁"
              label="Clouds"
              title="Cloud cover -- NASA VIIRS true-color reflectance, daily mosaic"
            />
            <LayerToggle
              on={showSolar}
              onToggle={() => setShowSolar((v) => !v)}
              icon="☀"
              label="Daylight"
              title="Daylight -- solar irradiance by cosine of the solar zenith angle"
            />
          </div>
        </div>
      </div>

      {/* Empty / loading / error state - distinguish a failed fetch from loading */}
      {!webglError && points.length === 0 && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#94a3b8",
            padding: "1rem",
            textAlign: "center",
          }}
        >
          {dataError ? (
            <span>
              Couldn't load the grid data right now.{" "}
              <Link to="/dashboard" style={{ color: "#7dd3fc", textDecoration: "underline" }}>
                Try the dashboard
              </Link>
              .
            </span>
          ) : (
            "Loading live grid data…"
          )}
        </div>
      )}

      {/* Selected detail panel */}
      {selected && (
        <div
          className="globe-detail"
          style={{
            position: "absolute",
            top: 20,
            right: 24,
            width: 260,
            background: "rgba(10,15,20,0.92)",
            border: "1px solid rgba(255,255,255,0.15)",
            borderRadius: 12,
            padding: "16px 18px",
            color: "#fff",
            backdropFilter: "blur(8px)",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
            }}
          >
            <div
              style={{
                textTransform: "uppercase",
                letterSpacing: "0.5px",
                color: "#9ca3af",
                fontSize: "0.7rem",
                fontWeight: 700,
              }}
            >
              {selected.provider} · {selected.region}
            </div>
            <button
              type="button"
              onClick={() => setSelected(null)}
              style={{
                background: "none",
                border: "none",
                color: "#9ca3af",
                cursor: "pointer",
                fontSize: "1rem",
                lineHeight: 1,
                padding: 0,
              }}
            >
              ×
            </button>
          </div>
          <div
            style={{
              margin: "4px 0 12px",
              color: "#d1d5db",
              fontSize: "0.85rem",
            }}
          >
            {selected.location} <span style={{ color: "#6b7280" }}>({selected.grid_zone})</span>
          </div>
          <div
            style={{
              fontSize: "2rem",
              fontWeight: 700,
              color: intensityColor(selected.intensity),
            }}
          >
            {selected.intensity}
            <span style={{ fontSize: "0.8rem", fontWeight: 400, color: "#9ca3af" }}> gCO₂/kWh</span>
          </div>
          <div style={{ color: "#86efac", marginTop: 2 }}>{selected.renewable}% renewable</div>
          {selected.consumptionIntensity != null && (
            <div
              style={{ color: "#cbd5e1", marginTop: 6, fontSize: "0.85rem" }}
              title="Flow-traced across the European grid: what this region actually consumes after imports and exports, versus what it generates locally (the figure above)."
            >
              Consumed: ~{selected.consumptionIntensity}
              <span style={{ color: "#6b7280" }}> gCO₂/kWh · flow-traced</span>
            </div>
          )}
          {selected.marginalIntensity != null && (
            <div
              style={{
                color: "#cbd5e1",
                marginTop: 6,
                fontSize: "0.85rem",
                display: "inline-flex",
                alignItems: "center",
              }}
            >
              Marginal: ~{selected.marginalIntensity}
              <span style={{ color: "#6b7280" }}> gCO₂/kWh · extra kWh now</span>
              <InfoTip label="marginal intensity" text={MARGINAL_TIP} placement="top" />
            </div>
          )}
          {isCleanSurplus(selected.renewable, selected.intensity, selected.marginalIntensity) && (
            <div
              style={{
                marginTop: 8,
                fontSize: "0.72rem",
                fontWeight: 600,
                color: "#4ade80",
                display: "inline-flex",
                alignItems: "center",
              }}
            >
              ⚡ Clean surplus · ideal time to run
              <InfoTip label="clean surplus" text={SURPLUS_TIP} placement="top" />
            </div>
          )}
          {formatLoad(selected.gridLoadMw) && (
            <div style={{ color: "#93c5fd", marginTop: 6, fontSize: "0.85rem" }}>
              Grid load: {formatLoad(selected.gridLoadMw)}
              <span style={{ color: "#6b7280" }}> · whole grid, all consumers</span>
            </div>
          )}
          {selected.powerBreakdown && <PowerMix breakdown={selected.powerBreakdown} />}
          <RegionHistory
            provider={selected.provider}
            region={selected.region}
            current={selected.intensity}
          />
          <RegionForecast provider={selected.provider} region={selected.region} />
          <RegionWeather provider={selected.provider} region={selected.region} />
          <div
            style={{
              marginTop: 12,
              fontSize: "0.72rem",
              display: "inline-flex",
              alignItems: "center",
              color: selected.quality === "estimated" ? "#fbbf24" : "#4ade80",
            }}
          >
            {selected.quality === "estimated" ? "Estimated" : "Live grid data"}
            <span style={{ color: "#6b7280" }}> · {selected.source}</span>
            <InfoTip label="live vs estimated" text={DATA_QUALITY_TIP_RICH} placement="top" />
          </div>
        </div>
      )}
    </div>
  );
}
